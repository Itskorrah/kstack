"""KStack local-first CLI. State-changing commands are explicitly identified."""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path

from .engine import discover, assess, promote, rollback, report, load_config
from .github_api import GitHubAPI
from .installer import install, uninstall, doctor, bundled_skills, available_skills
from .router import route
from .state import app_state, read_json, lock_state
from .project import inspect_project, bootstrap
from .verification import verify_project
from .evidence import inspect as evidence_status
from .external import install_package, list_external

ROOT = Path(__file__).resolve().parents[2]
_MUTATORS = {"scan", "assess", "promote", "rollback", "install", "uninstall", "maintenance", "bootstrap", "verify-project", "external-install"}


def parser():
    ap = argparse.ArgumentParser(prog="kstack", description="Reproducible developer skills and evidence-based maintenance")
    ap.add_argument("--state", help="Local state directory (default: ~/.kstack)")
    ap.add_argument("--root", type=Path, default=ROOT, help="KStack source checkout")
    sp = ap.add_subparsers(dest="command", required=True)
    for name in ("list", "status", "scan", "assess", "promote", "rollback", "install", "uninstall", "doctor", "route",
                 "maintenance", "inspect-project", "bootstrap", "verify-project", "evidence", "external-install", "external-list"):
        cmd = sp.add_parser(name)
        if name in {"scan", "maintenance"}:
            cmd.add_argument("--limit", type=int, default=30 if name == "maintenance" else 50)
        if name in ("assess", "promote"):
            cmd.add_argument("id", help="owner/repository:path/to/SKILL.md")
        if name == "promote":
            cmd.add_argument("--review", type=Path, required=True)
            cmd.add_argument("--autonomous", action="store_true")
        if name == "rollback":
            cmd.add_argument("snapshot", type=int)
        if name in {"install", "uninstall", "doctor", "external-install", "external-list"}:
            cmd.add_argument("--host", choices=["codex", "claude"], required=name != "doctor")
            cmd.add_argument("--scope", choices=["project", "global"], default="global")
            cmd.add_argument("--project", type=Path)
            if name in {"install", "uninstall"}:
                cmd.add_argument("--dry-run", action="store_true")
            if name == "install":
                cmd.add_argument("--bundled-only", action="store_true")
        if name == "external-install":
            cmd.add_argument("--source", type=Path, required=True, help="Clean local Git checkout")
            cmd.add_argument("--skill-dir", required=True, help="Relative folder containing SKILL.md")
            cmd.add_argument("--commit", required=True, help="Exact approved 40-digit Git commit")
            cmd.add_argument("--apply", action="store_true", help="Actually install; preview by default")
            cmd.add_argument("--reviewed", action="store_true", help="Attest a genuine manual code/provenance review")
            cmd.add_argument("--allow-code", action="store_true", help="Allow copying code/assets after manual review")
        if name in {"route", "inspect-project", "bootstrap", "verify-project"}:
            if name == "route":
                cmd.add_argument("task")
                cmd.add_argument("--profile", default="general")
                cmd.add_argument("--project", type=Path)
            else:
                cmd.add_argument("--project", type=Path, required=True)
        if name == "bootstrap":
            cmd.add_argument("--apply", action="store_true")
        if name == "verify-project":
            cmd.add_argument("--run", action="store_true")
            cmd.add_argument("--timeout", type=int, default=120)
        if name == "maintenance":
            cmd.add_argument("--apply", action="store_true")
            cmd.add_argument("--reviews", type=Path)
    return ap


def command(args, root: Path, state: Path, api=None):
    policy, watchlist = load_config(root)
    if args.command == "list":
        directory = root / "data"
        if not directory.is_dir():
            directory = Path(__file__).parent / "bundled" / "data"
        return {"bundled": sorted(bundled_skills(root)), "active": read_json(state / "active.json", {}),
                "integrations": read_json(directory / "integrations.json", [])}
    if args.command == "status":
        return {**report(state), "evidence": evidence_status(state)}
    if args.command == "scan":
        return discover(api or GitHubAPI(), watchlist, state, args.limit)
    if args.command == "assess":
        names = set(available_skills(root, state))
        owned = read_json(state / "active.json", {}).get(args.id)
        if owned:
            names.discard(owned["name"])
        return assess(api or GitHubAPI(), policy, state, args.id, names)
    if args.command == "promote":
        return promote(state, policy, args.id, json.loads(args.review.read_text(encoding="utf-8")), args.autonomous)
    if args.command == "rollback":
        return rollback(state, args.snapshot)
    if args.command == "install":
        return install(root, state, args.host, args.scope, args.project, with_external=not args.bundled_only, dry_run=args.dry_run)
    if args.command == "uninstall":
        return uninstall(args.host, args.scope, args.project, dry_run=args.dry_run)
    if args.command == "doctor":
        return doctor(root, state, args.host, args.scope, args.project)
    if args.command == "route":
        return route(args.task, root, state, args.profile, args.project)
    if args.command == "inspect-project":
        return inspect_project(args.project)
    if args.command == "bootstrap":
        return bootstrap(args.project, dry_run=not args.apply)
    if args.command == "verify-project":
        return verify_project(args.project, state, timeout=args.timeout, apply=args.run)
    if args.command == "evidence":
        return evidence_status(state)
    if args.command == "external-install":
        return install_package(args.source, args.skill_dir, args.commit, args.host, args.scope, args.project,
                               dry_run=not args.apply, reviewed=args.reviewed, allow_code=args.allow_code)
    if args.command == "external-list":
        return list_external(args.host, args.scope, args.project)
    if args.command == "maintenance":
        answer = {"discovery": discover(api or GitHubAPI(), watchlist, state, args.limit),
                  "assessed": [], "promoted": [], "blocked": []}
        for ident, item in read_json(state / "candidates.json", {}).items():
            if item["status"] == "discovered":
                try:
                    names = set(available_skills(root, state))
                    owned = read_json(state / "active.json", {}).get(ident)
                    if owned:
                        names.discard(owned["name"])
                    analysed = assess(api or GitHubAPI(), policy, state, ident, names)
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
        return answer
    raise AssertionError(args.command)


def main(argv=None, api=None):
    args = parser().parse_args(argv)
    root = args.root.resolve()
    state = app_state(args.state)
    try:
        # Explicit dry-run commands never mutate; offline read-only checks don't require locks.
        writing = args.command in _MUTATORS
        if args.command == "bootstrap" and not args.apply:
            writing = False
        if args.command == "verify-project" and not args.run:
            writing = False
        if args.command == "external-install" and not args.apply:
            writing = False
        if args.command in ("install", "uninstall") and args.dry_run:
            writing = False
        with lock_state(state) if writing else nullcontext():
            answer = command(args, root, state, api)
        print(json.dumps(answer, indent=2, ensure_ascii=False, sort_keys=True))
        return 0 if not isinstance(answer, dict) or answer.get("ok", True) else 1
    except (ValueError, RuntimeError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "command": args.command}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
