"""Git revision binding and complete failure receipts for project checks."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from kstack.verification import verify_project
from kstack.evidence import inspect


class VerificationRevisionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.project = Path(tmp.name) / "project"
        self.project.mkdir()
        self.state = Path(tmp.name) / "state"
        (self.project / "tracked.txt").write_text("original", encoding="utf-8")
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")

    def git(self, *args):
        run = subprocess.run(["git", "-C", str(self.project), *args],
                             capture_output=True, text=True, check=True)
        return run.stdout.strip()

    def configure(self, argv):
        (self.project / "kstack.json").write_text(
            json.dumps({"version": 1, "verification_commands": [argv]}), encoding="utf-8")
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "-qm", "baseline")

    def test_unchanged_revision_passes(self):
        self.configure([sys.executable, "-c", "print('ok')"])
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["ok"])
        self.assertTrue(answer["revision_stable"])
        self.assertTrue(answer["checks_passed"])
        self.assertEqual(answer["git_snapshot"], answer["pre_verification_git_snapshot"])
        self.assertTrue(inspect(self.state)["ok"])

    def test_dirty_worktree_after_passing_check_is_not_verified(self):
        self.configure([sys.executable, "-c",
                        "from pathlib import Path; Path('tracked.txt').write_text('modified')"])
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["checks_passed"])
        self.assertFalse(answer["revision_stable"])
        self.assertFalse(answer["ok"])
        self.assertEqual(answer["status"], "incomplete")
        self.assertTrue(answer["pre_verification_git_snapshot"]["clean"])
        self.assertFalse(answer["git_snapshot"]["clean"])

    def test_preexisting_dirty_tracked_change_is_bound_by_content(self):
        self.configure([sys.executable, "-c",
                        "from pathlib import Path; Path('tracked.txt').write_text('changed again')"])
        (self.project / "tracked.txt").write_text("preexisting local edit", encoding="utf-8")
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["checks_passed"])
        self.assertFalse(answer["pre_verification_git_snapshot"]["clean"])
        self.assertFalse(answer["git_snapshot"]["clean"])
        self.assertNotEqual(answer["pre_verification_git_snapshot"]["worktree_sha256"],
                            answer["git_snapshot"]["worktree_sha256"])
        self.assertFalse(answer["revision_stable"])
        self.assertFalse(answer["ok"])

    def test_preexisting_untracked_change_is_bound_by_content(self):
        self.configure([sys.executable, "-c",
                        "from pathlib import Path; Path('generated.txt').write_text('changed again')"])
        (self.project / "generated.txt").write_text("preexisting generated file", encoding="utf-8")
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["checks_passed"])
        self.assertNotEqual(answer["pre_verification_git_snapshot"]["worktree_sha256"],
                            answer["git_snapshot"]["worktree_sha256"])
        self.assertFalse(answer["revision_stable"])
        self.assertFalse(answer["ok"])

    def test_index_state_change_is_not_hidden_by_same_dirty_content(self):
        script = ("import subprocess; subprocess.run(['git', 'reset', '--quiet', 'HEAD', "
                  "'--', 'tracked.txt'], check=True)")
        self.configure([sys.executable, "-c", script])
        (self.project / "tracked.txt").write_text("staged edit", encoding="utf-8")
        self.git("add", "tracked.txt")
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["checks_passed"])
        self.assertFalse(answer["pre_verification_git_snapshot"]["clean"])
        self.assertFalse(answer["git_snapshot"]["clean"])
        self.assertNotEqual(answer["pre_verification_git_snapshot"]["worktree_sha256"],
                            answer["git_snapshot"]["worktree_sha256"])
        self.assertFalse(answer["revision_stable"])
        self.assertFalse(answer["ok"])

    def test_unchanged_preexisting_dirty_tree_can_still_be_verified(self):
        self.configure([sys.executable, "-c", "print('ok')"])
        (self.project / "tracked.txt").write_text("preexisting local edit", encoding="utf-8")
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["checks_passed"])
        self.assertFalse(answer["pre_verification_git_snapshot"]["clean"])
        self.assertTrue(answer["revision_stable"])
        self.assertTrue(answer["ok"])

    def test_commit_moving_head_after_passing_check_is_not_verified(self):
        script = ("import subprocess; from pathlib import Path; "
                  "Path('tracked.txt').write_text('new contents'); "
                  "subprocess.run(['git','add','tracked.txt'],check=True); "
                  "subprocess.run(['git','-c','commit.gpgsign=false','commit','-qm','updated'],check=True)")
        self.configure([sys.executable, "-c", script])
        answer = verify_project(self.project, self.state, apply=True)
        self.assertTrue(answer["checks_passed"])
        self.assertFalse(answer["revision_stable"])
        self.assertFalse(answer["ok"])
        self.assertNotEqual(answer["pre_verification_git_snapshot"]["commit"],
                            answer["git_snapshot"]["commit"])

    def test_missing_test_tool_has_command_hash(self):
        argv = ["kstack_test_tool_that_does_not_exist_2038"]
        self.configure(argv)
        answer = verify_project(self.project, self.state, apply=True)
        self.assertFalse(answer["ok"])
        item = answer["commands"][0]
        self.assertEqual(item["status"], "blocked")
        self.assertEqual(item["argv_sha256"], hashlib.sha256(json.dumps(argv).encode()).hexdigest())
        self.assertIn("elapsed_seconds", item)
        self.assertNotIn("argv", item)

    def test_timeout_receipt_has_command_hash(self):
        argv = [sys.executable, "-c", "import time; time.sleep(3)"]
        self.configure(argv)
        answer = verify_project(self.project, self.state, apply=True, timeout=1)
        self.assertFalse(answer["ok"])
        item = answer["commands"][0]
        self.assertEqual(item["status"], "timeout")
        self.assertEqual(item["argv_sha256"], hashlib.sha256(json.dumps(argv).encode()).hexdigest())
        self.assertIn("elapsed_seconds", item)


if __name__ == "__main__":
    unittest.main()
