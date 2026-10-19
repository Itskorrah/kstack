"""Managed filesystem installs for Codex and Claude Code; never run skill code."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from .security import digest, parse_skill, NAME, is_link_or_junction
from .state import read_json, write_json
from .transaction import (commit_host_files, host_lock, host_transaction_pending,
                          recover_host_files)


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if is_link_or_junction(path):
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
        if is_link_or_junction(entry) or not entry.is_dir():
            continue
        path = entry / "SKILL.md"
        if is_link_or_junction(path) or not path.is_file():
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
        if is_link_or_junction(obj) or not obj.is_file():
            raise ValueError(f"Active skill missing: {name}")
        content = obj.read_text(encoding="utf-8")
        if digest(content) != item["content_sha256"] or parse_skill(content)["name"] != name:
            raise ValueError(f"Active skill integrity mismatch: {name}")
        skills[name] = content
    return skills


def _assert_no_symlink_ancestors(path: Path) -> None:
    current = path
    while current != current.parent:
        if is_link_or_junction(current):
            raise ValueError(f"Symlink or junction ancestor in managed location: {current}")
        current = current.parent


def install(root: Path, state: Path, host: str, scope: str, project: Path | None = None,
            home: Path | None = None, with_external: bool = True, dry_run: bool = False) -> dict:
    dest = skill_dir(host, scope, project, home)
    _assert_no_symlink_ancestors(dest)
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
        with host_lock(dest):
            recovered = recover_host_files(dest)
            result = _install_locked(root, state, host, scope, project, home, with_external, dest)
            result["recovered_interrupted_generation"] = recovered["recovered"]
            return result
    if host_transaction_pending(dest):
        raise ValueError("Interrupted host transaction exists; run recover-install before previewing")
    return _install_locked(root, state, host, scope, project, home, with_external, dest, dry_run=True)


def _install_locked(root: Path, state: Path, host: str, scope: str,
                    project: Path | None, home: Path | None, with_external: bool,
                    dest: Path, dry_run: bool = False) -> dict:
    contents = available_skills(root, state, with_external)
    manifest_file = dest / ".kstack-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    manifest = read_json(manifest_file, {"version": 1, "files": {}})
    if (not isinstance(manifest, dict) or manifest.get("version", 1) not in (1, 2, 3)
            or not isinstance(manifest.get("files"), dict)):
        raise ValueError("Corrupted install manifest")
    old = dict(manifest["files"])
    desired = {name + "/SKILL.md": digest(content) for name, content in contents.items()}
    # Preflight every mutation before making any change.
    for rel, old_hash in old.items():
        name, sep, filename = rel.partition("/")
        if not sep or filename != "SKILL.md" or not NAME.fullmatch(name):
            raise ValueError("Invalid managed manifest path")
        if not isinstance(old_hash, str) or len(old_hash) != 64 or any(c not in "0123456789abcdef" for c in old_hash):
            raise ValueError("Invalid managed file hash")
        target = dest / rel
        _assert_no_symlink_ancestors(target)
        if target.exists() and digest(target.read_text(encoding="utf-8")) != old_hash:
            raise ValueError(f"Refusing to modify locally edited managed file: {target}")
    for name, content in contents.items():
        target = dest / name / "SKILL.md"
        _assert_no_symlink_ancestors(target)
        if target.exists() and name + "/SKILL.md" not in old:
            raise ValueError(f"Refusing to adopt or overwrite unmanaged file: {target}")
    changes = []
    mutations: dict[str, str | None] = {}
    for name, content in sorted(contents.items()):
        target = dest / name / "SKILL.md"
        expected_hash = digest(content)
        unchanged = target.exists() and digest(target.read_text(encoding="utf-8")) == expected_hash
        changes.append({"path": str(target), "action": "unchanged" if unchanged else "install"})
        if not unchanged:
            mutations[name + "/SKILL.md"] = content
    for rel in sorted(set(old) - set(desired)):
        target = dest / rel
        changes.append({"path": str(target), "action": "remove-stale"})
        if target.exists():
            mutations[rel] = None
    if manifest.get("version") == 3:
        generation = manifest.get("generation")
        if not isinstance(generation, str) or len(generation) != 32 or any(c not in "0123456789abcdef" for c in generation):
            raise ValueError("Invalid managed install generation")
    else:
        generation = None
    unchanged_generation = manifest.get("version") == 3 and manifest.get("files") == desired
    if not unchanged_generation:
        generation = uuid.uuid4().hex
        next_manifest = {"version": 3, "generation": generation,
                         "previous_generation": manifest.get("generation"), "files": desired}
    else:
        next_manifest = manifest
    if not dry_run:
        serialized_manifest = json.dumps(next_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        if manifest != next_manifest or not manifest_file.exists():
            mutations[manifest_file.name] = serialized_manifest
        transaction = (commit_host_files(dest, mutations, generation=generation, retain_backup=True)
                       if mutations else {"committed": False, "files_changed": 0, "generation": generation})
    else:
        transaction = None
    return {"host": host, "scope": scope, "destination": str(dest), "dry_run": dry_run,
            "changes": changes, "transaction": transaction}


def rollback_install(host: str, scope: str, project: Path | None = None,
                    home: Path | None = None) -> dict:
    """Restore the previous managed core-skill generation from its hash-checked backup."""
    dest = skill_dir(host, scope, project, home)
    _assert_no_symlink_ancestors(dest)
    if not dest.is_dir():
        raise ValueError("No managed host installation exists")
    with host_lock(dest):
        recovered = recover_host_files(dest)
        manifest_file = dest / ".kstack-managed.json"
        if host_transaction_pending(dest):
            raise ValueError("Interrupted host transaction could not be recovered")
        current = read_json(manifest_file, None)
        generation = current.get("generation") if isinstance(current, dict) else None
        if not isinstance(generation, str) or len(generation) != 32 or any(c not in "0123456789abcdef" for c in generation):
            raise ValueError("Current install has no retained rollback generation")
        snapshot = dest / ".kstack-generations" / generation
        _assert_no_symlink_ancestors(snapshot)
        if is_link_or_junction(snapshot) or not snapshot.is_dir():
            raise ValueError("Previous host generation backup is missing")
        generation_record = snapshot / "generation.json"
        if is_link_or_junction(generation_record):
            raise ValueError("Host generation record cannot be a symlink")
        record = read_json(generation_record, {})
        if (not isinstance(record, dict) or record.get("format") != 1
                or record.get("generation") != generation or not isinstance(record.get("entries"), list)):
            raise ValueError("Previous host generation backup is invalid")
        changes: dict[str, bytes | None] = {}
        seen = set()
        for entry in record["entries"]:
            if not isinstance(entry, dict) or set(entry) != {"path", "old_sha256", "old_mode", "new_sha256"}:
                raise ValueError("Invalid previous host generation entry")
            rel = entry["path"]
            if (not isinstance(rel, str) or rel in seen or rel.startswith("/") or "\\" in rel
                    or any(part in ("", ".", "..") for part in rel.split("/"))):
                raise ValueError("Invalid previous host generation path")
            seen.add(rel)
            for key in ("old_sha256", "new_sha256"):
                value = entry[key]
                if value is not None and (not isinstance(value, str) or len(value) != 64
                                          or any(c not in "0123456789abcdef" for c in value)):
                    raise ValueError("Invalid previous host generation hash")
            target = dest / rel
            _assert_no_symlink_ancestors(target)
            if is_link_or_junction(target):
                raise ValueError(f"Managed target became a symlink: {rel}")
            current_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.is_file() else None
            if current_hash != entry["new_sha256"]:
                raise ValueError(f"Host file changed since generation; refusing rollback: {rel}")
            old_hash = entry["old_sha256"]
            if old_hash is None:
                changes[rel] = None
            else:
                backup = snapshot / "backup" / rel
                _assert_no_symlink_ancestors(backup)
                if is_link_or_junction(backup) or not backup.is_file():
                    raise ValueError(f"Previous host file backup is missing: {rel}")
                data = backup.read_bytes()
                if hashlib.sha256(data).hexdigest() != old_hash:
                    raise ValueError(f"Previous host file backup is corrupt: {rel}")
                changes[rel] = data
        manifest_bytes = changes.get(manifest_file.name)
        if manifest_file.name not in changes:
            raise ValueError("Install generation has no manifest commit marker")
        rollback_generation = uuid.uuid4().hex
        if manifest_bytes is not None:
            prior = json.loads(manifest_bytes.decode("utf-8"))
            if not isinstance(prior, dict) or not isinstance(prior.get("files"), dict):
                raise ValueError("Previous install manifest backup is invalid")
            prior = {**prior, "version": 3, "generation": rollback_generation,
                     "previous_generation": generation}
            changes[manifest_file.name] = json.dumps(prior, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        transaction = commit_host_files(dest, changes, generation=rollback_generation, retain_backup=True)
        return {"rolled_back": True, "host": host, "scope": scope,
                "restored_generation": generation, "transaction": transaction,
                "recovered_interrupted_generation": recovered["recovered"]}

def uninstall(host: str, scope: str, project: Path | None = None, home: Path | None = None,
              dry_run: bool = False) -> dict:
    dest = skill_dir(host, scope, project, home)
    manifest_file = dest / ".kstack-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    if dry_run:
        return _uninstall_locked(host, scope, project, home, dest, dry_run=True)
    if not dest.exists():
        return {"destination": str(dest), "dry_run": False, "removed": [],
                "transaction": {"committed": False, "files_changed": 0}}
    with host_lock(dest):
        recovered = recover_host_files(dest)
        result = _uninstall_locked(host, scope, project, home, dest)
        result["recovered_interrupted_generation"] = recovered["recovered"]
        return result


def _uninstall_locked(host: str, scope: str, project: Path | None, home: Path | None,
                      dest: Path, dry_run: bool = False) -> dict:
    manifest_file = dest / ".kstack-managed.json"
    _assert_no_symlink_ancestors(manifest_file)
    if host_transaction_pending(dest):
        raise ValueError("Interrupted host transaction exists; run recover-install before uninstalling")
    manifest = read_json(manifest_file, {"files": {}})
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), dict):
        raise ValueError("Invalid install manifest")
    files = manifest.get("files", {})
    # Preflight all files to ensure no half-uninstall on conflict.
    for relative, stored_hash in files.items():
        name, sep, filename = relative.partition("/")
        if not sep or filename != "SKILL.md" or not NAME.fullmatch(name):
            raise ValueError("Invalid managed manifest path")
        target = dest / name / "SKILL.md"
        if is_link_or_junction(target) or is_link_or_junction(target.parent):
            raise ValueError("Managed target became symlink")
        if target.exists() and digest(target.read_text(encoding="utf-8")) != stored_hash:
            raise ValueError("Managed skill locally modified; refusing uninstall")
    removed = []
    mutations: dict[str, None] = {}
    for relative in files:
        target = dest / relative
        if target.exists():
            removed.append(str(target))
            mutations[relative] = None
    if manifest_file.exists():
        mutations[manifest_file.name] = None
    transaction = commit_host_files(dest, mutations) if not dry_run and mutations else None
    return {"destination": str(dest), "dry_run": dry_run, "removed": removed,
            "transaction": transaction}


def doctor(root: Path, state: Path, host: str | None = None, scope: str = "global",
           project: Path | None = None, home: Path | None = None) -> dict:
    checks = []
    for name, content in bundled_skills(root).items():
        checks.append({"check": "bundled:" + name, "ok": bool(parse_skill(content))})
    for name, content in available_skills(root, state).items():
        checks.append({"check": "available:" + name, "ok": bool(parse_skill(content))})
    if host:
        location = skill_dir(host, scope, project, home)
        if host_transaction_pending(location):
            checks.append({"check": "host:no_interrupted_install", "ok": False})
            return {"ok": False, "checks": checks,
                    "note": "An interrupted host installation needs recovery before integrity can be checked."}
        manifest_path = location / ".kstack-managed.json"
        if not manifest_path.is_file() or is_link_or_junction(manifest_path):
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
            ok = path.is_file() and not is_link_or_junction(path) and digest(path.read_text(encoding="utf-8")) == expected_hash
            checks.append({"check": "installed:" + rel, "ok": ok})
        from .external import list_external
        external = list_external(host, scope, project, home)
        checks.append({"check": "host:external_packages", "ok": external["ok"]})
    return {"ok": all(item["ok"] for item in checks), "checks": checks,
            "note": "File presence and integrity do not prove an agent loaded or obeyed a skill."}
