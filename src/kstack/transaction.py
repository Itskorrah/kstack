"""Crash-recoverable updates for KStack's related JSON state documents.

A write-ahead undo journal records old values before touching multiple files.
A recovered interrupted operation rolls back to its previous generation. Call
under state.lock_state; this is NOT a distributed transaction or a security
boundary against an attacker who can rewrite local state.
"""
from __future__ import annotations

import os
from pathlib import Path
from .state import read_json, write_json

JOURNAL = "pending-transaction.json"


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
