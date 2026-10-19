"""Deterministic candidate lifecycle: discover -> review -> stage -> promote -> rollback.

Never executes remotely sourced skills. No probabilistic scores are represented
as proofs of safety, capability or performance.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from .github_api import GitHubAPI
from .security import SHA, screen, digest, parse_skill, valid_repo, valid_path
from .state import read_json, write_json

UTC = dt.timezone.utc

def stamp():
    return dt.datetime.now(UTC).isoformat(timespec="seconds")


def load_config(root: Path) -> tuple[dict, dict]:
    return read_json(root / "data" / "policy.json", {}), read_json(root / "data" / "watchlist.json", {})


def candidate_id(repo: str, path: str) -> str:
    valid_repo(repo)
    valid_path(path)
    return f"{repo}:{path}"


def relevance(description: str, interests: list[str]) -> int:
    value = description.lower()
    return min(20, 5 * sum(1 for tag in interests if tag.lower() in value))


def analyse(content: str, policy: dict, repo: str, path: str, tree: list[dict], current_names: set[str]) -> dict:
    """Preliminary text-only score. Agent assessment still required to auto-promote."""
    meta = parse_skill(content)
    folder = path.rsplit("/", 1)[0] + "/"
    files = [f.get("path", "") for f in tree if f.get("type") == "blob" and f.get("path", "").startswith(folder)]
    flags = screen(content, [f[len(folder):] for f in files])
    body = content.split("\n---\n", 1)[1]
    headings = re.findall(r"(?m)^#{1,3} [A-Za-z]", body)
    steps = re.findall(r"(?m)^\s*(?:\d+\.|[-*])\s+\S", body)
    verification = bool(re.search(r"verify|test|check|evidence|validation", body, re.I))
    controls = bool(re.search(r"scope|permission|approval|fallback|limit|boundary", body, re.I))
    score = (
        min(20, 8 + len(meta["description"]) // 30)
        + min(20, len(headings) * 4 + len(steps) * 2)
        + (20 if verification else 0)
        + (20 if controls else 0)
        + relevance(meta["description"] + " " + body[:1000], policy.get("interests", []))
    )
    score = min(100, score)
    duplicate = meta["name"] in current_names
    reasons = []
    if duplicate:
        reasons.append("skill name already active: requires deliberate replacement")
    if flags:
        reasons.extend(flags)
    if repo.split("/")[0].lower() not in {x.lower() for x in policy.get("trusted_owners", [])}:
        reasons.append("publisher is not in the explicit trusted-owner list")
    if len(files) > policy.get("max_package_files", 12):
        reasons.append("too many package files")
    if len(files) != 1 or files[0] != path:
        reasons.append("auto promotion restricted to single-file Markdown skills")
    return {"name": meta["name"], "description": meta["description"], "preliminary_score": score,
            "screening_flags": flags, "blockers": reasons, "package_files": files,
            "content_sha256": digest(content), "screening_only": True}


def discover(api: GitHubAPI, watchlist: dict, state: Path, max_candidates: int = 50) -> dict:
    """Scan pinned GitHub repo snapshots, not arbitrary user supplied URLs."""
    if max_candidates < 1 or max_candidates > 250:
        raise ValueError("max_candidates must be 1..250")
    existing = read_json(state / "candidates.json", {})
    changes = []
    errors = []
    for source in watchlist.get("sources", []):
        repo = valid_repo(source["repository"])
        roots = source.get("paths", ["skills/"])
        try:
            info = api.repository(repo)
            if info.get("archived") or info.get("disabled"):
                continue
            commit = api.head(repo, info.get("default_branch") or "main")
            tree = api.tree(repo, commit)
            matches = sorted(x["path"] for x in tree if x.get("type") == "blob"
                             and x.get("path", "").endswith("/SKILL.md")
                             and any(x["path"].startswith(p) for p in roots))
            for path in matches:
                if len(changes) >= max_candidates:
                    break
                ident = candidate_id(repo, path)
                previous = existing.get(ident, {})
                if previous.get("commit") == commit:
                    continue
                # Content not trusted or executed. Candidates are immutable refs.
                existing[ident] = {"id": ident, "repository": repo, "path": path,
                                   "commit": commit, "status": "discovered", "discovered_at": stamp()}
                changes.append(ident)
        except (ValueError, KeyError, RuntimeError) as exc:
            errors.append({"repository": repo, "error": str(exc)[:200]})
        if len(changes) >= max_candidates:
            break
    write_json(state / "candidates.json", existing)
    write_json(state / "last-discovery.json", {"when": stamp(), "changed": changes, "errors": errors})
    return {"changed": changes, "errors": errors, "total_known": len(existing)}


def assess(api: GitHubAPI, policy: dict, state: Path, ident: str, current_names: set[str]) -> dict:
    records = read_json(state / "candidates.json", {})
    if ident not in records:
        raise KeyError("Unknown candidate; discover first")
    item = records[ident]
    repo, path, commit = item["repository"], item["path"], item["commit"]
    tree = api.tree(repo, commit)
    if not any(x.get("path") == path and x.get("type") == "blob" for x in tree):
        raise ValueError("Candidate is not in the pinned commit")
    content = api.skill(repo, path, commit)
    evaluation = analyse(content, policy, repo, path, tree, current_names)
    object_key = evaluation["content_sha256"]
    # Store only the reviewed Markdown; no remote script is copied or run.
    obj = state / "objects" / (object_key + ".md")
    if obj.exists() and digest(obj.read_text(encoding="utf-8")) != object_key:
        raise ValueError("Object store integrity violation")
    obj.parent.mkdir(parents=True, exist_ok=True)
    if not obj.exists():
        if obj.is_symlink():
            raise ValueError("Refusing symlink object")
        from .installer import atomic_text
        atomic_text(obj, content)
    item.update(evaluation)
    item["status"] = "quarantined" if item["blockers"] else "assessed"
    item["assessed_at"] = stamp()
    records[ident] = item
    write_json(state / "candidates.json", records)
    return item


def validate_review(review: dict, item: dict, policy: dict) -> list[str]:
    errors = []
    if review.get("id") != item["id"] or review.get("content_sha256") != item.get("content_sha256"):
        errors.append("review not bound to candidate and exact content")
    for field in ("engineering_quality", "project_relevance", "novelty", "security_confidence"):
        val = review.get(field)
        if type(val) is not int or val < 0 or val > 100:
            errors.append(f"invalid independent assessment: {field}")
    evidence = review.get("evidence", [])
    if not isinstance(evidence, list) or len(evidence) < 2 or any(not isinstance(e, str) or len(e.strip()) < 24 for e in evidence):
        errors.append("at least two substantive evidence statements required")
    if review.get("tested_in_sandbox") is not True:
        errors.append("isolated skill activation rehearsal not attested")
    if not review.get("test_report") or len(str(review["test_report"])) < 20:
        errors.append("specific rehearsal result required")
    if review.get("reviewer", "").strip() in ("", "automated-text-scorer"):
        errors.append("named independent reviewer required")
    if not errors:
        weighted = round(0.35 * review["engineering_quality"] + 0.35 * review["project_relevance"]
                         + 0.15 * review["novelty"] + 0.15 * review["security_confidence"])
        if weighted < policy.get("auto_promote_min_review", 92):
            errors.append(f"review rating {weighted} below high-autonomy threshold")
        if review["security_confidence"] < 95:
            errors.append("security confidence below 95")
    return errors


def promote(state: Path, policy: dict, ident: str, review: dict, autonomous: bool = False) -> dict:
    records = read_json(state / "candidates.json", {})
    if ident not in records:
        raise KeyError("Candidate not discovered")
    item = records[ident]
    if item.get("blockers"):
        raise ValueError("Promotion blocked: " + "; ".join(item["blockers"]))
    if not SHA.fullmatch(item.get("commit", "")):
        raise ValueError("Missing immutable source commit")
    if autonomous and not policy.get("high_autonomy", False):
        raise ValueError("Autonomous promotion disabled by policy")
    findings = validate_review(review, item, policy)
    if findings:
        raise ValueError("Promotion blocked: " + "; ".join(findings))
    object_file = state / "objects" / (item["content_sha256"] + ".md")
    if object_file.is_symlink() or not object_file.is_file() or digest(object_file.read_text(encoding="utf-8")) != item["content_sha256"]:
        raise ValueError("Pinned skill object missing or modified")
    active = read_json(state / "active.json", {})
    existing_names = {v["name"] for k, v in active.items() if k != ident}
    if item["name"] in existing_names:
        raise ValueError("Name collision with active skill")
    history = read_json(state / "history.json", [])
    # Atomic manifest update, with a stored previous generation.
    snapshots = state / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    version = len(history) + 1
    write_json(snapshots / f"{version:06d}.json", active)
    active[ident] = {"name": item["name"], "repository": item["repository"], "path": item["path"],
                     "commit": item["commit"], "content_sha256": item["content_sha256"],
                     "promoted_at": stamp(), "reviewer": review["reviewer"]}
    write_json(state / "active.json", active)
    history.append({"version": version, "when": stamp(), "action": "auto-promote" if autonomous else "promote", "id": ident})
    write_json(state / "history.json", history)
    return active[ident]


def rollback(state: Path, version: int) -> dict:
    snapshot = state / "snapshots" / f"{version:06d}.json"
    previous = read_json(snapshot, None)
    if previous is None or not isinstance(previous, dict):
        raise ValueError("Unknown rollback snapshot")
    for data in previous.values():
        obj = state / "objects" / (data["content_sha256"] + ".md")
        if obj.is_symlink() or not obj.is_file() or digest(obj.read_text(encoding="utf-8")) != data["content_sha256"]:
            raise ValueError("Cannot restore missing or altered skill")
    current = read_json(state / "active.json", {})
    history = read_json(state / "history.json", [])
    next_number = len(history) + 1
    write_json(state / "snapshots" / f"{next_number:06d}.json", current)
    write_json(state / "active.json", previous)
    history.append({"version": next_number, "when": stamp(), "action": "rollback", "to_snapshot": version})
    write_json(state / "history.json", history)
    return previous


def report(state: Path) -> dict:
    candidates = read_json(state / "candidates.json", {})
    active = read_json(state / "active.json", {})
    return {"generated_at": stamp(), "active_external": active, "candidate_counts": {
        x: sum(c.get("status") == x for c in candidates.values()) for x in ("discovered", "assessed", "quarantined")
    }, "last_discovery": read_json(state / "last-discovery.json", {}),
        "review_required": [k for k, c in candidates.items() if c.get("status") in ("assessed", "quarantined") and k not in active],
        "limitations": ["No model or agent is executed by the KStack CLI.",
                        "Text screening is not a malware/security certification.",
                        "Remote agent/host integration has not been accepted until tested on that host."]}
