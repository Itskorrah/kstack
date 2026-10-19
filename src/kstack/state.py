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
