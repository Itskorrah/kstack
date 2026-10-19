"""Local state with atomic updates and strict file ownership."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
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

@contextmanager
def lock_state(path: Path):
    """Prevent concurrent KStack mutations using exclusive directory creation.

    A stale lock blocks writes instead of silently replacing another owner's
    lock; recovery requires manual inspection and removal.
    """
    lock = path / ".write-lock"
    path.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or lock.is_symlink():
        raise ValueError("State lock path cannot be a symlink")
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ValueError("KStack state is locked; inspect .write-lock before retrying") from exc
    try:
        (lock / "owner.json").write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
        yield
    finally:
        (lock / "owner.json").unlink(missing_ok=True)
        lock.rmdir()
