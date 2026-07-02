"""Generic web-push subscription state helpers."""

from __future__ import annotations

from typing import Any


def push_status_payload(*, public_key: str | None, subscriptions: list[dict[str, Any]], last: Any) -> dict[str, Any]:
    """Build the public push status payload without exposing key material."""
    return {
        "vapid": bool(public_key),
        "subscriptions": len(subscriptions),
        "last": last,
    }


def upsert_subscription(
    subscriptions: list[dict[str, Any]],
    subscription: dict[str, Any],
    *,
    now: float,
) -> list[dict[str, Any]]:
    """Insert or update one subscription by endpoint, preserving created_at."""
    endpoint = subscription.get("endpoint")
    if not endpoint:
        raise ValueError("invalid subscription")
    updated = [dict(item) for item in subscriptions]
    incoming = dict(subscription)
    incoming["updated_at"] = now
    existing = next((i for i, item in enumerate(updated) if item.get("endpoint") == endpoint), None)
    if existing is None:
        incoming["created_at"] = now
        updated.append(incoming)
    else:
        incoming["created_at"] = updated[existing].get("created_at", now)
        updated[existing] = incoming
    return updated


def remove_subscription(subscriptions: list[dict[str, Any]], endpoint: str) -> list[dict[str, Any]]:
    """Remove subscriptions matching an endpoint."""
    if not endpoint:
        raise ValueError("invalid subscription")
    return [dict(item) for item in subscriptions if item.get("endpoint") != endpoint]


def missing_vapid_record(*, now: float, attempted: int) -> dict[str, Any]:
    """Build a last-push record for a missing VAPID configuration."""
    return {
        "ts": now,
        "attempted": attempted,
        "sent": 0,
        "error": "missing vapid",
    }


def push_delivery_record(
    *,
    now: float,
    attempted: int,
    sent: int,
    kept: int,
    errors: list[str],
    max_errors: int = 5,
) -> dict[str, Any]:
    """Build a last-push delivery result record."""
    return {
        "ts": now,
        "attempted": attempted,
        "sent": sent,
        "kept": kept,
        "errors": errors[-max_errors:],
    }
