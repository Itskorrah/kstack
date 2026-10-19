"""Adversarial host transaction tests; no platform host or network required."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from kstack.transaction import (
    HOST_JOURNAL, STAGE_PREFIX, _host_path_key, commit_host_files,
    recover_host_files,
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


class HostPathIdentityTests(unittest.TestCase):
    def test_normalised_host_names_collide(self):
        self.assertEqual(_host_path_key("Skill/Guide.md"), _host_path_key("skill/guide.md"))
        self.assertEqual(_host_path_key("café.md"), _host_path_key("cafe\u0301.md"))

    def test_transaction_rejects_case_alias_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "path collision"):
                commit_host_files(root, {"SKILL/Guide.md": b"one", "skill/guide.md": b"two"})
            self.assertEqual(list(root.iterdir()), [])

    def test_transaction_rejects_normalisation_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "path collision"):
                commit_host_files(root, {"café.md": b"one", "cafe\u0301.md": b"two"})
            self.assertEqual(list(root.iterdir()), [])


class HostRecoveryPreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.stage_name = STAGE_PREFIX + "a" * 32
        self.stage = self.root / self.stage_name

    def interrupted(self, entries, *, generation=None):
        """entries: list of (relative path, old bytes, new bytes, observed bytes)."""
        journal_entries = []
        for relative, old, new, observed in entries:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(observed)
            backup = self.stage / "backup" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(old)
            journal_entries.append({
                "path": relative, "old_sha256": sha(old),
                "old_mode": 0o644, "new_sha256": sha(new),
            })
        journal = {"format": 1, "stage": self.stage_name, "entries": journal_entries}
        if generation is not None:
            journal["generation"] = generation
        (self.root / HOST_JOURNAL).write_text(json.dumps(journal), encoding="utf-8")

    def test_late_user_edit_does_not_partially_rollback(self):
        self.interrupted([
            ("a.txt", b"old-a", b"new-a", b"new-a"),
            ("b.txt", b"old-b", b"new-b", b"user-edited-b"),
        ])
        with self.assertRaisesRegex(ValueError, "manual recovery"):
            recover_host_files(self.root)
        self.assertEqual((self.root / "a.txt").read_bytes(), b"new-a")
        self.assertEqual((self.root / "b.txt").read_bytes(), b"user-edited-b")
        self.assertTrue((self.root / HOST_JOURNAL).exists())

    def test_late_corrupt_backup_does_not_partially_rollback(self):
        self.interrupted([
            ("a.txt", b"old-a", b"new-a", b"new-a"),
            ("b.txt", b"old-b", b"new-b", b"new-b"),
        ])
        (self.stage / "backup/b.txt").write_bytes(b"corrupted")
        with self.assertRaisesRegex(ValueError, "missing or corrupt"):
            recover_host_files(self.root)
        self.assertEqual((self.root / "a.txt").read_bytes(), b"new-a")
        self.assertEqual((self.root / "b.txt").read_bytes(), b"new-b")
        self.assertTrue((self.root / HOST_JOURNAL).exists())

    @unittest.skipIf(os.name == "nt", "Separate case variants require a case-sensitive fixture filesystem")
    def test_colliding_journal_paths_do_not_rollback(self):
        self.interrupted([
            ("A.txt", b"old-a", b"new-a", b"new-a"),
            ("a.txt", b"old-b", b"new-b", b"new-b"),
        ])
        with self.assertRaisesRegex(ValueError, "case-insensitive"):
            recover_host_files(self.root)
        self.assertEqual((self.root / "A.txt").read_bytes(), b"new-a")
        self.assertEqual((self.root / "a.txt").read_bytes(), b"new-b")

    def test_complete_generation_recovers_all_files(self):
        self.interrupted([
            ("a.txt", b"old-a", b"new-a", b"new-a"),
            ("sub/b.txt", b"old-b", b"new-b", b"new-b"),
        ])
        result = recover_host_files(self.root)
        self.assertTrue(result["recovered"])
        self.assertEqual((self.root / "a.txt").read_bytes(), b"old-a")
        self.assertEqual((self.root / "sub/b.txt").read_bytes(), b"old-b")
        self.assertFalse((self.root / HOST_JOURNAL).exists())

    def test_unsafe_generation_snapshot_rejected_before_rollback(self):
        self.interrupted([("a.txt", b"old", b"new", b"new")], generation="a" * 32)
        snapshot_parent = self.root / ".kstack-generations"
        snapshot_parent.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (snapshot_parent / ("a" * 32)).symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlinks unavailable on this filesystem")
        with self.assertRaisesRegex(ValueError, "symlink"):
            recover_host_files(self.root)
        self.assertEqual((self.root / "a.txt").read_bytes(), b"new")
        self.assertTrue((self.root / HOST_JOURNAL).exists())


if __name__ == "__main__":
    unittest.main()
