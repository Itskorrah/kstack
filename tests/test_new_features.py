"""Integration-level local tests for genuinely executed KStack behaviour."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from contextlib import redirect_stdout
from pathlib import Path

from kstack.cli import main, ROOT
from kstack.project import inspect_project, bootstrap, load_project_config
from kstack.router import route
from kstack.verification import verify_project
from kstack.evidence import append, inspect
from kstack.external import inspect_package, install_package, list_external
from kstack.installer import doctor, install
from kstack.state import lock_state


class NewFeatureTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.project = self.root / "app"
        self.project.mkdir()
        self.state = self.root / "state"

    def test_doctor_uninstalled_fails(self):
        result = doctor(ROOT, self.state, "codex", "project", self.project)
        self.assertFalse(result["ok"])
        self.assertIn("not installed", result["note"])

    def test_doctor_installed_active_generation(self):
        install(ROOT, self.state, "codex", "project", self.project)
        result = doctor(ROOT, self.state, "codex", "project", self.project)
        self.assertTrue(result["ok"])
        manifest = self.project / ".agents/skills/.kstack-managed.json"
        contents = json.loads(manifest.read_text())
        contents["files"].pop("kstack-router/SKILL.md")
        manifest.write_text(json.dumps(contents))
        self.assertFalse(doctor(ROOT, self.state, "codex", "project", self.project)["ok"])

    def test_project_profile_detected(self):
        (self.project / "package.json").write_text(json.dumps({"dependencies": {"react": "18.0", "next": "15.0"}}))
        facts = inspect_project(self.project)
        self.assertEqual(facts["profile"], "web")
        self.assertIn("react", facts["technologies"])
        created = bootstrap(self.project, dry_run=False)
        self.assertEqual(created["action"], "created")
        again = bootstrap(self.project, dry_run=False)
        self.assertEqual(again["action"], "unchanged")
        self.assertEqual(load_project_config(self.project)["profile"], "web")

    def test_project_preserves_existing_config(self):
        (self.project / "kstack.json").write_text('{"version":1,"profile":"python"}')
        self.assertEqual(bootstrap(self.project, dry_run=False)["action"], "unchanged")
        self.assertEqual(load_project_config(self.project)["profile"], "python")

    def test_invalid_project_manifest_rejected(self):
        (self.project / "kstack.json").write_text('{"verification_commands":["rm -rf /"]}')
        with self.assertRaises(ValueError): load_project_config(self.project)

    def test_project_profile_prevents_traversal(self):
        (self.project / "kstack.json").write_text('{"profile":"../../data/policy"}')
        with self.assertRaisesRegex(ValueError, "profile"):
            route("build frontend", ROOT, self.state, project=self.project)

    def test_route_reports_uninstalled_external_as_candidates(self):
        (self.project / "package.json").write_text('{"dependencies":{"react":"18.0"}}')
        result = route("Overhaul UI accessibility and browser testing", ROOT, self.state, project=self.project)
        self.assertEqual(result["profile"], "web")
        self.assertIn("kstack-verify", result["installed_skill_suggestions"])
        self.assertIn("ui-skills", [x["id"] for x in result["external_candidates"]])
        self.assertTrue(all(not x["host_verified"] for x in result["external_candidates"]))

    def test_high_risk_route_requires_audit(self):
        result = route("Change authentication in production", ROOT, self.state)
        self.assertIn("kstack-audit", result["installed_skill_suggestions"])
        self.assertIn("kstack-verify", result["installed_skill_suggestions"])
        self.assertEqual(result["risk"], "elevated")

    def test_explicit_verification_runs(self):
        config = {"version": 1, "profile": "python",
                  "verification_commands": [[sys.executable, "-c", "print('PASS')"]]}
        (self.project / "kstack.json").write_text(json.dumps(config))
        result = verify_project(self.project, self.state, apply=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse((self.state / "evidence.json").exists())
        completed = verify_project(self.project, self.state, apply=True)
        self.assertTrue(completed["ok"])
        self.assertEqual(completed["commands"][0]["status"], "passed")
        self.assertTrue(inspect(self.state)["ok"])

    def test_verification_failure_is_not_success(self):
        config = {"verification_commands": [[sys.executable, "-c", "raise SystemExit(12)"],
                                            [sys.executable, "-c", "print('SHOULD NOT RUN')"]]}
        (self.project / "kstack.json").write_text(json.dumps(config))
        result = verify_project(self.project, self.state, apply=True)
        self.assertFalse(result["ok"])
        self.assertEqual(len(result["commands"]), 1)
        self.assertEqual(result["commands"][0]["returncode"], 12)

    def test_verification_is_explicit_not_magic(self):
        self.assertEqual(verify_project(self.project, self.state, apply=True)["status"], "not_configured")

    def test_evidence_chain_tampering(self):
        append(self.state, "incident", {"summary": "test"})
        append(self.state, "maintenance", {"summary": "next"})
        self.assertEqual(inspect(self.state)["records"], 2)
        path = self.state / "evidence.json"
        events = json.loads(path.read_text())
        events[0]["detail"]["summary"] = "tampered"
        path.write_text(json.dumps(events))
        self.assertFalse(inspect(self.state)["ok"])
        with self.assertRaises(ValueError): append(self.state, "incident", {})

    def test_state_lock_concurrent_refused(self):
        with lock_state(self.state):
            with self.assertRaisesRegex(ValueError, "locked"):
                with lock_state(self.state):
                    pass
        self.assertFalse((self.state / ".write-lock").exists())

    def _git_source(self):
        source = self.root / "external"
        directory = source / "skills" / "useful"
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text('---\nname: useful\ndescription: Carefully check project validity and tests when implementing code.\n---\n# Guide\n\n' + 'Inspect and test real behaviour. ' * 12)
        def git(*args):
            result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        git("init", "-q")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "test")
        return source, git("rev-parse", "HEAD")

    def test_reviewed_external_package_install(self):
        source, commit = self._git_source()
        report = inspect_package(source, "skills/useful", commit)
        self.assertFalse(report["contains_code_or_assets"])
        dry = install_package(source, "skills/useful", commit, "codex", "project", self.project)
        self.assertTrue(dry["dry_run"])
        self.assertFalse((self.project / ".agents/skills/useful").exists())
        with self.assertRaisesRegex(ValueError, "reviewed"):
            install_package(source, "skills/useful", commit, "codex", "project", self.project, dry_run=False)
        result = install_package(source, "skills/useful", commit, "codex", "project", self.project,
                                 dry_run=False, reviewed=True)
        self.assertTrue(result["installed"])
        self.assertTrue(list_external("codex", "project", self.project)["ok"])
        (self.project / ".agents/skills/useful/SKILL.md").write_text("tampered")
        self.assertFalse(list_external("codex", "project", self.project)["ok"])

    def test_pinned_external_commit_and_clean_checkout(self):
        source, commit = self._git_source()
        with self.assertRaises(ValueError): inspect_package(source, "skills/useful", "f" * 40)
        (source / "skills/useful/readme.md").write_text("untracked")
        with self.assertRaisesRegex(ValueError, "untracked"):
            inspect_package(source, "skills/useful", commit)

    def test_external_package_code_requires_extra_approval(self):
        source, _ = self._git_source()
        (source / "skills/useful/tool.py").write_text("print('NEVER EXECUTED')")
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(source), "-c", "commit.gpgsign=false", "commit", "-qm", "code"], check=True)
        commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
        with self.assertRaisesRegex(ValueError, "allow-code"):
            install_package(source, "skills/useful", commit, "codex", "project", self.project,
                            dry_run=False, reviewed=True)
        result = install_package(source, "skills/useful", commit, "codex", "project", self.project,
                                 dry_run=False, reviewed=True, allow_code=True)
        self.assertTrue(result["installed"])

    def test_cli_workflow(self):
        buf = StringIO()
        with redirect_stdout(buf):
            code = main(["--state", str(self.state), "bootstrap", "--project", str(self.project), "--apply"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(buf.getvalue())["action"], "created")
        self.assertFalse((self.state / ".write-lock").exists())

    def test_verification_never_persists_raw_output(self):
        from kstack.verification import verify_project
        secret = 'DUMMY_TEST_SECRET_DO_NOT_STORE'
        config = {"verification_commands": [[sys.executable, "-c", f"print({secret!r})"]]}
        (self.project / "kstack.json").write_text(json.dumps(config))
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["ok"])
        self.assertTrue(answer["commands"][0]["output_redacted"])
        self.assertNotIn(secret, (self.state / "evidence.json").read_text())
