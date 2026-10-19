import json
import tempfile
import unittest
from pathlib import Path
from kstack.cli import ROOT
from kstack.installer import install, uninstall, doctor, available_skills, bundled_skills, skill_dir
from kstack.state import write_json
from kstack.security import digest
from unittest.mock import patch

class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.state = self.dir / "state"
        self.project = self.dir / "project"
        self.project.mkdir()
    def test_bundled(self):
        self.assertGreaterEqual(len(bundled_skills(ROOT)), 4)
    def test_global_codex_install(self):
        ans = install(ROOT, self.state, "codex", "global", home=self.dir)
        self.assertTrue(Path(ans["destination"]).exists())
        self.assertTrue(doctor(ROOT, self.state, "codex", home=self.dir)["ok"])
        self.assertTrue(ans["transaction"]["committed"])
        manifest = json.loads((Path(ans["destination"]) / ".kstack-managed.json").read_text())
        self.assertEqual(manifest["version"], 3)
        self.assertTrue((Path(ans["destination"]) / ".kstack-generations" / manifest["generation"]).is_dir())
        repeat = install(ROOT, self.state, "codex", "global", home=self.dir)
        self.assertTrue(all(item["action"] == "unchanged" for item in repeat["changes"]))
        self.assertFalse(repeat["transaction"]["committed"])
        done = uninstall("codex", "global", home=self.dir)
        self.assertGreaterEqual(len(done["removed"]), 4)

    def test_host_install_rollback_restores_prior_generation(self):
        from kstack import installer
        install(ROOT, self.state, "codex", "project", self.project)
        location = skill_dir("codex", "project", self.project)
        target = location / "kstack-router/SKILL.md"
        previous = target.read_text()
        skills = installer.available_skills(ROOT, self.state)
        changed = dict(skills)
        changed["kstack-router"] = previous.replace("KStack", "KStack Updated", 1)
        with patch.object(installer, "available_skills", return_value=changed):
            result = install(ROOT, self.state, "codex", "project", self.project)
            self.assertTrue(result["transaction"]["committed"])
            self.assertIn("KStack Updated", target.read_text())
            rolled = installer.rollback_install("codex", "project", self.project)
        self.assertTrue(rolled["rolled_back"])
        self.assertEqual(target.read_text(), previous)
        self.assertTrue(doctor(ROOT, self.state, "codex", "project", self.project)["ok"])

    def test_host_rollback_refuses_changed_current_file(self):
        from kstack import installer
        install(ROOT, self.state, "codex", "project", self.project)
        location = skill_dir("codex", "project", self.project)
        target = location / "kstack-router/SKILL.md"
        skills = installer.available_skills(ROOT, self.state)
        changed = dict(skills)
        changed["kstack-router"] = target.read_text().replace("KStack", "KStack Updated", 1)
        with patch.object(installer, "available_skills", return_value=changed):
            install(ROOT, self.state, "codex", "project", self.project)
        target.write_text("user change")
        with self.assertRaisesRegex(ValueError, "refusing rollback"):
            installer.rollback_install("codex", "project", self.project)
    def test_project_claude_install(self):
        answer = install(ROOT, self.state, "claude", "project", self.project)
        self.assertIn(".claude/skills", answer["destination"])
        self.assertTrue(doctor(ROOT, self.state, "claude", "project", self.project)["ok"])
    def test_dry_run_no_mutation(self):
        x = install(ROOT, self.state, "codex", "project", self.project, dry_run=True)
        self.assertFalse(Path(x["destination"]).exists())
    def test_no_unmanaged_overwrites(self):
        path = skill_dir("codex", "project", self.project) / "kstack-router" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("changed")
        with self.assertRaises(ValueError): install(ROOT, self.state, "codex", "project", self.project)
    def test_no_adopting_identical_unmanaged_skill(self):
        content = available_skills(ROOT, self.state)["kstack-router"]
        path = skill_dir("codex", "project", self.project) / "kstack-router" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(content)
        with self.assertRaisesRegex(ValueError, "unmanaged"):
            install(ROOT, self.state, "codex", "project", self.project)
        self.assertEqual(path.read_text(), content)
    def test_no_overwrite_modified_managed(self):
        install(ROOT, self.state, "codex", "project", self.project)
        path = skill_dir("codex", "project", self.project) / "kstack-router" / "SKILL.md"
        path.write_text("owner modified")
        with self.assertRaises(ValueError): install(ROOT, self.state, "codex", "project", self.project)
        with self.assertRaises(ValueError): uninstall("codex", "project", self.project)
    def test_external_integrity(self):
        with self.assertRaises(ValueError):
            write_json(self.state / "active.json", {"a": {"name": "extra-skill", "content_sha256": "0" * 64}})
            available_skills(ROOT, self.state)
    def test_stale_managed_skill_removed_on_sync(self):
        install(ROOT, self.state, "codex", "project", self.project)
        loc = skill_dir("codex", "project", self.project)
        obsolete = loc / "kstack-router" / "SKILL.md"
        manifest_file = loc / ".kstack-managed.json"
        # Simulate a previously managed skill not present in the desired set.
        from unittest.mock import patch
        from kstack import installer
        original = installer.available_skills(ROOT, self.state)
        filtered = {k: v for k, v in original.items() if k != "kstack-router"}
        with patch.object(installer, "available_skills", return_value=filtered):
            result = installer.install(ROOT, self.state, "codex", "project", self.project)
        self.assertFalse(obsolete.exists())
        self.assertTrue(any(x["action"] == "remove-stale" for x in result["changes"]))
        self.assertNotIn("kstack-router/SKILL.md", json.loads(manifest_file.read_text())["files"])
    def test_symlink_parent_is_rejected(self):
        target = self.project / ".agents"
        target.symlink_to(self.state, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            install(ROOT, self.state, "codex", "project", self.project)
    def test_invalid_scope(self):
        with self.assertRaises(ValueError): skill_dir("unknown", "project", self.project)
