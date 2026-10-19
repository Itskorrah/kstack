"""Privacy-minimal, self-reported development outcomes and conservative trends."""
from __future__ import annotations

from pathlib import Path
from .state import read_json, write_json
from .evidence import append

CATEGORIES = {"correctness", "reliability", "security", "performance", "design", "documentation", "other"}
RESULTS = {"passed", "failed", "blocked", "partially_verified"}


def record(state: Path, item: dict) -> dict:
    if not isinstance(item, dict) or set(item) != {"project_type", "category", "skills", "result", "evidence_note"}:
        raise ValueError("Expected project_type, category, skills, result, evidence_note")
    if not isinstance(item["project_type"], str) or not 2 <= len(item["project_type"]) <= 40:
        raise ValueError("Invalid project type")
    if item["category"] not in CATEGORIES or item["result"] not in RESULTS:
        raise ValueError("Invalid outcome category/result")
    if not isinstance(item["skills"], list) or len(item["skills"]) > 20 or any(not isinstance(s, str) or not s or len(s)>80 for s in item["skills"]):
        raise ValueError("Invalid skill names")
    if not isinstance(item["evidence_note"], str) or not 15 <= len(item["evidence_note"]) <= 2000:
        raise ValueError("Outcome requires a meaningful brief evidence note")
    history = read_json(state / "outcomes.json", [])
    if not isinstance(history, list) or len(history) >= 10_000:
        raise ValueError("Outcome log unavailable or exceeds limit")
    entry = dict(item)
    entry["origin"] = "user-reported-not-independently-verified"
    history.append(entry)
    write_json(state / "outcomes.json", history)
    append(state, "evaluation", {"outcome_number": len(history), "result": item["result"],
                                 "origin": entry["origin"]})
    return {"recorded": len(history), "entry": entry}


def summary(state: Path) -> dict:
    history = read_json(state / "outcomes.json", [])
    if not isinstance(history, list):
        raise ValueError("Invalid outcome log")
    by_skill = {}
    for item in history:
        for skill in set(item.get("skills", [])):
            stats = by_skill.setdefault(skill, {"samples": 0, "passed": 0, "failed": 0, "blocked": 0, "partially_verified": 0})
            stats["samples"] += 1
            if item.get("result") in RESULTS:
                stats[item["result"]] += 1
    # Never infer efficacy from self-reported observations or sparse samples.
    return {"total": len(history), "by_skill": by_skill,
            "interpretation": "Self-reported observations only; no causal skill-effectiveness or model comparison is established."}
