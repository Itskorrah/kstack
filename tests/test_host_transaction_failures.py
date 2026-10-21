"""Failure injection at host-generation replacement and journal boundaries."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from kstack import transaction
from kstack.transaction import (
    HOST_JOURNAL, STAGE_PREFIX, commit_host_files, recover_host_files,
)


class HostTransactionFailureMatrixTests(unittest.TestCase):
    def _initial_host(self, root):
        root.mkdir()
        (root / "obsolete.txt").write_bytes(b"old-obsolete")
        (root / "skills").mkdir()
        (root / "skills/a.txt").write_bytes(b"old-a")
        (root / "skills/b.txt").write_bytes(b"old-b")
        (root / ".kstack-managed.json").write_bytes(b"old-manifest")

    def _assert_old_generation(self, root):
        self.assertFalse((root / "new.txt").exists())
        self.assertEqual((root / "obsolete.txt").read_bytes(), b"old-obsolete")
        self.assertEqual((root / "skills/a.txt").read_bytes(), b"old-a")
        self.assertEqual((root / "skills/b.txt").read_bytes(), b"old-b")
        self.assertEqual((root / ".kstack-managed.json").read_bytes(), b"old-manifest")
        self.assertFalse((root / HOST_JOURNAL).exists())
        self.assertFalse((root / (STAGE_PREFIX + "a" * 32)).exists())
        self.assertFalse((root / ".kstack-generations" / ("a" * 32)).exists())

    def test_each_managed_replace_recovers_if_failure_occurs_before_or_after(self):
        changes = {
            "new.txt": b"created",
            "obsolete.txt": None,
            "skills/a.txt": b"new-a",
            "skills/b.txt": b"new-b",
            ".kstack-managed.json": b"new-manifest",
        }
        replacement_targets = {"new.txt", "skills/a.txt", "skills/b.txt", ".kstack-managed.json"}
        for timing in ("before", "after"):
            for failure_at in range(1, 5):
                with self.subTest(timing=timing, failure_at=failure_at):
                    with tempfile.TemporaryDirectory() as directory:
                        root = Path(directory) / "host"
                        self._initial_host(root)
                        original_replace = transaction.os.replace
                        calls = {"count": 0}

                        def fail_at_boundary(source, destination):
                            destination_path = Path(destination)
                            try:
                                relative = destination_path.relative_to(root).as_posix()
                            except ValueError:
                                relative = ""
                            if relative not in replacement_targets:
                                return original_replace(source, destination)
                            calls["count"] += 1
                            if calls["count"] == failure_at:
                                if timing == "after":
                                    original_replace(source, destination)
                                raise OSError("injected replacement boundary failure")
                            return original_replace(source, destination)

                        with patch.object(transaction.os, "replace", side_effect=fail_at_boundary):
                            with self.assertRaisesRegex(OSError, "replacement boundary"):
                                commit_host_files(root, changes, generation="a" * 32,
                                                  retain_backup=True)
                        self._assert_old_generation(root)

    def test_failure_removing_commit_journal_rolls_back_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "host"
            root.mkdir()
            target = root / "skill.md"
            target.write_bytes(b"old")
            original_unlink = Path.unlink
            failed = {"once": False}

            def fail_journal_removal(path, *args, **kwargs):
                if path.name == HOST_JOURNAL and not failed["once"]:
                    failed["once"] = True
                    raise OSError("injected journal removal failure")
                return original_unlink(path, *args, **kwargs)

            with patch.object(Path, "unlink", autospec=True, side_effect=fail_journal_removal):
                with self.assertRaisesRegex(OSError, "journal removal"):
                    commit_host_files(root, {"skill.md": b"new"}, generation="b" * 32,
                                      retain_backup=True)
            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse((root / HOST_JOURNAL).exists())
            self.assertFalse((root / (STAGE_PREFIX + "b" * 32)).exists())
            self.assertFalse((root / ".kstack-generations" / ("b" * 32)).exists())

    def test_interruption_after_journal_commit_is_recovered_on_next_call(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "host"
            root.mkdir()
            target = root / "skill.md"
            target.write_bytes(b"old")
            original_replace = transaction.os.replace

            def interrupt_after_journal(source, destination):
                if Path(destination).name == HOST_JOURNAL:
                    original_replace(source, destination)
                    raise OSError("interruption after journal commit")
                return original_replace(source, destination)

            with patch.object(transaction.os, "replace", side_effect=interrupt_after_journal):
                with self.assertRaisesRegex(OSError, "after journal commit"):
                    commit_host_files(root, {"skill.md": b"new"}, generation="c" * 32,
                                      retain_backup=True)
            self.assertTrue((root / HOST_JOURNAL).exists())
            self.assertEqual(target.read_bytes(), b"old")

            recovered = recover_host_files(root)
            self.assertTrue(recovered["recovered"])
            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse((root / HOST_JOURNAL).exists())
            self.assertFalse((root / (STAGE_PREFIX + "c" * 32)).exists())
            self.assertFalse((root / ".kstack-generations" / ("c" * 32)).exists())

    def test_staging_backup_and_new_file_failures_leave_host_unchanged(self):
        for area in ("backup", "new"):
            for timing in ("before", "after"):
                with self.subTest(area=area, timing=timing):
                    with tempfile.TemporaryDirectory() as directory:
                        root = Path(directory) / "host"
                        self._initial_host(root)
                        stage = root / (STAGE_PREFIX + "d" * 32)
                        original_write = transaction._write_staged
                        failed = {"once": False}

                        def fail_staging_write(path, data):
                            selected = (Path(path) == stage / area / "skills/a.txt")
                            if selected and not failed["once"]:
                                failed["once"] = True
                                if timing == "after":
                                    original_write(path, data)
                                raise OSError("injected staging write failure")
                            return original_write(path, data)

                        with patch.object(transaction, "_write_staged", side_effect=fail_staging_write):
                            with self.assertRaisesRegex(OSError, "staging write"):
                                commit_host_files(root, {"skills/a.txt": b"new-a"},
                                                  generation="d" * 32, retain_backup=True)
                        self.assertTrue(failed["once"])
                        self.assertEqual((root / "skills/a.txt").read_bytes(), b"old-a")
                        self.assertFalse((root / HOST_JOURNAL).exists())
                        self.assertFalse(stage.exists())
                        self.assertFalse((root / ".kstack-generations" / ("d" * 32)).exists())


if __name__ == "__main__":
    unittest.main()
