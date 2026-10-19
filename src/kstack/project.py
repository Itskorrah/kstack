"""Read-only project detection and conservative project onboarding."""
from __future__ import annotations

import json
import fnmatch
import re
from pathlib import Path

from .state import read_json, write_json
from .security import NAME, is_link_or_junction, is_safe_relative_path

SIGNALS: tuple[tuple[str, str], ...] = (
    ("pyproject.toml", "python"), ("requirements.txt", "python"),
    ("Cargo.toml", "rust"), ("Package.swift", "swift"),
    ("pubspec.yaml", "flutter"), ("package.json", "node"),
    ("next.config.js", "nextjs"), ("next.config.mjs", "nextjs"),
    ("next.config.ts", "nextjs"), ("vite.config.ts", "vite"),
    ("vite.config.js", "vite"), ("app.json", "expo"),
)


SKIP_WORKSPACE_DIRS = {".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build",
                       "target", ".venv", "venv", "coverage", ".next", ".turbo"}


def _profile_for(technologies: set[str]) -> str:
    if {"nextjs", "vite", "react", "tiptap"} & technologies:
        return "web"
    if {"tauri", "dotnet", "swift"} & technologies:
        return "native-desktop"
    if {"flutter", "expo", "react-native"} & technologies:
        return "mobile"
    if "python" in technologies:
        return "python"
    return "general"


def _base_facts(project: Path) -> dict:
    technologies: set[str] = set()
    signals: list[str] = []
    for name, label in SIGNALS:
        file = project / name
        if file.is_file() and not is_link_or_junction(file):
            technologies.add(label)
            signals.append(name)
    if any(p.is_file() and not is_link_or_junction(p) for p in project.glob("*.sln")) or any(
            p.is_file() and not is_link_or_junction(p) for p in project.glob("*.csproj")):
        technologies.add("dotnet")
        signals.append("*.sln / *.csproj")
    if any(p.is_dir() and not is_link_or_junction(p) for p in project.glob("*.xcodeproj")) or any(
            p.is_dir() and not is_link_or_junction(p) for p in project.glob("*.xcworkspace")):
        technologies.add("swift")
        signals.append("Xcode project")
    tauri_config = project / "src-tauri" / "tauri.conf.json"
    if tauri_config.is_file() and not is_link_or_junction(tauri_config):
        technologies.add("tauri")
        signals.append("src-tauri/tauri.conf.json")
    package_file = project / "package.json"
    package_data = {}
    if package_file.is_file() and not is_link_or_junction(package_file) and package_file.stat().st_size <= 200_000:
        try:
            package = json.loads(package_file.read_text(encoding="utf-8"))
            if not isinstance(package, dict):
                raise ValueError("package.json must be an object")
            package_data = package
            dependencies = package.get("dependencies", {})
            dev_dependencies = package.get("devDependencies", {})
            if not isinstance(dependencies, dict) or not isinstance(dev_dependencies, dict):
                raise ValueError("package dependencies must be objects")
            deps = {**dependencies, **dev_dependencies}
            for dep, label in (("react", "react"), ("next", "nextjs"), ("@tiptap/core", "tiptap"),
                               ("@playwright/test", "playwright"), ("expo", "expo"), ("typescript", "typescript")):
                if dep in deps:
                    technologies.add(label)
            if "react-native" in deps:
                technologies.add("react-native")
            if not isinstance(package.get("scripts", {}), dict):
                raise ValueError("Invalid scripts section")
        except (json.JSONDecodeError, UnicodeError, ValueError, TypeError):
            package_data = {}
            signals.append("package.json (unreadable or invalid)")
    cargo = project / "Cargo.toml"
    if cargo.is_file() and not is_link_or_junction(cargo):
        technologies.add("rust")
        signals.append("Cargo.toml")
    go_mod = project / "go.mod"
    if go_mod.is_file() and not is_link_or_junction(go_mod):
        technologies.add("go")
        signals.append("go.mod")
    if (project / "Package.swift").is_file() and not is_link_or_junction(project / "Package.swift"):
        technologies.add("swift")
        signals.append("Package.swift")
    if (project / "pubspec.yaml").is_file() and not is_link_or_junction(project / "pubspec.yaml"):
        technologies.add("flutter")
        signals.append("pubspec.yaml")
    if (project / "tests").is_dir() and not is_link_or_junction(project / "tests"):
        signals.append("tests/")
    if (project / "AGENTS.md").is_file():
        signals.append("AGENTS.md")
    if (project / "CLAUDE.md").is_file():
        signals.append("CLAUDE.md")
    return {"project": project, "profile": _profile_for(technologies),
            "technologies": technologies, "signals": signals, "package": package_data}


def _workspace_patterns(project: Path, package: dict) -> tuple[list[str], list[str]]:
    patterns, excluded = [], []
    workspaces = package.get("workspaces", []) if package else []
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages", [])
    if isinstance(workspaces, list):
        for item in workspaces:
            if isinstance(item, str):
                (excluded if item.startswith("!") else patterns).append(item[1:] if item.startswith("!") else item)
    cargo = project / "Cargo.toml"
    if cargo.is_file() and not is_link_or_junction(cargo) and cargo.stat().st_size <= 200_000:
        text = cargo.read_text(encoding="utf-8", errors="replace")
        section = re.search(r"(?ms)^\[workspace\]\s*(.*?)(?=^\[|\Z)", text)
        if section:
            for key, output in (("members", patterns), ("exclude", excluded)):
                match = re.search(r"(?ms)^\s*" + key + r"\s*=\s*\[(.*?)\]", section.group(1))
                if match:
                    output.extend(a or b for a, b in re.findall(r"'([^']*)'|\"([^\"]*)\"", match.group(1)))
    pnpm = project / "pnpm-workspace.yaml"
    if pnpm.is_file() and not is_link_or_junction(pnpm) and pnpm.stat().st_size <= 50_000:
        lines = pnpm.read_text(encoding="utf-8", errors="replace").splitlines()
        in_packages = False
        for line in lines:
            if line.strip() == "packages:":
                in_packages = True
                continue
            if in_packages and line.strip() and not line[:1].isspace():
                break
            if in_packages:
                match = re.match(r"^\s*-\s*(['\"]?)([^'\"#]+)\1\s*(?:#.*)?$", line)
                if match:
                    patterns.append(match.group(2).strip())
    return list(dict.fromkeys(patterns)), list(dict.fromkeys(excluded))


def _workspace_members(project: Path, patterns: list[str], excluded: list[str]) -> list[Path]:
    found = {}
    for pattern in patterns:
        if not is_safe_relative_path(pattern):
            raise ValueError(f"Invalid declared workspace path: {pattern!r}")
        for match in project.glob(pattern):
            if len(found) >= 500:
                raise ValueError("Workspace declaration exceeds 500 project roots")
            if not match.is_dir() or is_link_or_junction(match):
                continue
            resolved = match.resolve()
            if not resolved.is_relative_to(project) or any(is_link_or_junction(p) for p in [match, *match.parents] if p != project.parent):
                continue
            relative = resolved.relative_to(project).as_posix()
            if any(fnmatch.fnmatch(relative, mask) for mask in excluded):
                continue
            found[relative] = resolved
    return [found[key] for key in sorted(found)]


def _verification_suggestions(folder: Path, relative: str, facts: dict) -> list[dict]:
    suggestions = []
    technologies = facts["technologies"]
    def add(command, reason):
        item = {"working_directory": relative, "command": command,
                "source": reason, "requires_owner_review": True, "executed": False}
        if item not in suggestions:
            suggestions.append(item)
    if "python" in technologies and (folder / "tests").is_dir():
        add(["python", "-m", "unittest", "discover", "-s", "tests", "-v"], "tests/ directory")
    package = facts.get("package", {})
    scripts = package.get("scripts", {}) if isinstance(package, dict) else {}
    if isinstance(scripts, dict):
        for name in ("test", "lint", "typecheck", "build"):
            if name in scripts and isinstance(scripts[name], str):
                add(["npm", "run", name], f"package.json scripts.{name}")
    if "rust" in technologies and (folder / "Cargo.toml").is_file():
        add(["cargo", "test"], "Cargo.toml")
    if "swift" in technologies and (folder / "Package.swift").is_file():
        add(["swift", "test"], "Package.swift")
    if "flutter" in technologies and (folder / "pubspec.yaml").is_file():
        add(["flutter", "test"], "pubspec.yaml")
    if "dotnet" in technologies:
        solution = next(iter(folder.glob("*.sln")), None)
        if solution:
            add(["dotnet", "test", solution.name], "solution file")
    return suggestions


def inspect_project(project: Path) -> dict:
    """Read declared project roots and known manifests without running project code."""
    project = project.expanduser().resolve()
    if not project.is_dir():
        raise ValueError("Project directory does not exist")
    root_facts = _base_facts(project)
    patterns, excluded = _workspace_patterns(project, root_facts["package"])
    members = _workspace_members(project, patterns, excluded)
    targets = [{"path": ".", "profile": root_facts["profile"],
                "technologies": sorted(root_facts["technologies"]), "signals": sorted(set(root_facts["signals"]))}]
    suggestions = _verification_suggestions(project, ".", root_facts)
    all_technologies = set(root_facts["technologies"])
    all_signals = set(root_facts["signals"])
    profiles = {root_facts["profile"]}
    for folder in members:
        relative = folder.relative_to(project).as_posix()
        facts = _base_facts(folder)
        if not facts["technologies"]:
            continue
        profiles.add(facts["profile"])
        all_technologies.update(facts["technologies"])
        all_signals.update(relative + "/" + value for value in facts["signals"])
        targets.append({"path": relative, "profile": facts["profile"],
                        "technologies": sorted(facts["technologies"]),
                        "signals": sorted(set(facts["signals"]))})
        suggestions.extend(_verification_suggestions(folder, relative, facts))
    profile = "monorepo" if len(targets) > 1 and len(profiles) > 1 else root_facts["profile"]
    return {"project": str(project), "profile": profile, "technologies": sorted(all_technologies),
            "signals": sorted(all_signals), "configured": (project / "kstack.json").is_file(),
            "workspace": {"declared": bool(patterns), "patterns": patterns, "excluded": excluded,
                          "targets": targets},
            "verification_suggestions": suggestions}


def _validate_commands(commands, field: str) -> list[list[str]]:
    if not isinstance(commands, list) or len(commands) > 30:
        raise ValueError(f"{field} must contain at most 30 argument-list commands")
    total_chars = 0
    for command in commands:
        if (not isinstance(command, list) or not command or len(command) > 25
                or any(not isinstance(arg, str) or not arg or "\x00" in arg or len(arg) > 4000 for arg in command)):
            raise ValueError(f"{field} commands must be bounded lists of nonempty arguments")
        total_chars += sum(len(arg) for arg in command)
    if total_chars > 100_000:
        raise ValueError(f"{field} is too large")
    return commands


def _project_target(folder: Path, relative: str) -> Path:
    if not is_safe_relative_path(relative):
        raise ValueError("verification target path must be a contained relative directory")
    target = folder.joinpath(*relative.split("/"))
    current = target
    while current != folder.parent and current != current.parent:
        if is_link_or_junction(current):
            raise ValueError("verification target path cannot traverse a symlink or junction")
        if current == folder:
            break
        current = current.parent
    if not target.resolve().is_relative_to(folder) or not target.is_dir():
        raise ValueError("verification target directory is missing or outside the project")
    return target


def load_project_config(project: Path) -> dict:
    folder = project.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError("Project directory does not exist")
    path = folder / "kstack.json"
    if is_link_or_junction(path):
        raise ValueError("kstack.json cannot be a symlink or junction")
    config = read_json(path, {})
    if not isinstance(config, dict):
        raise ValueError("kstack.json must contain a JSON object")
    version = config.get("version", 1)
    if type(version) is not int or version not in (1, 2):
        raise ValueError("Unsupported project configuration version")
    allowed = {"version", "profile", "skill_preferences", "verification_commands", "delivery"}
    if version == 2:
        allowed.add("verification_targets")
    if set(config) - allowed:
        raise ValueError("Unknown KStack configuration keys: " + ", ".join(sorted(set(config) - allowed)))
    profile = config.get("profile")
    if profile is not None and (not isinstance(profile, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,48}", profile)):
        raise ValueError("profile must be a valid profile identifier")
    preferences = config.get("skill_preferences", [])
    if (not isinstance(preferences, list) or len(preferences) > 100
            or any(not isinstance(value, str) or not NAME.fullmatch(value) for value in preferences)
            or len(set(preferences)) != len(preferences)):
        raise ValueError("skill_preferences must contain unique valid skill names")
    config["verification_commands"] = _validate_commands(config.get("verification_commands", []), "verification_commands")
    delivery = config.get("delivery", {})
    if (not isinstance(delivery, dict) or set(delivery) - {"verify_before_merge"}
            or any(type(value) is not bool for value in delivery.values())):
        raise ValueError("delivery supports only the boolean verify_before_merge setting")
    if version == 2:
        targets = config.get("verification_targets", [])
        if not isinstance(targets, list) or len(targets) > 50:
            raise ValueError("verification_targets must be a list of at most 50 targets")
        seen = set()
        validated = []
        for item in targets:
            if not isinstance(item, dict) or set(item) != {"path", "commands"}:
                raise ValueError("Each verification target needs only path and commands")
            target = _project_target(folder, item["path"])
            relative = target.relative_to(folder).as_posix()
            if relative in seen:
                raise ValueError("Duplicate verification target path")
            seen.add(relative)
            commands = _validate_commands(item["commands"], "verification target commands")
            if not commands:
                raise ValueError("Verification target commands cannot be empty")
            validated.append({"path": relative, "commands": commands})
        if len(config["verification_commands"]) + sum(len(x["commands"]) for x in validated) > 100:
            raise ValueError("Project verification configuration exceeds 100 commands")
        config["verification_targets"] = validated
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


START = "<!-- KSTACK:START -->"
END = "<!-- KSTACK:END -->"
INSTRUCTIONS = ("<!-- KSTACK:START -->\n"
                "## KStack developer workflow\n"
                "For substantial development, load the installed `kstack-router` skill when available. "
                "Select only relevant installed specialists; prefer Evolve when separately installed "
                "and appropriate. Run actual project checks before claiming verification. "
                "Respect existing repository instructions, permissions and security constraints; "
                "do not infer that catalogue entries are installed or that a passing static check proves host acceptance.\n"
                "<!-- KSTACK:END -->\n")


def install_instructions(project: Path, *, dry_run: bool = True, hosts=("codex", "claude")) -> dict:
    """Add a narrowly scoped, recognisable block, preserving all existing instructions.

    Refuse malformed or ambiguous markers. Never delete text owned by users.
    """
    from .installer import atomic_text
    directory = project.expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("Project directory does not exist")
    targets = {"codex": "AGENTS.md", "claude": "CLAUDE.md"}
    changed = []
    for host in hosts:
        if host not in targets:
            raise ValueError("Unsupported instruction host")
        file = directory / targets[host]
        if file.is_symlink():
            raise ValueError("Refusing symlink instruction target")
        original = file.read_text(encoding="utf-8") if file.is_file() else ""
        if original.count(START) != original.count(END) or original.count(START) > 1:
            raise ValueError("Malformed or duplicated KStack instruction markers")
        if START in original:
            first = original.index(START)
            second = original.index(END)
            if second < first:
                raise ValueError("Reversed managed instruction markers")
            expected = original[:first] + INSTRUCTIONS.rstrip("\n") + original[second + len(END):]
        else:
            expected = original.rstrip("\n") + ("\n\n" if original.strip() else "") + INSTRUCTIONS
        action = "unchanged" if original == expected else "would-write" if dry_run else "updated"
        changed.append({"host": host, "file": str(file), "action": action})
        if not dry_run and original != expected:
            atomic_text(file, expected)
    return {"changes": changed, "dry_run": dry_run,
            "note": "Instructions refer to installed skills; real agent activation still requires host acceptance."}
