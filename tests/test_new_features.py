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
from kstack.external import inspect_package, install_package, list_external, uninstall_package
from kstack.installer import doctor, install
from kstack.state import lock_state, lock_status


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

    def test_declared_monorepo_roots_and_unapproved_verification_suggestions(self):
        (self.project / "package.json").write_text(json.dumps({"workspaces": ["apps/*", "packages/*"]}))
        web = self.project / "apps/web"
        web.mkdir(parents=True)
        (web / "package.json").write_text(json.dumps({"dependencies": {"react": "19"},
                                                        "scripts": {"test": "echo tests", "build": "vite build"}}))
        api = self.project / "packages/api"
        (api / "tests").mkdir(parents=True)
        (api / "pyproject.toml").write_text("[project]\nname='api'\n")
        facts = inspect_project(self.project)
        self.assertEqual(facts["profile"], "monorepo")
        self.assertIn("python", facts["technologies"])
        self.assertIn("react", facts["technologies"])
        self.assertEqual({item["path"] for item in facts["workspace"]["targets"]},
                         {".", "apps/web", "packages/api"})
        self.assertTrue(all(item["requires_owner_review"] and not item["executed"]
                            for item in facts["verification_suggestions"]))
        created = bootstrap(self.project, dry_run=False)
        config = load_project_config(self.project)
        self.assertEqual(created["action"], "created")
        self.assertEqual(config["verification_commands"], [])
        self.assertNotIn("verification_targets", config)

    def test_version_two_verification_targets_run_from_declared_root(self):
        target = self.project / "packages/api"
        target.mkdir(parents=True)
        (self.project / "kstack.json").write_text(json.dumps({
            "version": 2, "profile": "monorepo", "verification_commands": [],
            "verification_targets": [{"path": "packages/api", "commands": [[
                sys.executable, "-c", "from pathlib import Path; print(Path.cwd().name)"]]}]
        }))
        plan = verify_project(self.project, self.state, apply=False)
        self.assertEqual(plan["commands"][0]["working_directory"], "packages/api")
        result = verify_project(self.project, self.state, apply=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["commands"][0]["working_directory"], "packages/api")

    def test_version_two_verification_targets_reject_path_escape(self):
        (self.project / "kstack.json").write_text(json.dumps({
            "version": 2, "verification_targets": [{"path": "../outside", "commands": [["true"]]}]
        }))
        with self.assertRaisesRegex(ValueError, "relative directory"):
            load_project_config(self.project)

    def test_version_two_verification_targets_reject_windows_drive_path(self):
        (self.project / "kstack.json").write_text(json.dumps({
            "version": 2, "verification_targets": [{"path": "C:/outside", "commands": [["true"]]}]
        }))
        with self.assertRaisesRegex(ValueError, "relative directory"):
            load_project_config(self.project)

    def test_route_reports_uninstalled_external_as_candidates(self):
        (self.project / "package.json").write_text('{"dependencies":{"react":"18.0"}}')
        result = route("Overhaul UI accessibility and browser testing", ROOT, self.state, project=self.project)
        self.assertEqual(result["profile"], "web")
        self.assertIn("kstack-verify", [x["name"] for x in result["workflow_suggestions"]])
        self.assertIn("ui-skills", [x["id"] for x in result["external_candidates"]])
        self.assertTrue(all(not x["host_verified"] for x in result["external_candidates"]))

    def test_high_risk_route_requires_audit(self):
        result = route("Change authentication in production", ROOT, self.state)
        self.assertIn("kstack-audit", [x["name"] for x in result["workflow_suggestions"]])
        self.assertIn("kstack-verify", [x["name"] for x in result["workflow_suggestions"]])
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
            self.assertTrue(lock_status(self.state)["locked"])
        self.assertTrue((self.state / ".kstack-write.lock").is_file())
        self.assertFalse(lock_status(self.state)["locked"])

    def test_state_lock_preserves_existing_directory_permissions(self):
        import os
        import stat
        if os.name != "posix":
            self.skipTest("POSIX directory mode check required")
        self.state.mkdir(exist_ok=True)
        self.state.chmod(0o755)
        with lock_state(self.state):
            pass
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o755)

    def test_state_lock_serializes_separate_processes_and_releases_on_exit(self):
        import os
        code = ("import sys, time\nfrom pathlib import Path\nfrom kstack.state import lock_state\n"
                "with lock_state(Path(sys.argv[1])):\n    print('READY', flush=True)\n    time.sleep(30)\n")
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        child = subprocess.Popen([sys.executable, "-c", code, str(self.state)],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            self.assertTrue(lock_status(self.state)["locked"])
            with self.assertRaisesRegex(ValueError, "locked"):
                with lock_state(self.state):
                    pass
        finally:
            child.terminate()
            child.wait(timeout=10)
            child.stdout.close()
            child.stderr.close()
        self.assertFalse(lock_status(self.state)["locked"])
        with lock_state(self.state):
            self.assertTrue(lock_status(self.state)["locked"])

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

    def _dependency_package(self):
        source = self.root / "dependency-package"
        entries = [
            {"name": "coordinator", "path": "skills/coordinator", "version": "1.0.0",
             "dependencies": [{"name": "audit", "specifier": ">=1.0.0,<2.0.0"},
                              {"name": "verify", "specifier": "^2.1.0"}],
             "provides": ["orchestration.evolve"]},
            {"name": "audit", "path": "skills/audit", "version": "1.4.0",
             "provides": ["review.audit"]},
            {"name": "verify", "path": "skills/verify", "version": "2.3.0",
             "dependencies": [{"name": "audit", "specifier": "~1.4.0"}],
             "provides": ["testing.regression"]},
        ]
        for item in entries:
            directory = source / item["path"]
            directory.mkdir(parents=True)
            (directory / "SKILL.md").write_text(
                f'---\nname: {item["name"]}\ndescription: Use this skill when its declared package capability is needed.\n---\n'
                "Inspect repository behavior, apply the requested change, and verify the result.\n")
        manifest = source / "kstack-package.json"
        manifest.write_text(json.dumps({"format": 1, "skills": entries}, indent=2) + "\n")
        def git(*args):
            result = subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        git("init", "-q")
        git("config", "user.email", "test@example.com")
        git("config", "user.name", "Test")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "package")
        return source, manifest, entries, git

    def test_sibling_package_resolves_versions_and_capabilities(self):
        source, _manifest, _entries, git = self._dependency_package()
        commit = git("rev-parse", "HEAD")
        package = inspect_package(source, "skills/coordinator", commit)
        self.assertEqual([x["name"] for x in package["resolved_skills"]], ["audit", "verify", "coordinator"])
        self.assertEqual(package["providers"], {"review.audit": "audit", "testing.regression": "verify",
                                                   "orchestration.evolve": "coordinator"})
        self.assertEqual(package["dependencies"], ["audit", "verify"])
        result = install_package(source, "skills/coordinator", commit, "codex", "project", self.project,
                                 dry_run=False, reviewed=True)
        self.assertEqual(result["installed_skills"], ["audit", "verify", "coordinator"])
        self.assertTrue((self.project / ".agents/skills/audit/SKILL.md").is_file())
        status = list_external("codex", "project", self.project)
        self.assertTrue(status["ok"])
        self.assertEqual({x["capability"] for x in status["capabilities"]},
                         {"review.audit", "testing.regression", "orchestration.evolve"})
        routed = route("Comprehensively refactor the project", ROOT, self.state, project=self.project,
                       host="codex", scope="project")
        evolve = next(x for x in routed["external_candidates"] if x["id"] == "evolve")
        self.assertEqual(evolve["status"], "installed-files-unverified")
        self.assertEqual(evolve["installed_skills"], ["coordinator"])
        self.assertFalse(evolve["host_verified"])

    def test_router_distinguishes_available_from_host_installed_workflows(self):
        result = route("Fix an API bug and run regression tests", ROOT, self.state,
                       project=self.project, host="codex", scope="project")
        verify = next(x for x in result["workflow_suggestions"] if x["name"] == "kstack-verify")
        self.assertEqual(verify["status"], "available-not-installed")
        install(ROOT, self.state, "codex", "project", self.project)
        installed = route("Fix an API bug and run regression tests", ROOT, self.state,
                          project=self.project, host="codex", scope="project")
        verify = next(x for x in installed["workflow_suggestions"] if x["name"] == "kstack-verify")
        self.assertEqual(verify["status"], "installed-files-unverified")
        self.assertFalse(verify["host_verified"])

    def test_sibling_package_rejects_missing_cyclic_and_incompatible_dependencies(self):
        from copy import deepcopy
        source, manifest, entries, git = self._dependency_package()
        cases = []
        missing = deepcopy(entries)
        missing[0]["dependencies"] = [{"name": "missing", "specifier": "*"}]
        cases.append((missing, "Missing sibling dependency"))
        cycle = deepcopy(entries)
        cycle[1]["dependencies"] = [{"name": "coordinator", "specifier": "*"}]
        cases.append((cycle, "Cyclic skill dependency"))
        incompatible = deepcopy(entries)
        incompatible[0]["dependencies"][0]["specifier"] = ">=2.0.0,<3.0.0"
        cases.append((incompatible, "does not satisfy"))
        windows_path = deepcopy(entries)
        windows_path[1]["path"] = "C:/outside"
        cases.append((windows_path, "Invalid package skill path"))
        for index, (skills, message) in enumerate(cases):
            with self.subTest(message=message):
                manifest.write_text(json.dumps({"format": 1, "skills": skills}, indent=2) + "\n")
                git("add", "kstack-package.json")
                git("-c", "commit.gpgsign=false", "commit", "-qm", f"invalid package {index}")
                with self.assertRaisesRegex(ValueError, message):
                    inspect_package(source, "skills/coordinator", git("rev-parse", "HEAD"))

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

    def test_external_install_refuses_to_adopt_matching_unmanaged_file(self):
        source, commit = self._git_source()
        target = self.project / ".agents/skills/useful/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes((source / "skills/useful/SKILL.md").read_bytes())
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            install_package(source, "skills/useful", commit, "codex", "project", self.project,
                            dry_run=False, reviewed=True)
        self.assertFalse((self.project / ".agents/skills/.kstack-external-managed.json").exists())
        self.assertTrue(target.is_file())

    def test_external_uninstall_dry_run_and_preserves_unmanaged_files(self):
        source, commit = self._git_source()
        install_package(source, "skills/useful", commit, "codex", "project", self.project,
                        dry_run=False, reviewed=True)
        folder = self.project / ".agents/skills/useful"
        target = folder / "SKILL.md"
        note = folder / "owner-notes.txt"
        note.write_text("keep this user file")
        dry = uninstall_package("useful", "codex", "project", self.project, dry_run=True)
        self.assertEqual(dry["status"], "would_remove")
        self.assertTrue(target.exists())
        result = uninstall_package("useful", "codex", "project", self.project)
        self.assertEqual(result["status"], "removed")
        self.assertFalse(target.exists())
        self.assertEqual(note.read_text(), "keep this user file")
        self.assertTrue(list_external("codex", "project", self.project)["ok"])

    def test_external_uninstall_refuses_modified_file(self):
        source, commit = self._git_source()
        install_package(source, "skills/useful", commit, "codex", "project", self.project,
                        dry_run=False, reviewed=True)
        target = self.project / ".agents/skills/useful/SKILL.md"
        target.write_text("owner edit")
        with self.assertRaisesRegex(ValueError, "modified"):
            uninstall_package("useful", "codex", "project", self.project)
        self.assertEqual(target.read_text(), "owner edit")
        self.assertTrue((self.project / ".agents/skills/.kstack-external-managed.json").exists())

    def test_external_uninstall_requires_removing_dependents_first(self):
        source, _manifest, _entries, git = self._dependency_package()
        commit = git("rev-parse", "HEAD")
        install_package(source, "skills/coordinator", commit, "codex", "project", self.project,
                        dry_run=False, reviewed=True)
        with self.assertRaisesRegex(ValueError, "installed dependents.*verify"):
            uninstall_package("audit", "codex", "project", self.project)
        uninstall_package("coordinator", "codex", "project", self.project)
        uninstall_package("verify", "codex", "project", self.project)
        result = uninstall_package("audit", "codex", "project", self.project)
        self.assertEqual(result["status"], "removed")

    def test_pinned_external_commit_and_clean_checkout(self):
        source, commit = self._git_source()
        with self.assertRaises(ValueError): inspect_package(source, "skills/useful", "f" * 40)
        (source / "skills/useful/readme.md").write_text("untracked")
        with self.assertRaisesRegex(ValueError, "untracked"):
            inspect_package(source, "skills/useful", commit)

    def test_external_git_inspection_disables_configured_fsmonitor(self):
        import os
        import shlex
        if os.name != "posix":
            self.skipTest("POSIX executable fixture required")
        source, commit = self._git_source()
        marker = self.root / "fsmonitor-was-run"
        helper = self.root / "fsmonitor-helper"
        helper.write_text(f"#!/bin/sh\nprintf called > {shlex.quote(str(marker))}\n")
        helper.chmod(helper.stat().st_mode | 0o111)
        subprocess.run(["git", "-C", str(source), "config", "core.fsmonitor", str(helper)], check=True)
        inspect_package(source, "skills/useful", commit)
        self.assertFalse(marker.exists())

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
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--state", str(self.state), "external-uninstall", "--host", "codex",
                         "--scope", "project", "--project", str(self.project), "--name", "absent-skill"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "not_installed")
        self.assertTrue((self.state / ".kstack-write.lock").is_file())
        self.assertFalse(lock_status(self.state)["locked"])

    def test_verification_never_persists_raw_output(self):
        from kstack.verification import verify_project
        secret = 'DUMMY_TEST_SECRET_DO_NOT_STORE'
        config = {"verification_commands": [[sys.executable, "-c", f"print({secret!r})"]]}
        (self.project / "kstack.json").write_text(json.dumps(config))
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["ok"])
        self.assertTrue(answer["commands"][0]["output_redacted"])
        self.assertNotIn(secret, (self.state / "evidence.json").read_text())
