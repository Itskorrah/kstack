"""Portable approved-skill lockfile and verified import, without credentials."""
from __future__ import annotations

import json
from pathlib import Path
from .security import SHA, digest, NAME, valid_repo, valid_path, parse_skill
from .state import read_json, write_json

FORMAT = 1


def export_lock(state: Path, target: Path, *, dry_run: bool = True) -> dict:
    active = read_json(state / "active.json", {})
    records = []
    for ident, data in sorted(active.items()):
        sha = data["content_sha256"]
        file = state / "objects" / (sha + ".md")
        if not file.is_file() or file.is_symlink() or digest(file.read_text(encoding="utf-8")) != sha:
            raise ValueError("Approved skill object missing/corrupt: " + ident)
        valid_repo(data["repository"])
        valid_path(data["path"])
        if not SHA.fullmatch(data["commit"]) or not NAME.fullmatch(data["name"]):
            raise ValueError("Invalid approved-skill provenance")
        records.append({"id": ident, "name": data["name"], "repository": data["repository"],
                        "path": data["path"], "commit": data["commit"], "content_sha256": sha})
    lock = {"format": FORMAT, "skills": records}
    if not dry_run:
        if target.is_symlink() or target.exists():
            raise ValueError("Destination exists; refusing overwrite")
        write_json(target, lock)
    return {"ok": True, "dry_run": dry_run, "destination": str(target), "lock": lock,
            "note": "This manifest contains no skill bodies. A receiving machine needs the approved objects separately."}


def inspect_lock(path: Path, state: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("skills"), list):
        raise ValueError("Unsupported KStack lockfile format")
    names = set()
    status = []
    for skill in data["skills"]:
        if not isinstance(skill, dict) or set(skill) != {"id", "name", "repository", "path", "commit", "content_sha256"}:
            raise ValueError("Malformed lockfile entry")
        name = skill["name"]
        repo = valid_repo(skill["repository"])
        path_in_repo = valid_path(skill["path"])
        if skill["id"] != f"{repo}:{path_in_repo}" or name in names or not NAME.fullmatch(name):
            raise ValueError("Invalid or duplicated skill identity")
        names.add(name)
        if not SHA.fullmatch(skill["commit"]) or not __import__("re").fullmatch("[a-f0-9]{64}", skill["content_sha256"]):
            raise ValueError("Invalid pinned reference or content hash")
        target = state / "objects" / (skill["content_sha256"] + ".md")
        present = target.is_file() and not target.is_symlink()
        valid = present and digest(target.read_text(encoding="utf-8")) == skill["content_sha256"]
        if valid and parse_skill(target.read_text(encoding="utf-8"))["name"] != name:
            valid = False
        status.append({"id": skill["id"], "object_verified": valid})
    return {"ok": all(x["object_verified"] for x in status), "skills": status,
            "note": "Lockfile inspection never installs or auto-promotes skills."}
