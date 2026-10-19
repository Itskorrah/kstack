"""Pre-delivery evidence policy. Plans only; never silently mutates GitHub.

A host-specific GitHub write adapter must be introduced separately, with
explicit per-task user authorisation and independent remote-state verification.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from .security import SHA, valid_repo
from .state import read_json
from .evidence import inspect as inspect_evidence


def git_snapshot(project: Path) -> dict:
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project directory does not exist")
    def run(*argv):
        try:
            answer = subprocess.run(["git", "-C", str(root), *argv], capture_output=True,
                                    text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return answer.stdout.strip() if answer.returncode == 0 else None
    commit = run("rev-parse", "HEAD")
    worktree = run("status", "--porcelain", "--untracked-files=normal")
    return {"commit": commit if commit and SHA.fullmatch(commit) else None,
            "clean": worktree == "" if worktree is not None else False,
            "branch": run("branch", "--show-current"),
            "git_available": bool(commit and SHA.fullmatch(commit))}


def delivery_readiness(project: Path, state: Path, repository: str, target_branch: str = "main",
                       authorised: bool = False) -> dict:
    valid_repo(repository)
    if (not target_branch or target_branch.startswith("/") or ".." in target_branch or
            any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._/" for c in target_branch)):
        raise ValueError("Invalid delivery target branch")
    current = git_snapshot(project)
    evidence = read_json(state / "evidence.json", [])
    integrity = inspect_evidence(state)
    relevant = [x for x in evidence if isinstance(x, dict) and x.get("kind") == "verification"
                and x.get("detail", {}).get("project") == str(Path(project).expanduser().resolve())
                and x.get("detail", {}).get("git_snapshot", {}).get("commit") == current["commit"]
                and x.get("detail", {}).get("ok") is True
                and x.get("detail", {}).get("git_snapshot", {}).get("clean") is True]
    reasons = []
    if not current["git_available"]:
        reasons.append("project Git revision unavailable")
    if not current["clean"]:
        reasons.append("project working tree is not clean")
    if not integrity.get("ok"):
        reasons.append("local evidence journal invalid")
    if not relevant:
        reasons.append("no successful fresh verification bound to the current clean Git revision")
    if not authorised:
        reasons.append("per-task GitHub delivery authorisation not granted")
    return {"ready_for_host_adapter": not reasons, "repository": repository,
            "target_branch": target_branch, "source": current,
            "verification_evidence_hash": relevant[-1].get("hash") if relevant else None,
            "blockers": reasons,
            "action": "none: advisory preflight only",
            "note": "Actual PR/merge still needs host API, remote branch/protection checks and post-merge verification."}
