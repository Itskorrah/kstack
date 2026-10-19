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
from .security import parse_skill, SHA, NAME
from .state import read_json, write_json

MAX_FILES = 150
MAX_BYTES = 3_000_000


def _git(source: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(source), *args], capture_output=True, text=True,
                         timeout=15, check=False, env={k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT", "WINDIR")})
    if run.returncode:
        raise ValueError("Local source is not a usable Git checkout: " + " ".join(args))
    return run.stdout.strip()


def inspect_package(source: Path, relative: str, expected_commit: str) -> dict:
    source = source.expanduser().resolve()
    if not source.is_dir() or not SHA.fullmatch(expected_commit):
        raise ValueError("Existing source directory and exact Git commit required")
    actual = _git(source, "rev-parse", "HEAD")
    if actual != expected_commit:
        raise ValueError("Checkout HEAD differs from approved commit")
    if _git(source, "status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Checkout contains modified or untracked files; review a clean pinned checkout")
    parts = Path(relative).parts
    if (not parts or any(p in ("", ".", "..") for p in parts) or relative.startswith("/")
            or "\\" in relative or parts[-1] == "SKILL.md"):
        raise ValueError("Expected a relative skill directory")
    directory = source.joinpath(*parts)
    if not directory.is_dir() or directory.is_symlink() or not directory.resolve().is_relative_to(source):
        raise ValueError("Invalid skill directory")
    skill = directory / "SKILL.md"
    if not skill.is_file() or skill.is_symlink():
        raise ValueError("Expected ordinary SKILL.md")
    name = parse_skill(skill.read_text(encoding="utf-8"))["name"]
    files = {}
    total = 0
    tracked = set(_git(source, "ls-files", "--cached").splitlines())
    for entry in sorted(directory.rglob("*")):
        if entry.is_symlink():
            raise ValueError("Symbolic links are not supported in approved skill packages")
        if not entry.is_file():
            continue
        if not entry.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Package path escaped root")
        rel_from_checkout = entry.relative_to(source).as_posix()
        if rel_from_checkout not in tracked:
            raise ValueError("Package includes untracked file")
        rel = entry.relative_to(directory).as_posix()
        size = entry.stat().st_size
        total += size
        if len(files) >= MAX_FILES or total > MAX_BYTES:
            raise ValueError("Skill package exceeds safety/resource limits")
        files[rel] = hashlib.sha256(entry.read_bytes()).hexdigest()
    has_code = any(not path.lower().endswith((".md", ".txt", ".json", ".yaml", ".yml")) for path in files)
    return {"name": name, "source": str(source), "relative": relative, "commit": actual,
            "files": files, "contains_code_or_assets": has_code, "bytes": total}


def install_package(source: Path, relative: str, expected_commit: str, host: str, scope: str,
                    project: Path | None = None, home: Path | None = None, *, dry_run: bool = True,
                    reviewed: bool = False, allow_code: bool = False) -> dict:
    package = inspect_package(source, relative, expected_commit)
    if not reviewed and not dry_run:
        raise ValueError("Explicit --reviewed required: verify provenance, licence and trust before installation")
    if package["contains_code_or_assets"] and not allow_code and not dry_run:
        raise ValueError("Contains non-documentation resources: --allow-code required after manual review")
    dest = skill_dir(host, scope, project, home)
    target_dir = dest / package["name"]
    _assert_no_symlink_ancestors(target_dir)
    manifest_file = dest / ".kstack-external-managed.json"
    prior = read_json(manifest_file, {"version": 1, "packages": {}})
    if not isinstance(prior, dict) or not isinstance(prior.get("packages"), dict):
        raise ValueError("Invalid external skill install manifest")
    managed = prior["packages"].get(package["name"])
    if managed and managed.get("files") != package["files"]:
        raise ValueError("Existing external package differs; uninstall old version before changing it")
    # Core KStack's manifest has priority; never overwrite its managed skill.
    if package["name"] in read_json(dest / ".kstack-managed.json", {"files": {}}).get("files", {}):
        raise ValueError("Name belongs to KStack's bundled skill")
    core = read_json(dest / ".kstack-managed.json", {"files": {}})["files"]
    if any(x.startswith(package["name"] + "/") for x in core):
        raise ValueError("Name collision with KStack-managed skill")
    for rel, checksum in package["files"].items():
        target = target_dir / rel
        _assert_no_symlink_ancestors(target)
        if target.is_symlink():
            raise ValueError("Refusing symlink target")
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
            raise ValueError("Existing content conflicts with proposed package")
    if target_dir.exists() and not managed:
        if any(x for x in target_dir.rglob("*") if x.is_file() and x.relative_to(target_dir).as_posix() not in package["files"]):
            raise ValueError("Unmanaged files exist in target directory")
    if not dry_run:
        for rel in package["files"]:
            target = target_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            src = source / relative / rel
            # Stable byte copy; no shell invocation or downloaded code execution.
            data = src.read_bytes()
            if hashlib.sha256(data).hexdigest() != package["files"][rel]:
                raise ValueError("Source changed during installation")
            from tempfile import mkstemp
            fd, tmp = mkstemp(prefix=".kstack-ext-", dir=target.parent)
            try:
                with os.fdopen(fd, "wb") as output:
                    output.write(data)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(tmp, target)
            finally:
                if os.path.lexists(tmp):
                    os.unlink(tmp)
        prior["packages"][package["name"]] = {
            "source": str(source), "relative": relative, "commit": expected_commit,
            "files": package["files"], "reviewed": True, "contains_code_or_assets": package["contains_code_or_assets"]}
        write_json(manifest_file, prior)
    return {**package, "destination": str(target_dir), "dry_run": dry_run,
            "installed": not dry_run, "note": "Package copied but real host invocation is not verified"}


def list_external(host: str, scope: str, project: Path | None = None, home: Path | None = None) -> dict:
    dest = skill_dir(host, scope, project, home)
    packages = read_json(dest / ".kstack-external-managed.json", {"packages": {}}).get("packages", {})
    reports = []
    for name, record in packages.items():
        folder = dest / name
        status = "installed"
        for rel, sha in record.get("files", {}).items():
            file = folder / rel
            if not file.is_file() or file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != sha:
                status = "modified_or_missing"
                break
        reports.append({"name": name, "status": status, "commit": record["commit"], "contains_code_or_assets": record["contains_code_or_assets"]})
    return {"packages": reports, "ok": all(x["status"] == "installed" for x in reports)}
