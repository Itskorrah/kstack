"""Read-only maintenance queue and honest prioritisation metadata."""
from __future__ import annotations

from pathlib import Path
from .state import read_json


def queue(state: Path) -> dict:
    candidates = read_json(state / "candidates.json", {})
    active = read_json(state / "active.json", {})
    history = read_json(state / "candidate-revisions.json", {})
    entries = []
    for ident, item in candidates.items():
        current = active.get(ident)
        if current and current.get("commit") == item.get("commit"):
            continue
        status = item.get("status", "unknown")
        if status == "quarantined":
            recommendation = "MANUAL_REVIEW"
        elif status == "assessed":
            recommendation = "EVALUATE_IN_SANDBOX"
        else:
            recommendation = "ASSESS"
        entries.append({"id": ident, "status": status, "commit": item.get("commit"),
                        "recommendation": recommendation, "update": bool(current),
                        "preliminary_score": item.get("preliminary_score"),
                        "blockers": item.get("blockers", []),
                        "revision_count": len(history.get(ident, [])) + 1})
    rank = {"EVALUATE_IN_SANDBOX": 0, "ASSESS": 1, "MANUAL_REVIEW": 2}
    entries.sort(key=lambda r: (rank.get(r["recommendation"], 3), not r["update"], r["id"]))
    return {"pending": len(entries), "items": entries,
            "last_discovery": read_json(state / "last-discovery.json", {}),
            "note": "Recommendations are metadata only. No evaluation or installation is implied."}
