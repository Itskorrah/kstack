"""Clean-checkout fixture coverage for portable skill package path validation."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from kstack.external import inspect_package


class PortableExternalPackageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.root.joinpath("skills", "alpha").mkdir(parents=True)
        (self.root / "skills/alpha/SKILL.md").write_text(
            "---\nname: alpha\ndescription: Thorough local validation of trustworthy project changes.\n---\n"
            "Review changes and verify their behaviour with tests.\n", encoding="utf-8"
        )

    def commit_fixture(self):
        def git(*args):
            result = subprocess.run(["git", "-C", str(self.root), *args],
                                    text=True, capture_output=True, check=True)
            return result.stdout.strip()
        git("init", "-q")
        git("config", "user.email", "fixture@example.invalid")
        git("config", "user.name", "Portable test")
        git("add", ".")
        git("-c", "commit.gpgsign=false", "commit", "-qm", "fixture")
        return git("rev-parse", "HEAD")

    def test_colliding_files_rejected_in_clean_checkout(self):
        first = self.root / "skills/alpha/Docs/Guide.md"
        second = self.root / "skills/alpha/docs/guide.md"
        first.parent.mkdir()
        second.parent.mkdir(exist_ok=True)
        first.write_text("A", encoding="utf-8")
        second.write_text("B", encoding="utf-8")
        if first.samefile(second):
            self.skipTest("Host filesystem cannot distinguish case variants")
        commit = self.commit_fixture()
        with self.assertRaisesRegex(ValueError, "colliding file paths"):
            inspect_package(self.root, "skills/alpha", commit)

    def test_colliding_manifest_skill_roots_rejected(self):
        other = self.root / "skills/ALPHA"
        other.mkdir(exist_ok=True)
        (other / "SKILL.md").write_text(
            "---\nname: beta\ndescription: Carefully validate a project before release.\n---\n",
            encoding="utf-8"
        )
        if (self.root / "skills/alpha").samefile(other):
            self.skipTest("Host filesystem cannot distinguish case variants")
        (self.root / "kstack-package.json").write_text(json.dumps({
            "format": 1,
            "skills": [
                {"name": "alpha", "path": "skills/alpha", "version": "1.0.0"},
                {"name": "beta", "path": "skills/ALPHA", "version": "1.0.0"},
            ],
        }), encoding="utf-8")
        commit = self.commit_fixture()
        with self.assertRaisesRegex(ValueError, "colliding paths"):
            inspect_package(self.root, "skills/alpha", commit)


if __name__ == "__main__":
    unittest.main()
