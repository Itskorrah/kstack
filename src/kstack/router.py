"""Small deterministic suggestion router; agents still choose skills at runtime."""
from __future__ import annotations

import re
from pathlib import Path
from .installer import available_skills
from .state import read_json

ROUTES = {
    "kstack-router": ("develop", "improve", "refactor", "implement", "repo", "build", "feature"),
    "kstack-audit": ("audit", "investigate", "architect", "security", "risk", "analyse", "review"),
    "kstack-verify": ("test", "verify", "regression", "browser", "bug", "perf", "benchmark", "validate"),
    "kstack-ship": ("ship", "release", "merge", "pull request", "push", "publish", "commit"),
}

def route(task: str, root: Path, state: Path, profile: str = "general") -> dict:
    if not task.strip():
        raise ValueError("Task cannot be empty")
    skills = available_skills(root, state)
    words = set(re.findall(r"[\w-]+", task.lower()))
    selected = []
    for name, triggers in ROUTES.items():
        if name in skills and any((trigger in task.lower() if " " in trigger else trigger in words) for trigger in triggers):
            selected.append(name)
    if not selected:
        selected = ["kstack-router"]
    profiles = read_json(root / "profiles" / (profile + ".json"), None)
    if profiles is None:
        raise ValueError("Unknown project profile")
    advice = [x for x in profiles.get("suggestions", []) if any(k in task.lower() for k in x.get("keywords", []))]
    return {"task": task, "profile": profile, "installed_skill_suggestions": selected,
            "conditional_guidance": [a["guidance"] for a in advice],
            "note": "Routing is a recommendation, not evidence the host loaded a skill."}
