"""Crash-recoverable updates for KStack's related JSON state documents.

A write-ahead undo journal records old values before touching multiple files.
A recovered interrupted operation rolls back to its previous generation. Call
under state.lock_state; this is NOT a distributed transaction or a security
boundary against an attacker who can rewrite local state.
"""
from __future__ import annotations

import os
import hashlib
import json
import re
import shutil
import stat
import tempfile
import uuid
import unicodedata
from pathlib import Path
from .state import file_lock, read_json, write_json
from .security import is_link_or_junction, is_safe_relative_path

JOURNAL = "pending-transaction.json"
HOST_JOURNAL = ".kstack-host-transaction.json"
STAGE_PREFIX = ".kstack-stage-"


def host_lock(root: Path):
    """Serialize KStack mutations to one host skill directory."""
    return file_lock(Path(root) / ".kstack-host.lock")


def host_transaction_pending(root: Path) -> bool:
    path = Path(root) / HOST_JOURNAL
    if path.is_symlink():
        raise ValueError("Refusing symlink host transaction journal")
    return path.exists()


def _sync_directory(path: Path) -> None:
    if os.name != "posix":
        return
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        # Some filesystems do not support directory fsync. File contents and
        # atomic replacement are still used; this limitation is platform-specific.
        pass


def _host_path_key(relative: str) -> str:
    """Conservative portable name comparison for case/Unicode collisions."""
    if not isinstance(relative, str):
        raise ValueError("Invalid relative host path")
    return unicodedata.normalize("NFC", relative).casefold()


def _safe_host_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str):
        raise ValueError("Invalid relative path in host transaction")
    parts = relative.split("/")
    if not is_safe_relative_path(relative):
        raise ValueError("Invalid relative path in host transaction")
    path = root.joinpath(*parts)
    current = path
    while current != root and current != current.parent:
        if is_link_or_junction(current):
            raise ValueError(f"Symlink in host transaction path: {current}")
        current = current.parent
    return path


def _sha_file(path: Path) -> str | None:
    if is_link_or_junction(path):
        raise ValueError(f"Host transaction target cannot be a symlink: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Host transaction target is not an ordinary file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_staged(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _save_host_generation(root: Path, token: str, stage: Path, entries: list[dict]) -> Path:
    generations = root / ".kstack-generations"
    if is_link_or_junction(generations):
        raise ValueError("Host generation directory cannot be a symlink")
    generations.mkdir(mode=0o700, exist_ok=True)
    snapshot = generations / token
    if snapshot.exists() or is_link_or_junction(snapshot):
        raise ValueError("Host generation identifier already exists")
    snapshot.mkdir(mode=0o700)
    try:
        for entry in entries:
            if entry["old_sha256"] is None:
                continue
            source = _safe_host_path(stage, "backup/" + entry["path"])
            if _sha_file(source) != entry["old_sha256"]:
                raise ValueError("Host transaction backup changed before generation snapshot")
            target = _safe_host_path(snapshot, "backup/" + entry["path"])
            _write_staged(target, source.read_bytes())
        write_json(snapshot / "generation.json", {
            "format": 1, "generation": token, "entries": entries,
        })
        _sync_directory(snapshot)
        _sync_directory(generations)
        return snapshot
    except BaseException:
        shutil.rmtree(snapshot, ignore_errors=True)
        raise


def commit_host_files(root: Path, changes: dict[str, bytes | str | None], *,
                      generation: str | None = None, retain_backup: bool = False) -> dict:
    """Apply a multi-file host generation with an undo journal.

    Files are staged and fsynced first. The journal records verified prior and
    next hashes before the first replacement. A later installer invocation can
    recover a process interruption to the complete old generation.
    """
    root = Path(root)
    if is_link_or_junction(root):
        raise ValueError("Host skill directory cannot be a symlink")
    names = [_host_path_key(path) for path in changes]
    if len(names) != len(set(names)):
        raise ValueError("Case-insensitive or Unicode-normalised host path collision")
    root.mkdir(parents=True, exist_ok=True)
    journal = root / HOST_JOURNAL
    if is_link_or_junction(journal) or journal.exists():
        raise ValueError("Interrupted host transaction exists; recover before writing")
    token = generation or uuid.uuid4().hex
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise ValueError("Invalid host generation identifier")
    stage = root / (STAGE_PREFIX + token)
    stage.mkdir(mode=0o700)
    backup_root = stage / "backup"
    new_root = stage / "new"
    entries = []
    try:
        for relative, raw in sorted(changes.items()):
            target = _safe_host_path(root, relative)
            old_hash = _sha_file(target)
            old_mode = stat.S_IMODE(target.stat().st_mode) if old_hash is not None else None
            if raw is None:
                new_data = None
                new_hash = None
            else:
                if not isinstance(raw, (str, bytes, bytearray)):
                    raise ValueError("Host transaction content must be text, bytes or a deletion")
                new_data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
                new_hash = hashlib.sha256(new_data).hexdigest()
            if old_hash == new_hash:
                continue
            if old_hash is not None:
                _write_staged(backup_root / relative, target.read_bytes())
            if new_data is not None:
                _write_staged(new_root / relative, new_data)
            entries.append({"path": relative, "old_sha256": old_hash, "old_mode": old_mode,
                            "new_sha256": new_hash})
        if not entries:
            shutil.rmtree(stage)
            return {"committed": False, "files_changed": 0, "generation": token}
        # Detect an external edit between backup and journal creation.
        for entry in entries:
            if _sha_file(_safe_host_path(root, entry["path"])) != entry["old_sha256"]:
                raise ValueError("Host file changed during transaction preflight; retry after review")
        generation_snapshot = _save_host_generation(root, token, stage, entries) if retain_backup else None
        write_json(journal, {"format": 1, "stage": stage.name, "entries": entries,
                             "generation": token if retain_backup else None})
        _sync_directory(root)
        try:
            # Managed manifests are commit markers and are always written last.
            ordered = sorted(entries, key=lambda entry: (
                entry["path"].startswith(".kstack-") and entry["path"].endswith(".json"),
                entry["path"]))
            for entry in ordered:
                target = _safe_host_path(root, entry["path"])
                if _sha_file(target) != entry["old_sha256"]:
                    raise ValueError(f"Host file changed during commit: {entry['path']}")
                if entry["new_sha256"] is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    staged = new_root / entry["path"]
                    os.replace(staged, target)
                    _sync_directory(target.parent)
            journal.unlink()
            _sync_directory(root)
        except BaseException:
            recover_host_files(root)
            raise
        shutil.rmtree(stage)
        _sync_directory(root)
        return {"committed": True, "files_changed": len(entries), "generation": token}
    except BaseException:
        if not journal.exists() and stage.exists():
            shutil.rmtree(stage, ignore_errors=True)
        if not journal.exists() and retain_backup:
            snapshot = root / ".kstack-generations" / token
            if snapshot.is_dir() and not snapshot.is_symlink():
                shutil.rmtree(snapshot, ignore_errors=True)
        raise


def recover_host_files(root: Path) -> dict:
    """Roll an interrupted host generation back after validating every path/hash."""
    root = Path(root)
    journal = root / HOST_JOURNAL
    if is_link_or_junction(journal):
        raise ValueError("Refusing symlink host transaction journal")
    if not journal.exists():
        return {"recovered": False}
    record = read_json(journal, {})
    if (not isinstance(record, dict) or record.get("format") != 1
            or set(record) not in ({"format", "stage", "entries"}, {"format", "stage", "entries", "generation"})):
        raise ValueError("Invalid host transaction journal; manual recovery required")
    stage_name = record["stage"]
    if not isinstance(stage_name, str) or not re.fullmatch(re.escape(STAGE_PREFIX) + r"[a-f0-9]{32}", stage_name):
        raise ValueError("Invalid host transaction staging path")
    stage = root / stage_name
    if is_link_or_junction(stage) or not stage.is_dir() or not isinstance(record["entries"], list):
        raise ValueError("Missing or invalid host transaction staging directory")
    generation = record.get("generation")
    if generation is not None and (
            not isinstance(generation, str) or not re.fullmatch(r"[a-f0-9]{32}", generation)
            or generation != stage_name[len(STAGE_PREFIX):]):
        raise ValueError("Invalid interrupted host generation identifier")
    entries = record["entries"]
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "old_sha256", "old_mode", "new_sha256"}:
            raise ValueError("Invalid host transaction entry")
        relative = entry["path"]
        if (not isinstance(relative, str)
                or any(value is not None and (not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value))
                       for value in (entry["old_sha256"], entry["new_sha256"]))
                or (entry["old_mode"] is not None and
                    (type(entry["old_mode"]) is not int or not 0 <= entry["old_mode"] <= 0o7777))):
            raise ValueError("Invalid host transaction hash or mode")
        if relative in seen:
            raise ValueError("Duplicate host transaction path")
        seen.add(relative)
        target = _safe_host_path(root, relative)
        current = _sha_file(target)
        if current not in (entry["old_sha256"], entry["new_sha256"]):
            raise ValueError(f"Host file changed after interruption; manual recovery required: {relative}")
        old_hash = entry["old_sha256"]
        if old_hash is None:
            if current is not None:
                target.unlink()
        elif current != old_hash:
            backup = _safe_host_path(stage, "backup/" + relative)
            if _sha_file(backup) != old_hash:
                raise ValueError(f"Host transaction backup is missing or corrupt: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix=".kstack-recover-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(backup.read_bytes())
                    stream.flush()
                    os.fsync(stream.fileno())
                if entry["old_mode"] is not None:
                    os.chmod(temporary, entry["old_mode"])
                os.replace(temporary, target)
                _sync_directory(target.parent)
            finally:
                if os.path.lexists(temporary):
                    os.unlink(temporary)
    journal.unlink()
    _sync_directory(root)
    shutil.rmtree(stage)
    if generation is not None:
        snapshot = _safe_host_path(root, ".kstack-generations/" + generation)
        if is_link_or_junction(snapshot):
            raise ValueError("Refusing symlink interrupted host generation")
        if snapshot.exists():
            shutil.rmtree(snapshot)
    return {"recovered": True, "files_restored": len(entries)}


def recover(state: Path) -> dict:
    journal = state / JOURNAL
    if journal.is_symlink():
        raise ValueError("Refusing symlink transaction journal")
    if not journal.exists():
        return {"recovered": False}
    record = read_json(journal, {})
    if not isinstance(record, dict) or set(record) != {"active", "history", "snapshot", "snapshot_before", "snapshot_existed"}:
        raise ValueError("Invalid transaction journal; manual recovery required")
    version = record["snapshot"]
    if type(version) is not int or version < 1 or version > 1_000_000:
        raise ValueError("Invalid snapshot version in journal")
    path = state / "snapshots" / f"{version:06d}.json"
    if path.is_symlink():
        raise ValueError("Refusing symlink snapshot")
    if record["snapshot_existed"]:
        write_json(path, record["snapshot_before"])
    else:
        path.unlink(missing_ok=True)
    write_json(state / "active.json", record["active"])
    write_json(state / "history.json", record["history"])
    journal.unlink()
    return {"recovered": True, "rolled_back_generation": version}


def commit_generation(state: Path, next_active: dict, next_history: list, version: int,
                      snapshot_payload: dict) -> None:
    if not isinstance(next_active, dict) or not isinstance(next_history, list):
        raise ValueError("Invalid generation data")
    if version < 1 or version != len(next_history):
        raise ValueError("Generation version inconsistent with history")
    pending = state / JOURNAL
    if pending.exists() or pending.is_symlink():
        raise ValueError("Interrupted transaction exists; recover before writing")
    snapshot = state / "snapshots" / f"{version:06d}.json"
    if snapshot.is_symlink():
        raise ValueError("Refusing symlink snapshot")
    snapshot_existed = snapshot.exists()
    if snapshot_existed:
        raise ValueError("Snapshot generation already exists; refusing overwrite")
    record = {"active": read_json(state / "active.json", {}),
              "history": read_json(state / "history.json", []),
              "snapshot": version, "snapshot_before": None,
              "snapshot_existed": False}
    write_json(pending, record)
    try:
        write_json(snapshot, snapshot_payload)
        write_json(state / "active.json", next_active)
        write_json(state / "history.json", next_history)
    except Exception:
        recover(state)
        raise
    pending.unlink()
