"""Pre-delivery evidence policy. Plans only; never silently mutates GitHub.

A host-specific GitHub write adapter must be introduced separately, with
explicit per-task user authorisation and independent remote-state verification.
"""
from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path
from .security import SHA, valid_repo
from .state import read_json
from .evidence import inspect as inspect_evidence


def _git_bytes(root: Path, *argv: str) -> bytes | None:
    try:
        answer = subprocess.run(["git", "-C", str(root), "-c", "core.fsmonitor=false", *argv], capture_output=True,
                                timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return answer.stdout if answer.returncode == 0 else None


def _worktree_fingerprint(root: Path, status: bytes, has_head: bool) -> str | None:
    """Hash Git-visible changes and their working-file contents without storing them."""
    if has_head:
        commands = (
            (b"diff-head", ("diff", "--no-ext-diff", "--no-textconv", "--raw", "--no-renames", "HEAD", "--")),
            (b"diff-index", ("diff", "--no-ext-diff", "--no-textconv", "--cached", "--raw", "--no-renames", "HEAD", "--")),
            (b"diff-worktree", ("diff", "--no-ext-diff", "--no-textconv", "--raw", "--no-renames", "--")),
            (b"paths-head", ("diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "--no-renames", "HEAD", "--")),
            (b"paths-index", ("diff", "--no-ext-diff", "--no-textconv", "--cached", "--name-only", "-z", "--no-renames", "HEAD", "--")),
            (b"paths-worktree", ("diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "--no-renames", "--")),
            (b"untracked", ("ls-files", "--others", "--exclude-standard", "-z")),
        )
    else:
        # An initialized repository can have staged and untracked files before
        # its first commit. Keep those checks meaningful without a HEAD ref.
        commands = (
            (b"diff-index", ("diff", "--no-ext-diff", "--no-textconv", "--cached", "--raw", "--no-renames", "--")),
            (b"diff-worktree", ("diff", "--no-ext-diff", "--no-textconv", "--raw", "--no-renames", "--")),
            (b"paths-index", ("diff", "--no-ext-diff", "--no-textconv", "--cached", "--name-only", "-z", "--no-renames", "--")),
            (b"paths-worktree", ("diff", "--no-ext-diff", "--no-textconv", "--name-only", "-z", "--no-renames", "--")),
            (b"untracked", ("ls-files", "--others", "--exclude-standard", "-z")),
        )
    values = [(b"status", status)]
    paths: set[bytes] = set()
    for label, argv in commands:
        output = _git_bytes(root, *argv)
        if output is None:
            return None
        values.append((label, output))
        if label.startswith(b"paths-") or label == b"untracked":
            paths.update(name for name in output.split(b"\0") if name)

    digest = hashlib.sha256()
    for label, value in values:
        digest.update(label + b"\0" + len(value).to_bytes(8, "big") + value)

    for name in sorted(paths):
        relative = os.fsdecode(name)
        parts = relative.replace("\\", "/").split("/")
        if not relative or relative.startswith(("/", "\\")) or any(part in ("", ".", "..") for part in parts):
            return None
        path = root.joinpath(*parts)
        current = path.parent
        while current != root and current != current.parent:
            try:
                parent_info = os.lstat(current)
            except OSError:
                return None
            if (stat.S_ISLNK(parent_info.st_mode)
                    or getattr(parent_info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
                return None
            current = current.parent
        digest.update(b"path\0" + len(name).to_bytes(8, "big") + name)
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            digest.update(b"missing\0")
            continue
        except OSError:
            return None
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISLNK(info.st_mode):
            try:
                target = os.fsencode(os.readlink(path))
            except OSError:
                return None
            digest.update(b"symlink\0" + mode.to_bytes(4, "big") + len(target).to_bytes(8, "big") + target)
        elif stat.S_ISREG(info.st_mode):
            file_digest = hashlib.sha256()
            try:
                with path.open("rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        return None
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        file_digest.update(chunk)
                    after = os.fstat(stream.fileno())
                current_info = os.lstat(path)
            except OSError:
                return None
            def identity(item):
                return (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns,
                        stat.S_IMODE(item.st_mode))
            if (not stat.S_ISREG(current_info.st_mode)
                    or identity(info) != identity(after)
                    or identity(info) != identity(current_info)):
                return None
            digest.update(b"file\0" + mode.to_bytes(4, "big") + info.st_size.to_bytes(8, "big") + file_digest.digest())
        else:
            # Modified submodules and special files need a dedicated recursive
            # fingerprint. Do not claim stability when their contents are opaque.
            return None
    return digest.hexdigest()


def git_snapshot(project: Path) -> dict:
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project directory does not exist")
    def run(*argv):
        try:
            answer = subprocess.run(["git", "-C", str(root), "-c", "core.fsmonitor=false", *argv], capture_output=True,
                                    text=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return answer.stdout.strip() if answer.returncode == 0 else None
    commit = run("rev-parse", "HEAD")
    worktree = _git_bytes(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    available = bool(commit and SHA.fullmatch(commit))
    return {"commit": commit if commit and SHA.fullmatch(commit) else None,
            "clean": worktree == b"" if worktree is not None else False,
            "branch": run("branch", "--show-current"),
            "git_available": available,
            "worktree_sha256": _worktree_fingerprint(root, worktree, available) if worktree is not None else None}


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
