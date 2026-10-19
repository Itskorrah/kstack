"""Local state with atomic updates and strict file ownership."""
from __future__ import annotations

import json
import os
import socket
import tempfile
import time
from pathlib import Path
from .security import is_link_or_junction


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_link_or_junction(path):
        raise ValueError(f"Refusing symlink output: {path}")
    fd, tmp = tempfile.mkstemp(prefix=".kstack-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def app_state(path: str | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else Path.home() / ".kstack"


from contextlib import contextmanager
from datetime import datetime, timezone
import errno


def _read_lock_record(lock: Path) -> dict:
    try:
        value = json.loads(lock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _acquire_os_lock(fd: int, *, nonblocking: bool = True) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_END)
        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
            os.fsync(fd)
        os.lseek(fd, 0, os.SEEK_SET)
        mode = msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK
        try:
            msvcrt.locking(fd, mode, 1)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK, errno.EPERM):
                raise BlockingIOError from exc
            raise
    else:
        import fcntl
        mode = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        try:
            fcntl.flock(fd, mode)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise BlockingIOError from exc
            raise


def _release_os_lock(fd: int) -> None:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)


def _write_lock_record(fd: int, value: dict) -> None:
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    os.write(fd, payload)
    os.fsync(fd)


@contextmanager
def file_lock(lock: Path):
    """Hold a cross-process advisory lock with inspectable process ownership.

    OS file locks are released by the kernel when a process exits, so an
    interrupted process cannot leave a directory lock that blocks all future
    writes. The JSON bytes in the persistent lock file are diagnostic metadata;
    the kernel lock, not that record, decides whether the resource is locked.
    """
    lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if is_link_or_junction(lock):
        raise ValueError(f"Lock path cannot be a symlink: {lock}")
    flags = os.O_RDWR | os.O_CREAT
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(lock, flags, 0o600)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ValueError(f"Lock path cannot be a symlink: {lock}") from exc
        raise
    acquired = False
    try:
        try:
            _acquire_os_lock(fd)
            acquired = True
        except BlockingIOError as exc:
            owner = _read_lock_record(lock)
            detail = ""
            if isinstance(owner.get("pid"), int):
                detail = f" (pid {owner['pid']} on {owner.get('hostname', 'unknown host')})"
            raise ValueError(f"KStack state is locked{detail}; inspect the lock owner before retrying") from exc
        if os.fstat(fd).st_size:
            owner = _read_lock_record(lock)
            if not {"pid", "hostname", "started_at", "locked"} <= set(owner) or type(owner.get("pid")) is not int:
                raise ValueError(f"Refusing to overwrite an unowned lock file: {lock}")
        owner = {"pid": os.getpid(), "hostname": socket.gethostname(),
                 "started_at": datetime.now(timezone.utc).isoformat(), "locked": True}
        _write_lock_record(fd, owner)
        try:
            yield owner
        finally:
            owner["locked"] = False
            owner["released_at"] = datetime.now(timezone.utc).isoformat()
            _write_lock_record(fd, owner)
    finally:
        if acquired:
            _release_os_lock(fd)
        os.close(fd)


def lock_state(path: Path):
    """Prevent concurrent KStack state mutations with an OS-released lock."""
    legacy = path / ".write-lock"
    if legacy.exists() or is_link_or_junction(legacy):
        status = _legacy_lock_status(legacy)
        owner_pid = status.get("owner", {}).get("pid")
        raise ValueError(f"Legacy state lock exists; run lock-status and recover-lock --owner-pid {owner_pid or '<pid>'} after confirming its process stopped")
    return file_lock(path / ".kstack-write.lock")


def _process_alive(pid: int) -> bool | None:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def _legacy_lock_status(lock: Path) -> dict:
    if not lock.is_dir() or is_link_or_junction(lock):
        return {"locked": False, "owner": None, "stale_owner": False, "legacy": True,
                "error": "Legacy lock is not an ordinary directory"}
    owner_file = lock / "owner.json"
    if is_link_or_junction(owner_file) or not owner_file.is_file():
        return {"locked": False, "owner": None, "stale_owner": False, "legacy": True,
                "error": "Legacy lock owner record is missing or invalid"}
    owner = _read_lock_record(owner_file)
    pid = owner.get("pid")
    alive = _process_alive(pid) if type(pid) is int else None
    return {"locked": alive is not False, "owner": owner or None,
            "stale_owner": alive is False, "legacy": True}


def lock_status(path: Path) -> dict:
    legacy = path / ".write-lock"
    if legacy.exists() or is_link_or_junction(legacy):
        return _legacy_lock_status(legacy)
    lock = path / ".kstack-write.lock"
    if not lock.exists():
        return {"locked": False, "owner": None, "stale_owner": False}
    if is_link_or_junction(lock) or not lock.is_file():
        raise ValueError("State lock path is not an ordinary file")
    fd = os.open(lock, os.O_RDWR | (getattr(os, "O_NOFOLLOW", 0)))
    acquired = False
    try:
        try:
            _acquire_os_lock(fd)
            acquired = True
        except BlockingIOError:
            return {"locked": True, "owner": _read_lock_record(lock), "stale_owner": False}
        owner = _read_lock_record(lock)
        same_host = owner.get("hostname") == socket.gethostname()
        pid = owner.get("pid")
        alive = _process_alive(pid) if type(pid) is int and same_host else None
        return {"locked": False, "owner": owner or None,
                "stale_owner": bool(owner.get("locked") is True and same_host and alive is False)}
    finally:
        if acquired:
            _release_os_lock(fd)
        os.close(fd)


def recover_stale_lock(path: Path, expected_pid: int) -> dict:
    """Clear stale owner metadata only after the kernel lock and PID are checked."""
    legacy = path / ".write-lock"
    if legacy.exists() or is_link_or_junction(legacy):
        status = _legacy_lock_status(legacy)
        if type(expected_pid) is not int or status.get("owner", {}).get("pid") != expected_pid:
            raise ValueError("Owner PID does not match the recorded legacy state lock")
        if not status.get("stale_owner"):
            raise ValueError("Legacy lock owner is alive or its process state cannot be verified")
        owner_file = legacy / "owner.json"
        if set(item.name for item in legacy.iterdir()) != {"owner.json"} or is_link_or_junction(owner_file):
            raise ValueError("Legacy lock directory contains unexpected content; manual inspection required")
        owner_file.unlink()
        legacy.rmdir()
        return {"recovered": True, "owner_pid": expected_pid, "legacy": True}
    lock = path / ".kstack-write.lock"
    if is_link_or_junction(lock) or not lock.is_file():
        raise ValueError("An ordinary state lock file is required")
    fd = os.open(lock, os.O_RDWR | (getattr(os, "O_NOFOLLOW", 0)))
    acquired = False
    try:
        try:
            _acquire_os_lock(fd)
            acquired = True
        except BlockingIOError as exc:
            owner = _read_lock_record(lock)
            raise ValueError(f"State lock is still held by pid {owner.get('pid', 'unknown')}") from exc
        owner = _read_lock_record(lock)
        if type(expected_pid) is not int or owner.get("pid") != expected_pid:
            raise ValueError("Owner PID does not match the recorded state lock")
        if owner.get("locked") is not True:
            raise ValueError("State lock record is already released; no recovery is needed")
        if owner.get("hostname") != socket.gethostname():
            raise ValueError("Cannot verify a state lock owner from another host")
        alive = _process_alive(expected_pid)
        if alive is not False:
            raise ValueError("Recorded lock owner is alive or its process state cannot be verified")
        recovered = dict(owner)
        recovered.update({"locked": False, "recovered_at": datetime.now(timezone.utc).isoformat()})
        _write_lock_record(fd, recovered)
        return {"recovered": True, "owner_pid": expected_pid, "hostname": socket.gethostname()}
    finally:
        if acquired:
            _release_os_lock(fd)
        os.close(fd)
