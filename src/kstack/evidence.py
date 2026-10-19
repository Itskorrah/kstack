"""Append-only, locally stored engineering evidence with a tamper-evident chain.

This is not a signed attestation: a person with filesystem write access can replace
an entire journal. It allows honest, consistent records, not proof of identity.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from .state import write_json, read_json


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def append(state: Path, kind: str, detail: dict) -> dict:
    if kind not in {"verification", "routing", "evaluation", "delivery", "maintenance", "incident"}:
        raise ValueError("Unknown evidence event")
    if not isinstance(detail, dict):
        raise ValueError("Event details must be an object")
    path = state / "evidence.json"
    history = read_json(path, [])
    if not isinstance(history, list) or not verify(history)["ok"]:
        raise ValueError("Existing evidence chain is invalid")
    if len(history) >= 10_000:
        raise ValueError("Evidence log limit reached; export and rotate explicitly")
    previous = history[-1]["hash"] if history else "0" * 64
    record = {"sequence": len(history) + 1, "time": dt.datetime.now(dt.timezone.utc).isoformat(),
              "kind": kind, "detail": detail, "previous": previous}
    record["hash"] = hashlib.sha256(canonical(record)).hexdigest()
    history.append(record)
    write_json(path, history)
    return record


def verify(history: list[dict]) -> dict:
    previous = "0" * 64
    for number, record in enumerate(history, 1):
        if not isinstance(record, dict) or record.get("sequence") != number or record.get("previous") != previous:
            return {"ok": False, "record": number, "reason": "sequence/chain mismatch"}
        clean = {k: v for k, v in record.items() if k != "hash"}
        actual = hashlib.sha256(canonical(clean)).hexdigest()
        if actual != record.get("hash"):
            return {"ok": False, "record": number, "reason": "content modified"}
        previous = actual
    return {"ok": True, "records": len(history), "head": previous}


def inspect(state: Path) -> dict:
    history = read_json(state / "evidence.json", [])
    if not isinstance(history, list):
        return {"ok": False, "reason": "invalid journal format"}
    return verify(history)
