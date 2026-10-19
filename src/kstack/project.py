"""Read-only project detection and conservative project onboarding."""
from __future__ import annotations

import json
from pathlib import Path

from .state import read_json, write_json

SIGNALS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "python"), ("requirements.txt", "python"),
    ("Cargo.toml", "rust"), ("Package.swift", "swift"),
    ("pubspec.yaml", "flutter"), ("package.json", "node"),
    ("next.config.js", "nextjs"), ("next.config.mjs", "nextjs"),
    ("next.config.ts", "nextjs"), ("vite.config.ts", "vite"),
    ("vite.config.js", "vite"), ("app.json", "expo"),
)


def inspect_project(project: Path) -> dict:
    """Read small, known manifests without executing the project or following arbitrary links."""
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError("Project directory does not exist")
    technologies: set[str] = set()
    signals: list[str] = []
    for name, label in SIGNALS:
        file = project / name
        if file.is_file() and not file.is_symlink():
            technologies.add(label)
            signals.append(name)
    if any(project.glob("*.sln")) or any(project.glob("*.csproj")):
        technologies.add("dotnet")
        signals.append("*.sln / *.csproj")
    if any(project.glob("*.xcodeproj")) or any(project.glob("*.xcworkspace")):
        technologies.add("swift")
        signals.append("Xcode project")
    if (project / "src-tauri" / "tauri.conf.json").is_file():
        technologies.add("tauri")
        signals.append("src-tauri/tauri.conf.json")
    package_file = project / "package.json"
    if package_file.is_file() and not package_file.is_symlink() and package_file.stat().st_size <= 200_000:
        try:
            package = json.loads(package_file.read_text(encoding="utf-8"))
            deps = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            for dep, label in (("react", "react"), ("next", "nextjs"), ("@tiptap/core", "tiptap"),
                               ("@playwright/test", "playwright"), ("expo", "expo"), ("typescript", "typescript")):
                if dep in deps:
                    technologies.add(label)
            if not isinstance(package.get("scripts", {}), dict):
                raise ValueError("Invalid scripts section")
        except (json.JSONDecodeError, UnicodeError, ValueError, TypeError):
            signals.append("package.json (unreadable or invalid)")
    if (project / "tests").is_dir():
        signals.append("tests/")
    if (project / "AGENTS.md").is_file():
        signals.append("AGENTS.md")
    if (project / "CLAUDE.md").is_file():
        signals.append("CLAUDE.md")
    if {"nextjs", "vite", "react", "tiptap"} & technologies:
        profile = "web"
    elif {"tauri", "dotnet", "swift"} & technologies:
        profile = "native-desktop"
    elif {"flutter", "expo"} & technologies:
        profile = "mobile"
    elif "python" in technologies:
        profile = "python"
    else:
        profile = "general"
    return {"project": str(project), "profile": profile, "technologies": sorted(technologies),
            "signals": sorted(set(signals)), "configured": (project / "kstack.json").is_file()}


def load_project_config(project: Path) -> dict:
    path = project / "kstack.json"
    config = read_json(path, {})
    if not isinstance(config, dict):
        raise ValueError("kstack.json must contain a JSON object")
    allowed = {"version", "profile", "skill_preferences", "verification_commands", "delivery"}
    if set(config) - allowed:
        raise ValueError("Unknown KStack configuration keys: " + ", ".join(sorted(set(config) - allowed)))
    if config.get("version", 1) != 1:
        raise ValueError("Unsupported project configuration version")
    if "skill_preferences" in config and (not isinstance(config["skill_preferences"], list)
            or any(not isinstance(v, str) for v in config["skill_preferences"])):
        raise ValueError("skill_preferences must be a list of skill names")
    commands = config.get("verification_commands", [])
    if not isinstance(commands, list) or any(not isinstance(c, list) or not c
                                              or any(not isinstance(a, str) or not a for a in c) for c in commands):
        raise ValueError("verification_commands must be lists of nonempty arguments")
    if len(commands) > 30 or any(len(c) > 25 for c in commands):
        raise ValueError("Too many verification commands or arguments")
    return config


def bootstrap(project: Path, dry_run: bool = True) -> dict:
    facts = inspect_project(project)
    folder = Path(facts["project"])
    path = folder / "kstack.json"
    if path.exists() or path.is_symlink():
        return {**facts, "action": "unchanged", "reason": "existing configuration preserved"}
    payload = {"version": 1, "profile": facts["profile"], "skill_preferences": [],
               "verification_commands": [], "delivery": {"verify_before_merge": True}}
    if not dry_run:
        write_json(path, payload)
    return {**facts, "action": "would-create" if dry_run else "created", "configuration": payload}
