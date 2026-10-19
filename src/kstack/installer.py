"""Managed filesystem installs for Codex and Claude Code; never run skill code."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from .security import digest, parse_skill, NAME
from .state import read_json, write_json


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError("Refusing to overwrite a symlink")
    fd, tmp = tempfile.mkstemp(prefix=".kstack-write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def skill_dir(host: str, scope: str, project: Path | None, home: Path | None = None) -> Path:
    if host not in ("codex", "claude") or scope not in ("project", "global"):
        raise ValueError("Supported: --host codex|claude and --scope project|global")
    if scope == "project":
        if project is None or not project.is_dir():
            raise ValueError("A pre-existing --project directory is required")
        base = project.resolve()
    else:
        base = (home or Path.home()).expanduser().resolve()
    return base / (".agents/skills" if host == "codex" else ".claude/skills")


def bundled_skills(root: Path) -> dict[str, str]:
    candidates = root / "skills"
    if not candidates.is_dir():
        # pip wheel fallback, synced by the packaging script.
        candidates = Path(__file__).parent / "bundled" / "skills"
    found = {}
    for entry in sorted(candidates.iterdir()):
        if entry.is_symlink() or not entry.is_dir():
            continue
        path = entry / "SKILL.md"
        if path.is_symlink() or not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        meta = parse_skill(content)
        if meta["name"] != entry.name:
            raise ValueError("Bundled skill folder/name mismatch")
        found[entry.name] = content
    return found


def available_skills(root: Path, state: Path, with_external: bool = True) -> dict[str, str]:
    skills = bundled_skills(root)
    if not with_external:
        return skills
    for item in read_json(state / "active.json", {}).values():
        name = item["name"]
        if not NAME.fullmatch(name) or name in skills:
            raise ValueError("Active skill name conflicts with bundled skill")
        obj = state / "objects" / (item["content_sha256"] + ".md")
        if obj.is_symlink() or not obj.is_file():
            raise ValueError(f"Active skill missing: {name}")
        content = obj.read_text(encoding="utf-8")
        if digest(content) != item["content_sha256"] or parse_skill(content)["name"] != name:
            raise ValueError(f"Active skill integrity mismatch: {name}")
        skills[name] = content
    return skills


def _assert_no_symlink_ancestors(path: Path) -> None:
    current = path
    while current != current.parent:
        if current.is_symlink():
            raise ValueError(f"Symlink ancestor in managed location: {current}")
        current = current.parent


def install(root: Path, state: Path, host: str, scope: str, project: Path | None = None,
            home: Path | None = None, with_external: bool = True, dry_run: bool = False) -> dict:
    dest = skill_dir(host, scope, project, home)
    _assert_no_symlink_ancestors(dest)
    contents = available_skills(root, state, with_external)
    manifest_file = dest / ".kstack-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    manifest = read_json(manifest_file, {"version": 1, "files": {}})
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise ValueError("Corrupted install manifest")
    old = dict(manifest["files"])
    desired = {name + "/SKILL.md": digest(content) for name, content in contents.items()}
    # Preflight every mutation before making any change.
    for rel, old_hash in old.items():
        name, sep, filename = rel.partition("/")
        if not sep or filename != "SKILL.md" or not NAME.fullmatch(name):
            raise ValueError("Invalid managed manifest path")
        target = dest / rel
        _assert_no_symlink_ancestors(target)
        if target.exists() and digest(target.read_text(encoding="utf-8")) != old_hash:
            raise ValueError(f"Refusing to modify locally edited managed file: {target}")
    for name, content in contents.items():
        target = dest / name / "SKILL.md"
        _assert_no_symlink_ancestors(target)
        if target.exists() and name + "/SKILL.md" not in old and digest(target.read_text(encoding="utf-8")) != digest(content):
            raise ValueError(f"Refusing to overwrite unmanaged file: {target}")
    changes = []
    for name, content in sorted(contents.items()):
        target = dest / name / "SKILL.md"
        expected_hash = digest(content)
        unchanged = target.exists() and digest(target.read_text(encoding="utf-8")) == expected_hash
        changes.append({"path": str(target), "action": "unchanged" if unchanged else "install"})
        if not dry_run and not unchanged:
            atomic_text(target, content)
    for rel in sorted(set(old) - set(desired)):
        target = dest / rel
        changes.append({"path": str(target), "action": "remove-stale"})
        if not dry_run and target.exists():
            target.unlink()
            if not any(target.parent.iterdir()):
                target.parent.rmdir()
    if not dry_run:
        write_json(manifest_file, {"version": 1, "files": desired})
    return {"host": host, "scope": scope, "destination": str(dest), "dry_run": dry_run, "changes": changes}

def uninstall(host: str, scope: str, project: Path | None = None, home: Path | None = None,
              dry_run: bool = False) -> dict:
    dest = skill_dir(host, scope, project, home)
    manifest_file = dest / ".kstack-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    manifest = read_json(manifest_file, {"files": {}})
    files = manifest.get("files", {})
    # Preflight all files to ensure no half-uninstall on conflict.
    for relative, stored_hash in files.items():
        name, sep, filename = relative.partition("/")
        if not sep or filename != "SKILL.md" or not NAME.fullmatch(name):
            raise ValueError("Invalid managed manifest path")
        target = dest / name / "SKILL.md"
        if target.is_symlink() or target.parent.is_symlink():
            raise ValueError("Managed target became symlink")
        if target.exists() and digest(target.read_text(encoding="utf-8")) != stored_hash:
            raise ValueError("Managed skill locally modified; refusing uninstall")
    removed = []
    for relative in files:
        target = dest / relative
        if target.exists():
            removed.append(str(target))
            if not dry_run:
                target.unlink()
                if not any(target.parent.iterdir()):
                    target.parent.rmdir()
    if not dry_run and manifest_file.exists():
        manifest_file.unlink()
    return {"destination": str(dest), "dry_run": dry_run, "removed": removed}


def doctor(root: Path, state: Path, host: str | None = None, scope: str = "global",
           project: Path | None = None, home: Path | None = None) -> dict:
    checks = []
    for name, content in bundled_skills(root).items():
        checks.append({"check": "bundled:" + name, "ok": bool(parse_skill(content))})
    for name, content in available_skills(root, state).items():
        checks.append({"check": "available:" + name, "ok": bool(parse_skill(content))})
    if host:
        location = skill_dir(host, scope, project, home)
        manifest_path = location / ".kstack-managed.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            checks.append({"check": "host:installation_present", "ok": False})
            return {"ok": False, "checks": checks,
                    "note": "KStack is not installed in this host/scope; run install first."}
        manifest = read_json(manifest_path, {})
        expected = {name + "/SKILL.md": digest(content) for name, content in available_skills(root, state).items()}
        if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
            checks.append({"check": "host:manifest_valid", "ok": False})
            return {"ok": False, "checks": checks, "note": "Invalid installation manifest"}
        checks.append({"check": "host:active_generation_matches", "ok": manifest["files"] == expected})
        for rel, expected_hash in manifest.get("files", {}).items():
            name, sep, filename = rel.partition("/")
            if not sep or filename != "SKILL.md" or not NAME.fullmatch(name):
                checks.append({"check": "host:invalid_manifest_path", "ok": False})
                continue
            path = location / rel
            ok = path.is_file() and not path.is_symlink() and digest(path.read_text(encoding="utf-8")) == expected_hash
            checks.append({"check": "installed:" + rel, "ok": ok})
        from .external import list_external
        external = list_external(host, scope, project, home)
        checks.append({"check": "host:external_packages", "ok": external["ok"]})
    return {"ok": all(item["ok"] for item in checks), "checks": checks,
            "note": "File presence and integrity do not prove an agent loaded or obeyed a skill."}
