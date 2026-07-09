"""Generic forge replay helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from bridge.forge_plan_core import is_real_user
from bridge.forge_sanitize import content_text


def replay_payload(
    trimmed_tail: list[dict],
    new_session_id: str,
    *,
    created_at: str | None = None,
) -> dict | None:
    messages = []
    for event in trimmed_tail:
        if not is_real_user(event):
            continue
        text = content_text((event.get("message") or {}).get("content"))
        if text.strip():
            messages.append({"timestamp": event.get("timestamp", ""), "text": text})
    if not messages:
        return None
    return {
        "new_sid": new_session_id,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "messages": messages,
    }
