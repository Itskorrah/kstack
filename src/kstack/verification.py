"""Run explicitly configured local project checks with limits and truthful evidence.

This is NOT a security sandbox. Only run commands controlled by the user or
trusted project owner, never command strings originating from candidate skills.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from .project import load_project_config
from .evidence import append


def verify_project(project: Path, state: Path, *, timeout: int = 120, apply: bool = False) -> dict:
    project = project.expanduser().resolve()
    if not 1 <= timeout <= 900:
        raise ValueError("Verification timeout must be between 1 and 900 seconds")
    config = load_project_config(project)
    commands = config.get("verification_commands", [])
    if not commands:
        return {"ok": False, "status": "not_configured", "commands": [],
                "message": "No trusted verification_commands configured in kstack.json"}
    if not apply:
        return {"ok": False, "status": "dry_run", "commands": commands,
                "message": "No commands executed; pass --run to execute trusted commands"}
    results = []
    # Restrict environment to common process essentials. This does not prevent
    # commands themselves from reading files; project commands must be trusted.
    safe = {key: value for key, value in os.environ.items()
            if key in {"PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "VIRTUAL_ENV"}}
    for argv in commands:
        if any("\x00" in a or len(a) > 4000 for a in argv):
            raise ValueError("Invalid verification command")
        started = time.monotonic()
        try:
            run = subprocess.run(argv, cwd=project, env=safe, shell=False, capture_output=True,
                                 text=True, errors="replace", timeout=timeout, check=False)
            item = {"executable": Path(argv[0]).name, "argv_sha256": hashlib.sha256(json.dumps(argv).encode()).hexdigest(), "argument_count": len(argv), "returncode": run.returncode, "status": "passed" if run.returncode == 0 else "failed",
                    "output_sha256": hashlib.sha256((run.stdout + run.stderr).encode()).hexdigest(),
                    "stdout_chars": len(run.stdout), "stderr_chars": len(run.stderr),
                    "output_redacted": True,
                    "elapsed_seconds": round(time.monotonic() - started, 3)}
        except subprocess.TimeoutExpired:
            item = {"executable": Path(argv[0]).name, "argument_count": len(argv), "status": "timeout", "elapsed_seconds": round(time.monotonic()-started, 3)}
        except OSError as exc:
            item = {"executable": Path(argv[0]).name, "argument_count": len(argv), "status": "blocked", "error": type(exc).__name__}
        results.append(item)
        if item["status"] != "passed":
            break
    from .delivery import git_snapshot
    snapshot = git_snapshot(project)
    answer = {"git_snapshot": snapshot, "ok": len(results) == len(commands) and all(x["status"] == "passed" for x in results),
              "status": "verified" if len(results) == len(commands) and all(x["status"] == "passed" for x in results) else "incomplete",
              "project": str(project), "commands": results}
    append(state, "verification", answer)
    return answer
