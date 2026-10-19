"""Risk- and capability-aware deterministic routing. Never claims to invoke a host."""
from __future__ import annotations

import json
import re
from pathlib import Path
from .installer import available_skills
from .state import read_json
from .project import inspect_project, load_project_config

ROUTES = {
    "kstack-router": ("develop", "improve", "refactor", "implement", "repo", "build", "feature", "design", "fix"),
    "kstack-audit": ("audit", "investigate", "architect", "security", "risk", "analyse", "review"),
    "kstack-verify": ("test", "verify", "regression", "browser", "bug", "perf", "benchmark", "validate"),
    "kstack-ship": ("ship", "release", "merge", "pull request", "push", "publish", "commit"),
}
SPECIALISTS = {
    "evolve": {"signals": ("improve", "refactor", "modernise", "audit", "entire", "comprehensive"), "profiles": ()},
    "ui-skills": {"signals": ("ui", "design", "visual", "layout", "accessibility", "frontend"), "profiles": ("web",)},
    "pstack": {"signals": ("architecture", "architect", "security", "review", "design", "blast radius"), "profiles": ()},
    "superpowers": {"signals": ("debug", "bug", "tdd", "test"), "profiles": ()},
    "vercel-react": {"signals": ("react", "nextjs", "performance", "frontend"), "profiles": ("web",)},
    "breakswarm": {"signals": ("browser", "e2e", "end to end", "ui testing"), "profiles": ("web",)},
    "sessionbridge": {"signals": ("handoff", "resume", "switch agent", "context"), "profiles": ()},
    "replica": {"signals": ("clone", "replicate", "competitor", "reverse engineer"), "profiles": ()},
    "motionforge": {"signals": ("video", "motion", "animate"), "profiles": ()},
}


def _matches(text: str, pattern: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(pattern) + r"(?!\w)", text))


def route(task: str, root: Path, state: Path, profile: str = "general", project: Path | None = None) -> dict:
    if not task.strip():
        raise ValueError("Task cannot be empty")
    root_profile = root / "profiles"
    if not root_profile.is_dir():
        root_profile = Path(__file__).parent / "bundled" / "profiles"
    facts = inspect_project(project) if project is not None else None
    project_config = load_project_config(Path(facts["project"])) if facts else {}
    chosen_profile = project_config.get("profile", facts["profile"] if facts else profile)
    # Validate profile name BEFORE joining paths.
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,48}", chosen_profile):
        raise ValueError("Invalid profile identifier")
    raw = read_json(root_profile / (chosen_profile + ".json"), None)
    if not isinstance(raw, dict):
        raise ValueError("Unknown project profile")
    text = task.lower()
    tiny = len(task.split()) <= 6 and not any(_matches(text, x) for x in ("comprehensive", "entire", "all", "overhaul", "major"))
    high_risk = any(_matches(text, x) for x in ("auth", "authentication", "security", "secrets", "production",
                    "database", "migration", "payment", "delete", "permissions", "credentials"))
    selected = []
    available = available_skills(root, state)
    for name, triggers in ROUTES.items():
        if name in available and any(_matches(text, word) for word in triggers):
            selected.append(name)
    if high_risk and "kstack-audit" not in selected:
        selected.append("kstack-audit")
    if (not tiny or high_risk) and "kstack-verify" not in selected:
        selected.append("kstack-verify")
    if "kstack-router" not in selected:
        selected.insert(0, "kstack-router")
    advice = [x.get("guidance", "") for x in raw.get("suggestions", [])
              if any(_matches(text, k.lower()) for k in x.get("keywords", []))]
    integration_dir = root / "data" / "integrations.json"
    if not integration_dir.is_file():
        integration_dir = Path(__file__).parent / "bundled" / "data" / "integrations.json"
    integrations = read_json(integration_dir, [])
    suggested = []
    for entry in integrations:
        sid = entry.get("id")
        candidate = SPECIALISTS.get(sid)
        if not candidate:
            continue
        relevance = sum(2 for keyword in candidate["signals"] if _matches(text, keyword))
        relevance += 1 if chosen_profile in candidate["profiles"] else 0
        if sid in project_config.get("skill_preferences", []):
            relevance += 3
        if relevance == 0:
            continue
        # One primary coordinator, no second competing coordinator.
        if sid == "superpowers" and any(x["id"] == "evolve" for x in suggested):
            relevance = max(1, relevance - 2)
        suggested.append({"id": sid, "fit": relevance, "status": "candidate-only",
                          "reason": entry.get("role", "specialist"), "host_verified": False})
    suggested.sort(key=lambda x: (-x["fit"], x["id"]))
    if tiny and not high_risk:
        suggested = suggested[:2]
    else:
        suggested = suggested[:4]
    return {"task": task, "profile": chosen_profile, "project": facts,
            "complexity": "low" if tiny and not high_risk else "substantial",
            "risk": "elevated" if high_risk else "ordinary",
            "installed_skill_suggestions": selected,
            "external_candidates": suggested,
            "conditional_guidance": advice,
            "verification": "required" if high_risk or not tiny else "proportionate",
            "note": "External candidates are NOT installed or invoked; verify host availability separately."}
