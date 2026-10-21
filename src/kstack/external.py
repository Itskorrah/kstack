"""Deliberate, pinned installation of reviewed local skill packages.

No upstream installer is executed. External packages may include scripts; they
remain inert during copy, but a coding host may execute them later. Thus code
packages require an extra, explicit permission and never auto-promote.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from .installer import atomic_text, skill_dir, _assert_no_symlink_ancestors
from .security import parse_skill, SHA, NAME, is_link_or_junction, is_safe_relative_path
from .state import read_json, write_json
from .transaction import commit_host_files, host_lock, host_transaction_pending, recover_host_files, _host_path_key

MAX_FILES = 150
MAX_BYTES = 3_000_000
PACKAGE_MANIFEST = "kstack-package.json"
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
CAPABILITY = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _version(value: str) -> tuple[int, int, int]:
    match = SEMVER.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise ValueError(f"Invalid package version: {value!r}; expected MAJOR.MINOR.PATCH")
    return tuple(map(int, match.groups()))


def _satisfies(version: tuple[int, int, int], specifier: str) -> bool:
    """Evaluate a deliberately small, deterministic SemVer range subset."""
    if not isinstance(specifier, str) or not specifier.strip():
        raise ValueError("Dependency version range cannot be empty")
    specifier = specifier.strip()
    checks = []
    if specifier == "*":
        return True
    if specifier.startswith(("^", "~")):
        kind, exact = specifier[0], _version(specifier[1:])
        if kind == "^":
            major, minor, patch = exact
            upper = (major + 1, 0, 0) if major else ((0, minor + 1, 0) if minor else (0, 0, patch + 1))
        else:
            upper = (exact[0], exact[1] + 1, 0)
        checks = [(">=", exact), ("<", upper)]
    elif SEMVER.fullmatch(specifier):
        checks = [("==", _version(specifier))]
    else:
        for part in specifier.split(","):
            match = re.fullmatch(r"\s*(>=|>|<=|<|==)\s*(\d+(?:\.\d+){2})\s*", part)
            if not match:
                raise ValueError(f"Unsupported dependency version range: {specifier}")
            checks.append((match.group(1), _version(match.group(2))))
    return all({"==": version == bound, ">=": version >= bound,
                "<=": version <= bound, ">": version > bound,
                "<": version < bound}[operator] for operator, bound in checks)


def _package_entries(source: Path, requested: str, tracked: set[str]) -> tuple[list[dict], dict[str, str]]:
    """Resolve a KStack package's declared sibling skills in dependency order."""
    path = source / PACKAGE_MANIFEST
    if is_link_or_junction(path):
        raise ValueError("Package manifest cannot be a symlink")
    if not path.exists():
        return [], {}
    if PACKAGE_MANIFEST not in tracked or not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError("Package manifest must be a tracked ordinary file under 100 KB")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("Invalid KStack package manifest JSON") from exc
    if not isinstance(data, dict) or set(data) != {"format", "skills"} or data.get("format") != 1:
        raise ValueError("Package manifest must use format 1 and declare skills")
    if not isinstance(data["skills"], list) or not data["skills"] or len(data["skills"]) > 150:
        raise ValueError("Package manifest skills must be a nonempty bounded list")
    by_name = {}
    by_path = {}
    portable_paths = set()
    for item in data["skills"]:
        if not isinstance(item, dict) or set(item) - {"name", "path", "version", "dependencies", "provides"}:
            raise ValueError("Invalid package skill entry")
        if not {"name", "path", "version"} <= set(item):
            raise ValueError("Package skill needs name, path and version")
        name, relative = item["name"], item["path"]
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in by_name:
            raise ValueError("Invalid or duplicate package skill name")
        if not is_safe_relative_path(relative):
            raise ValueError(f"Invalid package skill path: {relative!r}")
        portable_path = _host_path_key(relative)
        if portable_path in portable_paths:
            raise ValueError("Multiple package skills claim colliding paths across host filesystems")
        portable_paths.add(portable_path)
        version = _version(item["version"])
        dependencies = item.get("dependencies", [])
        provides = item.get("provides", [])
        if not isinstance(dependencies, list) or not isinstance(provides, list):
            raise ValueError("Package dependencies and provides must be lists")
        normalized_dependencies = []
        seen_dependencies = set()
        for dependency in dependencies:
            if (not isinstance(dependency, dict) or set(dependency) != {"name", "specifier"}
                    or not isinstance(dependency["name"], str) or not NAME.fullmatch(dependency["name"])
                    or dependency["name"] in seen_dependencies):
                raise ValueError(f"Invalid dependency declaration for {name}")
            _validate_specifier(dependency["specifier"])
            normalized_dependencies.append({"name": dependency["name"], "specifier": dependency["specifier"]})
            seen_dependencies.add(dependency["name"])
        if any(not isinstance(cap, str) or not CAPABILITY.fullmatch(cap) for cap in provides):
            raise ValueError(f"Invalid capability declaration for {name}")
        if len(set(provides)) != len(provides):
            raise ValueError(f"Duplicate capability declaration for {name}")
        entry = {"name": name, "path": relative, "version": item["version"],
                 "version_tuple": version, "dependencies": normalized_dependencies,
                 "provides": list(provides)}
        by_name[name] = entry
        by_path[relative] = entry
    root = by_path.get(requested)
    if root is None:
        raise ValueError("Requested skill directory is not declared in kstack-package.json")
    ordered, state = [], {}

    def visit(entry: dict, stack: list[str]) -> None:
        name = entry["name"]
        if state.get(name) == "done":
            return
        if state.get(name) == "visiting":
            raise ValueError("Cyclic skill dependency: " + " -> ".join(stack + [name]))
        state[name] = "visiting"
        for dependency in entry["dependencies"]:
            target = by_name.get(dependency["name"])
            if target is None:
                raise ValueError(f"Missing sibling dependency {dependency['name']} required by {name}")
            if not _satisfies(target["version_tuple"], dependency["specifier"]):
                raise ValueError(f"Dependency {target['name']} {target['version']} does not satisfy {dependency['specifier']}")
            visit(target, stack + [name])
        state[name] = "done"
        ordered.append(entry)

    visit(root, [])
    providers = {}
    for entry in ordered:
        for capability in entry["provides"]:
            if capability in providers:
                raise ValueError(f"Capability {capability} has multiple providers in the resolved package")
            providers[capability] = entry["name"]
    return ordered, providers


def _validate_specifier(specifier: str) -> None:
    """Validate a range without needing a candidate version yet."""
    if not isinstance(specifier, str) or not specifier.strip():
        raise ValueError("Dependency version range cannot be empty")
    value = specifier.strip()
    if value == "*":
        return
    if value.startswith(("^", "~")):
        _version(value[1:])
        return
    if SEMVER.fullmatch(value):
        _version(value)
        return
    parts = value.split(",")
    if not parts or any(not re.fullmatch(r"\s*(>=|>|<=|<|==)\s*(\d+(?:\.\d+){2})\s*", part) for part in parts):
        raise ValueError(f"Unsupported dependency version range: {specifier}")
    for part in parts:
        _version(re.fullmatch(r"\s*(?:>=|>|<=|<|==)\s*(\d+(?:\.\d+){2})\s*", part).group(1))


def _git(source: Path, *args: str) -> str:
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT", "WINDIR")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    run = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(source), *args],
                         capture_output=True, text=True, timeout=15, check=False, env=env)
    if run.returncode:
        raise ValueError("Local source is not a usable Git checkout: " + " ".join(args))
    return run.stdout.strip()


def _inspect_skill_files(source: Path, relative: str, tracked: set[str]) -> tuple[str, dict, int]:
    if not is_safe_relative_path(relative):
        raise ValueError("Expected a relative skill directory")
    parts = relative.split("/")
    directory = source.joinpath(*parts)
    if not directory.is_dir() or is_link_or_junction(directory) or not directory.resolve().is_relative_to(source):
        raise ValueError(f"Invalid skill directory: {relative}")
    skill = directory / "SKILL.md"
    if not skill.is_file() or is_link_or_junction(skill):
        raise ValueError(f"Expected ordinary SKILL.md in {relative}")
    name = parse_skill(skill.read_text(encoding="utf-8"))["name"]
    files, total = {}, 0
    portable_files = set()
    for entry in sorted(directory.rglob("*")):
        if is_link_or_junction(entry):
            raise ValueError("Symbolic links are not supported in approved skill packages")
        if not entry.is_file():
            continue
        if not entry.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Package path escaped root")
        rel_from_checkout = entry.relative_to(source).as_posix()
        if rel_from_checkout not in tracked:
            raise ValueError("Package includes untracked file")
        rel = entry.relative_to(directory).as_posix()
        portable_file = _host_path_key(rel)
        if portable_file in portable_files:
            raise ValueError("Skill package contains colliding file paths across host filesystems")
        portable_files.add(portable_file)
        size = entry.stat().st_size
        total += size
        if len(files) >= MAX_FILES or total > MAX_BYTES:
            raise ValueError("Skill package exceeds safety/resource limits")
        files[rel] = hashlib.sha256(entry.read_bytes()).hexdigest()
    return name, files, total


def inspect_package(source: Path, relative: str, expected_commit: str) -> dict:
    source = source.expanduser()
    if is_link_or_junction(source):
        raise ValueError("Source checkout cannot be a symlink")
    source = source.resolve()
    if not source.is_dir() or not SHA.fullmatch(expected_commit):
        raise ValueError("Existing source directory and exact Git commit required")
    actual = _git(source, "rev-parse", "HEAD")
    if actual != expected_commit:
        raise ValueError("Checkout HEAD differs from approved commit")
    if _git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Checkout contains modified or untracked files; review a clean pinned checkout")
    tracked = set(_git(source, "ls-files", "--cached").splitlines())
    package_entries, providers = _package_entries(source, relative, tracked)
    if not package_entries:
        name, files, total = _inspect_skill_files(source, relative, tracked)
        package_entries = [{"name": name, "path": relative, "version": None,
                            "dependencies": [], "provides": [], "files": files}]
        root_files = files
    else:
        root_entry = next(entry for entry in package_entries if entry["path"] == relative)
        root_name, root_files, _ = _inspect_skill_files(source, relative, tracked)
        if root_name != root_entry["name"]:
            raise ValueError("Package manifest name does not match SKILL.md frontmatter")
        total = 0
        package_count = 0
        for entry in package_entries:
            name, files, size = _inspect_skill_files(source, entry["path"], tracked)
            if name != entry["name"]:
                raise ValueError(f"Package manifest name does not match SKILL.md: {entry['path']}")
            entry["files"] = files
            total += size
            package_count += len(files)
            if package_count > MAX_FILES or total > MAX_BYTES:
                raise ValueError("Resolved skill package exceeds safety/resource limits")
    all_paths = [entry["name"] + "/" + rel for entry in package_entries for rel in entry["files"]]
    has_code = any(not path.lower().endswith((".md", ".txt", ".rst", ".adoc")) for path in all_paths)
    root_entry = next(entry for entry in package_entries if entry["path"] == relative)
    resolved = [{"name": entry["name"], "relative": entry["path"], "version": entry["version"],
                 "dependencies": entry["dependencies"], "provides": entry["provides"], "files": entry["files"]}
                for entry in package_entries]
    return {"name": root_entry["name"], "source": str(source), "relative": relative, "commit": actual,
            "version": root_entry["version"], "dependencies": [x["name"] for x in package_entries if x["name"] != root_entry["name"]],
            "resolved_skills": resolved, "providers": providers, "files": root_files,
            "contains_code_or_assets": has_code, "bytes": total}


def install_package(source: Path, relative: str, expected_commit: str, host: str, scope: str,
                    project: Path | None = None, home: Path | None = None, *, dry_run: bool = True,
                    reviewed: bool = False, allow_code: bool = False) -> dict:
    package = inspect_package(source, relative, expected_commit)
    if not reviewed and not dry_run:
        raise ValueError("Explicit --reviewed required: verify provenance, licence and trust before installation")
    if package["contains_code_or_assets"] and not allow_code and not dry_run:
        raise ValueError("Contains non-documentation resources: --allow-code required after manual review")
    dest = skill_dir(host, scope, project, home)
    _assert_no_symlink_ancestors(dest)
    if dry_run:
        if host_transaction_pending(dest):
            raise ValueError("Interrupted host transaction exists; run recover-install before previewing")
        return _install_package_locked(package, source, relative, expected_commit, dest,
                                       dry_run=True, reviewed=reviewed)
    dest.mkdir(parents=True, exist_ok=True)
    with host_lock(dest):
        recovered = recover_host_files(dest)
        result = _install_package_locked(package, source, relative, expected_commit, dest,
                                         dry_run=False, reviewed=reviewed, allow_code=allow_code)
        result["recovered_interrupted_generation"] = recovered["recovered"]
        return result


def _install_package_locked(package: dict, source: Path, relative: str, expected_commit: str,
                            dest: Path, *, dry_run: bool, reviewed: bool,
                            allow_code: bool = False) -> dict:
    manifest_file = dest / ".kstack-external-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    prior = read_json(manifest_file, {"version": 1, "packages": {}})
    if (not isinstance(prior, dict) or prior.get("version", 1) not in (1, 2)
            or not isinstance(prior.get("packages"), dict)):
        raise ValueError("Invalid external skill install manifest")
    resolved = package.get("resolved_skills") or [{"name": package["name"], "relative": relative,
        "version": None, "dependencies": [], "provides": [], "files": package["files"]}]
    core_manifest_file = dest / ".kstack-managed.json"
    _assert_no_symlink_ancestors(core_manifest_file)
    core_manifest = read_json(core_manifest_file, {"files": {}})
    core_files = core_manifest.get("files", {}) if isinstance(core_manifest, dict) else {}
    if not isinstance(core_files, dict):
        raise ValueError("Invalid KStack-managed host manifest")
    for skill in resolved:
        name, files = skill["name"], skill["files"]
        if not NAME.fullmatch(name) or not isinstance(files, dict):
            raise ValueError("Invalid resolved package skill")
        if any(path.startswith(name + "/") for path in core_files):
            raise ValueError(f"Name collision with KStack-managed skill: {name}")
        managed = prior["packages"].get(name)
        if managed is not None and (not isinstance(managed, dict) or managed.get("files") != files):
            raise ValueError(f"Existing external skill differs; review and uninstall before changing it: {name}")
        target_dir = dest / name
        _assert_no_symlink_ancestors(target_dir)
        for rel, checksum in files.items():
            if (not is_safe_relative_path(rel)
                    or not isinstance(checksum, str) or not SHA256.fullmatch(checksum)):
                raise ValueError("Invalid resolved package path or hash")
            target = target_dir / rel
            _assert_no_symlink_ancestors(target)
            if is_link_or_junction(target):
                raise ValueError("Refusing symlink target")
            if target.exists():
                if managed is None:
                    raise ValueError(f"Refusing to adopt existing unmanaged file: {target}")
                if hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
                    raise ValueError("Existing content conflicts with proposed package")
        if target_dir.exists() and managed is None:
            if any(x for x in target_dir.rglob("*") if x.is_file() and x.relative_to(target_dir).as_posix() not in files):
                raise ValueError(f"Unmanaged files exist in target directory: {name}")
    transaction = None
    if not dry_run:
        mutations: dict[str, bytes | None] = {}
        for skill in resolved:
            name = skill["name"]
            for rel, checksum in skill["files"].items():
                src = source / skill["relative"] / rel
                data = src.read_bytes()
                if hashlib.sha256(data).hexdigest() != checksum:
                    raise ValueError("Source changed during installation")
                mutations[name + "/" + rel] = data
        next_manifest = dict(prior)
        next_manifest["version"] = 2
        next_manifest["packages"] = dict(prior["packages"])
        for skill in resolved:
            next_manifest["packages"][skill["name"]] = {
                "source": str(source), "relative": skill["relative"], "package_root": relative,
                "commit": expected_commit, "version": skill["version"],
                "dependencies": skill["dependencies"], "provides": skill["provides"],
                "files": skill["files"], "reviewed": True,
                "contains_code_or_assets": any(not path.lower().endswith((".md", ".txt", ".rst", ".adoc"))
                                                for path in skill["files"])}
        mutations[manifest_file.name] = json.dumps(next_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        transaction = commit_host_files(dest, mutations)
    return {**package, "destination": str(dest), "installed_skills": [x["name"] for x in resolved], "dry_run": dry_run,
            "installed": not dry_run, "transaction": transaction,
            "note": "Package copied but real host invocation is not verified"}


def list_external(host: str, scope: str, project: Path | None = None, home: Path | None = None) -> dict:
    dest = skill_dir(host, scope, project, home)
    manifest = dest / ".kstack-external-managed.json"
    try:
        _assert_no_symlink_ancestors(manifest)
    except ValueError:
        return {"packages": [], "capabilities": [], "ok": False, "error": "External manifest path cannot contain a symlink"}
    raw = read_json(manifest, {"packages": {}})
    packages = raw.get("packages", {}) if isinstance(raw, dict) else None
    if not isinstance(packages, dict):
        return {"packages": [], "capabilities": [], "ok": False, "error": "Invalid external package manifest"}
    reports = []
    capabilities = {}
    for name, record in packages.items():
        if not isinstance(name, str) or not NAME.fullmatch(name) or not isinstance(record, dict):
            reports.append({"name": str(name), "status": "invalid_manifest"})
            continue
        folder = dest / name
        status = "installed"
        files = record.get("files")
        if not isinstance(files, dict) or not isinstance(record.get("commit"), str) or not SHA.fullmatch(record["commit"]):
            status = "invalid_manifest"
            files = {}
        for rel, sha in files.items():
            if (not is_safe_relative_path(rel)
                    or not isinstance(sha, str) or not SHA256.fullmatch(sha)):
                status = "invalid_manifest"
                break
            file = folder / rel
            try:
                _assert_no_symlink_ancestors(file)
            except ValueError:
                status = "modified_or_missing"
                break
            if not file.is_file() or is_link_or_junction(file) or hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                status = "modified_or_missing"
                break
        version = record.get("version")
        if version is not None:
            try:
                _version(version)
            except ValueError:
                status = "invalid_manifest"
        dependencies = record.get("dependencies", [])
        if not isinstance(dependencies, list):
            status = "invalid_manifest"
            dependencies = []
        for dependency in dependencies:
            if (not isinstance(dependency, dict) or set(dependency) != {"name", "specifier"}
                    or not isinstance(dependency.get("name"), str) or not isinstance(dependency.get("specifier"), str)):
                status = "invalid_manifest"
                break
            provider = packages.get(dependency["name"])
            try:
                if (not isinstance(provider, dict) or not isinstance(provider.get("version"), str)
                        or not _satisfies(_version(provider["version"]), dependency["specifier"])):
                    status = "dependency_missing_or_incompatible"
            except ValueError:
                status = "invalid_manifest"
        provides = record.get("provides", [])
        if not isinstance(provides, list) or any(not isinstance(cap, str) or not CAPABILITY.fullmatch(cap) for cap in provides):
            status = "invalid_manifest"
            provides = []
        for capability in provides:
            if capability in capabilities:
                capabilities[capability] = None
                status = "capability_conflict"
            else:
                capabilities[capability] = name
        reports.append({"name": name, "status": status, "commit": record.get("commit"),
                        "version": version, "dependencies": dependencies, "provides": provides,
                        "contains_code_or_assets": bool(record.get("contains_code_or_assets", False))})
    registry = [{"capability": key, "skill": value, "installed": value is not None}
                for key, value in sorted(capabilities.items())]
    return {"packages": reports, "capabilities": registry,
            "ok": all(x["status"] == "installed" for x in reports) and all(x["installed"] for x in registry)}


def uninstall_package(name: str, host: str, scope: str, project: Path | None = None,
                     home: Path | None = None, *, dry_run: bool = False) -> dict:
    """Remove one manifest-owned external skill without touching unrelated files."""
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError("Invalid external skill name")
    dest = skill_dir(host, scope, project, home)
    _assert_no_symlink_ancestors(dest)
    if not dest.exists():
        return {"name": name, "destination": str(dest), "dry_run": dry_run,
                "removed": [], "transaction": None, "status": "not_installed"}
    if dry_run:
        if host_transaction_pending(dest):
            raise ValueError("Interrupted host transaction exists; run recover-install before previewing")
        return _uninstall_package_locked(name, dest, dry_run=True)
    with host_lock(dest):
        recovered = recover_host_files(dest)
        result = _uninstall_package_locked(name, dest, dry_run=False)
        result["recovered_interrupted_generation"] = recovered["recovered"]
        return result


def _uninstall_package_locked(name: str, dest: Path, *, dry_run: bool) -> dict:
    manifest_file = dest / ".kstack-external-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    if host_transaction_pending(dest):
        raise ValueError("Interrupted host transaction exists; run recover-install before uninstalling")
    manifest = read_json(manifest_file, {"version": 1, "packages": {}})
    if (not isinstance(manifest, dict) or manifest.get("version", 1) not in (1, 2)
            or not isinstance(manifest.get("packages"), dict)):
        raise ValueError("Invalid external skill install manifest")
    packages = manifest["packages"]
    record = packages.get(name)
    if record is None:
        return {"name": name, "destination": str(dest), "dry_run": dry_run,
                "removed": [], "transaction": None, "status": "not_installed"}
    if not isinstance(record, dict) or not isinstance(record.get("files"), dict):
        raise ValueError("Invalid external package ownership record")

    dependents = []
    for other_name, other in packages.items():
        if not isinstance(other_name, str) or not NAME.fullmatch(other_name) or not isinstance(other, dict):
            raise ValueError("Invalid external package ownership record")
        dependencies = other.get("dependencies", [])
        if not isinstance(dependencies, list):
            raise ValueError("Invalid external package dependency record")
        for dependency in dependencies:
            if isinstance(dependency, str):
                dependency_name = dependency
            elif (isinstance(dependency, dict) and set(dependency) == {"name", "specifier"}
                  and isinstance(dependency.get("name"), str) and NAME.fullmatch(dependency["name"])
                  and isinstance(dependency.get("specifier"), str)):
                dependency_name = dependency["name"]
            else:
                raise ValueError("Invalid external package dependency record")
            if other_name != name and dependency_name == name:
                dependents.append(other_name)
    if dependents:
        raise ValueError("Cannot uninstall a skill with installed dependents: " + ", ".join(sorted(dependents)))

    folder = dest / name
    mutations: dict[str, bytes | None] = {}
    removed = []
    for relative, checksum in record["files"].items():
        if (not is_safe_relative_path(relative)
                or not isinstance(checksum, str) or not SHA256.fullmatch(checksum)):
            raise ValueError("Invalid external package ownership path or hash")
        target = folder / relative
        _assert_no_symlink_ancestors(target)
        if is_link_or_junction(target):
            raise ValueError("Refusing to uninstall a symlinked external file")
        if target.exists():
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
                raise ValueError(f"External skill was modified; refusing uninstall: {target}")
            mutations[name + "/" + relative] = None
            removed.append(str(target))

    remaining = dict(packages)
    del remaining[name]
    next_manifest: dict | None
    if remaining:
        next_manifest = dict(manifest)
        next_manifest["packages"] = remaining
        mutations[manifest_file.name] = json.dumps(next_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    else:
        mutations[manifest_file.name] = None
    transaction = commit_host_files(dest, mutations) if not dry_run and mutations else None
    return {"name": name, "destination": str(dest), "dry_run": dry_run,
            "removed": removed, "transaction": transaction,
            "status": "removed" if not dry_run else "would_remove"}
