"""Risk- and capability-aware deterministic routing. Never claims to invoke a host."""
from __future__ import annotations

import json
import re
from pathlib import Path
from .installer import available_skills, bundled_skills, skill_dir, _assert_no_symlink_ancestors
from .state import read_json
from .project import inspect_project, load_project_config
from .security import digest

ROUTES = {
    "kstack-router": ("develop", "improve", "refactor", "implement", "repo", "build", "feature", "design", "fix"),
    "kstack-audit": ("audit", "investigate", "architect", "security", "risk", "analyse", "review"),
    "kstack-verify": ("test", "verify", "regression", "browser", "bug", "perf", "benchmark", "validate"),
    "kstack-ship": ("ship", "release", "merge", "pull request", "push", "publish", "commit"),
}
SPECIALISTS = {
    "evolve": {"signals": ("improve", "refactor", "modernise", "audit", "entire", "comprehensive"), "profiles": (), "capabilities": ("orchestration.evolve",)},
    "ui-skills": {"signals": ("ui", "design", "visual", "layout", "accessibility", "frontend"), "profiles": ("web",), "capabilities": ("ui.design", "ui.accessibility")},
    "pstack": {"signals": ("architecture", "architect", "security", "review", "design", "blast radius",
                            "authentication", "authorization", "permissions", "secret", "secrets",
                            "database", "migration"), "profiles": (), "capabilities": ("architecture.review",)},
    "superpowers": {"signals": ("debug", "bug", "tdd", "test"), "profiles": (), "capabilities": ("engineering.tdd", "engineering.debugging")},
    "vercel-react": {"signals": ("react", "nextjs", "performance", "frontend"), "profiles": ("web",), "capabilities": ("react.performance",)},
    "breakswarm": {"signals": ("browser", "e2e", "end to end", "ui testing"), "profiles": (), "capabilities": ("testing.browser",)},
    "sessionbridge": {"signals": ("handoff", "resume", "switch agent", "context"), "profiles": (), "capabilities": ("orchestration.handoff",)},
    "replica": {"signals": ("clone", "replicate", "competitor", "reverse engineer"), "profiles": (), "capabilities": ("research.replication",)},
    "motionforge": {"signals": ("video", "motion", "animate"), "profiles": (), "capabilities": ("creative.motion",)},
}


def _matches(text: str, pattern: str) -> bool:
    return bool(re.search(r"(?<!\w)" + re.escape(pattern) + r"(?!\w)", text))


def _external_inventory(project: Path | None, host: str | None, scope: str) -> tuple[list[dict], list[dict]]:
    from .external import list_external
    hosts = [host] if host else ["codex", "claude"]
    scopes = []
    if scope in ("both", "project") and project is not None:
        scopes.append(("project", project))
    if scope in ("both", "global"):
        scopes.append(("global", None))
    if scope == "project" and project is None:
        raise ValueError("A project path is required to inspect project-scoped skills")
    installed, problems = [], []
    for selected_host in hosts:
        for selected_scope, folder in scopes:
            try:
                result = list_external(selected_host, selected_scope, folder)
            except (OSError, ValueError, KeyError) as exc:
                problems.append({"host": selected_host, "scope": selected_scope, "error": str(exc)})
                continue
            for item in result.get("packages", []):
                if item.get("status") != "installed":
                    problems.append({"host": selected_host, "scope": selected_scope,
                                     "skill": item.get("name"), "status": item.get("status")})
                    continue
                installed.append({**item, "host": selected_host, "scope": selected_scope,
                                  "host_verified": False})
            if not result.get("ok") and not result.get("packages"):
                problems.append({"host": selected_host, "scope": selected_scope,
                                 "error": result.get("error", "External skill manifest is not valid")})
    return installed, problems


def _bundled_install_locations(root: Path, state: Path, selected: list[str], project: Path | None,
                               host: str | None, scope: str) -> tuple[dict[str, list[str]], list[dict]]:
    hosts = [host] if host else ["codex", "claude"]
    scopes = []
    if scope in ("both", "project") and project is not None:
        scopes.append(("project", project))
    if scope in ("both", "global"):
        scopes.append(("global", None))
    if scope == "project" and project is None:
        raise ValueError("A project path is required to inspect project-scoped skills")
    contents = bundled_skills(root)
    locations = {name: [] for name in selected}
    problems = []
    for selected_host in hosts:
        for selected_scope, folder in scopes:
            directory = skill_dir(selected_host, selected_scope, folder)
            manifest_path = directory / ".kstack-managed.json"
            if not manifest_path.exists():
                continue
            try:
                _assert_no_symlink_ancestors(manifest_path)
                manifest = read_json(manifest_path, {})
                files = manifest.get("files", {}) if isinstance(manifest, dict) else None
                if not isinstance(files, dict):
                    raise ValueError("Invalid KStack host manifest")
                for name in selected:
                    expected = contents.get(name)
                    relative = name + "/SKILL.md"
                    if expected is None or relative not in files:
                        continue
                    path = directory / relative
                    _assert_no_symlink_ancestors(path)
                    if path.is_file() and digest(path.read_text(encoding="utf-8")) == digest(expected):
                        locations[name].append(selected_host + ":" + selected_scope)
                    else:
                        problems.append({"host": selected_host, "scope": selected_scope,
                                         "skill": name, "status": "installed_file_mismatch"})
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                problems.append({"host": selected_host, "scope": selected_scope, "error": str(exc)})
    return locations, problems


def route(task: str, root: Path, state: Path, profile: str = "general", project: Path | None = None,
          host: str | None = None, scope: str = "both") -> dict:
    if not task.strip():
        raise ValueError("Task cannot be empty")
    if host not in (None, "codex", "claude") or scope not in ("both", "global", "project"):
        raise ValueError("External skill search supports codex|claude and both|global|project scopes")
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
    external_installed, external_issues = _external_inventory(project, host, scope)
    installed_capabilities = {capability for item in external_installed for capability in item.get("provides", [])}
    suggested = []
    for entry in integrations:
        sid = entry.get("id")
        candidate = SPECIALISTS.get(sid)
        if not candidate:
            continue
        signal_fit = sum(2 for keyword in candidate["signals"] if _matches(text, keyword))
        if signal_fit == 0:
            continue
        # A project profile may refine a task match, but must not create one.
        relevance = signal_fit
        relevance += 1 if chosen_profile in candidate["profiles"] else 0
        if sid in project_config.get("skill_preferences", []):
            relevance += 3
        if relevance == 0:
            continue
        # One primary coordinator, no second competing coordinator.
        if sid == "superpowers" and any(x["id"] == "evolve" for x in suggested):
            relevance = max(1, relevance - 2)
        required = set(candidate.get("capabilities", ()))
        matches = [item for item in external_installed
                   if item["name"] == sid or bool(required.intersection(item.get("provides", [])))]
        suggested.append({"id": sid, "fit": relevance,
                          "status": "installed-files-unverified" if matches else "candidate-only",
                          "reason": entry.get("role", "specialist"), "host_verified": False,
                          "installed_skills": sorted({item["name"] for item in matches}),
                          "installed_locations": sorted({item["host"] + ":" + item["scope"] for item in matches}),
                          "available_capabilities": sorted(required.intersection(installed_capabilities))})
    suggested.sort(key=lambda x: (-x["fit"], x["id"]))
    if tiny and not high_risk:
        suggested = suggested[:2]
    else:
        suggested = suggested[:4]
    bundled_locations, bundled_issues = _bundled_install_locations(root, state, selected, project, host, scope)
    workflow_suggestions = [{"name": name,
                             "status": "installed-files-unverified" if bundled_locations.get(name) else "available-not-installed",
                             "installed_locations": sorted(bundled_locations.get(name, [])),
                             "host_verified": False}
                            for name in selected]
    return {"task": task, "profile": chosen_profile, "project": facts,
            "complexity": "low" if tiny and not high_risk else "substantial",
            "risk": "elevated" if high_risk else "ordinary",
            "workflow_suggestions": workflow_suggestions,
            "external_candidates": suggested,
            "external_skill_inventory": external_installed,
            "external_skill_inventory_issues": external_issues + bundled_issues,
            "conditional_guidance": advice,
            "verification": "required" if high_risk or not tiny else "proportionate",
            "note": "External candidates are NOT installed or invoked; verify host availability separately."}
