#!/usr/bin/env python3
"""Run KStack maintenance once when invoked by an external OS scheduler.

No external skill code is executed; network reads are limited to the GitHub
watchlist via the existing CLI. No auto-promotion unless independently supplied
and verified review documents are explicitly passed to the CLI elsewhere.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from kstack.scheduler import eligibility, mark_run
from kstack.state import app_state, lock_state
from kstack.engine import discover, load_config
from kstack.github_api import GitHubAPI
from kstack.queue import queue


def main(argv=None, api=None) -> int:
    parser = argparse.ArgumentParser(description="KStack weekly watchlist discovery; external scheduler required")
    parser.add_argument("--state", type=Path, default=Path.home() / ".kstack")
    parser.add_argument("--run", action="store_true", help="Perform network-backed scan, not merely show schedule")
    parser.add_argument("--force", action="store_true", help="Ignore already-checked week")
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args(argv)
    state = app_state(str(args.state))
    due = eligibility(state)
    if not args.run:
        print(json.dumps({"execution": "not_started", "schedule": due, "queue": queue(state)}, indent=2))
        return 0
    if not due["eligible"] and not args.force:
        print(json.dumps({"execution": "skipped", "schedule": due}))
        return 0
    root = Path(__file__).resolve().parents[2]
    with lock_state(state):
        from kstack.transaction import recover
        recover(state)
        _policy, watch = load_config(root)
        report = discover(api or GitHubAPI(), watch, state, args.limit)
        # Never record a network failure as successful weekly coverage; the
        # monthly in-depth review remains pending until actually performed.
        result = "completed" if not report["errors"] else "partial"
        mark_run(state, due["week_start"], outcome=result, errors=report["errors"])
        print(json.dumps({"execution": "ran", "outcome": result, "discovery": report,
                          "queue": queue(state), "schedule": due}, indent=2))
        return 0 if result == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
