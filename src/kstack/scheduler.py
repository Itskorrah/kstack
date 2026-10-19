"""External-scheduler-friendly weekly maintenance eligibility.

No daemon, hidden background process, or claimed recurring job. Call from
launchd, Task Scheduler or another approved host scheduler.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo
from pathlib import Path
from .state import read_json, write_json

ZONE = "Australia/Sydney"


def eligibility(state: Path, *, now: dt.datetime | None = None) -> dict:
    clock = now or dt.datetime.now(dt.timezone.utc)
    if clock.tzinfo is None:
        raise ValueError("Scheduler clock requires an explicit timezone")
    local = clock.astimezone(ZoneInfo(ZONE))
    monday = (local.date() - dt.timedelta(days=local.weekday())).isoformat()
    previous = read_json(state / "maintenance-schedule.json", {})
    eligible = previous.get("week_start") != monday
    month = local.strftime("%Y-%m")
    return {"eligible": eligible, "week_start": monday, "local_time": local.isoformat(),
            "month": month, "monthly_deep_review": previous.get("last_monthly_review") != month,
            "reason": "not yet checked this calendar week" if eligible else "already checked this calendar week"}


def mark_run(state: Path, week: str, *, outcome: str, errors: list | None = None) -> dict:
    if outcome not in ("completed", "blocked", "partial"):
        raise ValueError("Unrecognised maintenance outcome")
    if not __import__("re").fullmatch(r"\d{4}-\d{2}-\d{2}", week):
        raise ValueError("Invalid week key")
    previous = read_json(state / "maintenance-schedule.json", {})
    # Weekly summary runs can mark a monthly review only when an actual review is
    # supplied by the calling workflow. Discovery alone never counts as one.
    details = {"week_start": week, "outcome": outcome, "errors": errors or [],
               "last_monthly_review": previous.get("last_monthly_review")}
    # A blocked attempt is recorded but may be retried by invoking --force.
    write_json(state / "maintenance-schedule.json", details)
    return details
