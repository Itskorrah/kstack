"""CLI entry point. Network access is only performed by explicitly invoked scan/assess."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import discover, assess, promote, rollback, report, load_config
from .github_api import GitHubAPI
from .installer import install, uninstall, doctor, bundled_skills, available_skills
from .router import route
from .state import app_state, read_json

ROOT = Path(__file__).resolve().parents[2]


def parser():
    ap = argparse.ArgumentParser(prog="kstack", description="Versioned developer skill stack; network-free by default")
    ap.add_argument("--state", help="Local state directory (defaults to ~/.kstack)")
    ap.add_argument("--root", type=Path, default=ROOT, help="KStack source checkout")
    sp = ap.add_subparsers(dest="command", required=True)
    for name in ("list", "status", "scan", "assess", "promote", "rollback", "install", "uninstall", "doctor", "route", "maintenance"):
        cmd = sp.add_parser(name)
        if name == "scan":
            cmd.add_argument("--limit", type=int, default=50)
        if name in ("assess", "promote"):
            cmd.add_argument("id", help="owner/repository:path/to/SKILL.md")
        if name == "promote":
            cmd.add_argument("--review", type=Path, required=True, help="Independent evidence review JSON file")
            cmd.add_argument("--autonomous", action="store_true", help="Apply the high-autonomy promotion policy")
        if name == "rollback":
            cmd.add_argument("snapshot", type=int)
        if name in ("install", "uninstall", "doctor"):
            cmd.add_argument("--host", choices=["codex", "claude"], required=name != "doctor")
            cmd.add_argument("--scope", choices=["project", "global"], default="global")
            cmd.add_argument("--project", type=Path)
            if name != "doctor":
                cmd.add_argument("--dry-run", action="store_true")
            if name == "install":
                cmd.add_argument("--bundled-only", action="store_true")
        if name == "route":
            cmd.add_argument("task")
            cmd.add_argument("--profile", default="general")
        if name == "maintenance":
            cmd.add_argument("--apply", action="store_true", help="Assess and promote only qualifying reviewed candidates")
            cmd.add_argument("--reviews", type=Path, help="Folder of independently produced JSON assessments")
            cmd.add_argument("--limit", type=int, default=30)
    return ap


def main(argv=None, api=None):
    args = parser().parse_args(argv)
    root = args.root.resolve()
    state = app_state(args.state)
    policy, watchlist = load_config(root)
    try:
        if args.command == "list":
            answer = {"bundled": sorted(bundled_skills(root)), "active": read_json(state / "active.json", {}),
                      "integrations": read_json(root / "data" / "integrations.json", [])}
        elif args.command == "status":
            answer = report(state)
        elif args.command == "scan":
            answer = discover(api or GitHubAPI(), watchlist, state, args.limit)
        elif args.command == "assess":
            names = set(available_skills(root, state))
            answer = assess(api or GitHubAPI(), policy, state, args.id, names)
        elif args.command == "promote":
            answer = promote(state, policy, args.id, json.loads(args.review.read_text(encoding="utf-8")), args.autonomous)
        elif args.command == "rollback":
            answer = rollback(state, args.snapshot)
        elif args.command == "install":
            answer = install(root, state, args.host, args.scope, args.project, with_external=not args.bundled_only, dry_run=args.dry_run)
        elif args.command == "uninstall":
            answer = uninstall(args.host, args.scope, args.project, dry_run=args.dry_run)
        elif args.command == "doctor":
            answer = doctor(root, state, args.host, args.scope, args.project)
        elif args.command == "route":
            answer = route(args.task, root, state, args.profile)
        elif args.command == "maintenance":
            answer = {"discovery": discover(api or GitHubAPI(), watchlist, state, args.limit), "assessed": [], "promoted": [], "blocked": []}
            for ident, item in read_json(state / "candidates.json", {}).items():
                if item["status"] == "discovered":
                    try:
                        analysed = assess(api or GitHubAPI(), policy, state, ident, set(available_skills(root, state)))
                        answer["assessed"].append({"id": ident, "preliminary_score": analysed["preliminary_score"]})
                    except (ValueError, RuntimeError, KeyError) as exc:
                        answer["blocked"].append({"id": ident, "reason": str(exc)})
            if args.apply and args.reviews:
                for review_file in sorted(args.reviews.glob("*.json")):
                    try:
                        review = json.loads(review_file.read_text(encoding="utf-8"))
                        item = promote(state, policy, review["id"], review, autonomous=True)
                        answer["promoted"].append(item["name"])
                    except (ValueError, KeyError, json.JSONDecodeError, OSError) as exc:
                        answer["blocked"].append({"file": review_file.name, "reason": str(exc)})
        else:
            raise AssertionError(args.command)
        print(json.dumps(answer, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if not isinstance(answer, dict) or answer.get("ok", True) else 1
    except (ValueError, RuntimeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}), file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
