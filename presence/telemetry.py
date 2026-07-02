"""Generic telemetry helpers for presence-style status endpoints."""

from __future__ import annotations

import datetime
import time
from typing import Any


def with_age(data: dict[str, Any] | None, *, now: float | None = None, stale_after: int | None = None) -> dict[str, Any] | None:
    """Return a copy with age_seconds and optional stale flag."""
    if not data:
        return data
    current = time.time() if now is None else now
    result = dict(data)
    age = int(current - result.get("ts", 0))
    result["age_seconds"] = age
    if stale_after is not None:
        result["stale"] = age > stale_after
    return result


def format_duration(seconds: int) -> str:
    """Format seconds as Xm or XhYYm."""
    hours, minutes = divmod(seconds // 60, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def usage_payload(usage: dict[str, Any] | None, *, date: str) -> dict[str, Any]:
    """Build the public screentime usage payload."""
    if not usage or not usage.get("apps"):
        return {"status": "no data yet", "date": date}
    apps = usage["apps"]
    sorted_apps = sorted(apps.items(), key=lambda item: item[1]["seconds"], reverse=True)
    formatted = []
    total = 0
    for pkg, info in sorted_apps:
        seconds = info["seconds"]
        total += seconds
        formatted.append({
            "app": pkg,
            "label": info["label"],
            "time": format_duration(seconds),
            "seconds": seconds,
        })
    return {
        "date": usage.get("date", date),
        "total": format_duration(total),
        "total_seconds": total,
        "apps": formatted,
    }


def update_usage_record(
    usage: dict[str, Any] | None,
    *,
    app: str,
    label: str,
    seconds: int,
    date: str,
    now: float | None = None,
) -> dict[str, Any]:
    """Return an updated daily usage record."""
    current = time.time() if now is None else now
    record = usage or {"date": date, "apps": {}}
    if record.get("date") != date:
        record = {"date": date, "apps": {}}
    apps = dict(record.get("apps") or {})
    app_info = dict(apps.get(app) or {"label": label or app, "seconds": 0})
    app_info["seconds"] = app_info.get("seconds", 0) + seconds
    if label and label != app:
        app_info["label"] = label
    apps[app] = app_info
    record = dict(record)
    record["apps"] = apps
    record["last_updated"] = current
    return record


def old_usage_filenames(filenames: list[str], *, now: datetime.datetime | None = None, keep_days: int = 3) -> list[str]:
    """Return dated usage JSON filenames older than the retention window."""
    current = datetime.datetime.now() if now is None else now
    cutoff = current - datetime.timedelta(days=keep_days)
    old = []
    for filename in filenames:
        if not filename.endswith(".json"):
            continue
        try:
            usage_date = datetime.datetime.strptime(filename[:-5], "%Y-%m-%d")
        except ValueError:
            continue
        if usage_date < cutoff:
            old.append(filename)
    return old
