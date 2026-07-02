"""Generic forge summary injection helpers."""

from __future__ import annotations

import copy
from datetime import datetime, timezone


def synthetic_summary_event(summary_text: str, template: dict, marker: str) -> dict:
    new_event = copy.deepcopy(template) if isinstance(template, dict) else {}
    now = datetime.now(timezone.utc).isoformat()
    text = (
        f"{marker}\n"
        "This is an internal cumulative handoff summary produced before forge truncation. "
        "Treat it as prior conversation context, not as a new user request.\n\n"
        f"{summary_text.strip()}"
    )
    new_event.update(
        {
            "type": "user",
            "isMeta": False,
            "timestamp": now,
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }
    )
    new_event.pop("requestId", None)
    return new_event


def inject_summary_event(kept: list[dict], summary_text: str, marker: str) -> tuple[list[dict], bool]:
    if not summary_text.strip() or not kept:
        return kept, False
    template = next((event for event in kept if event.get("type") == "user"), kept[0])
    return [synthetic_summary_event(summary_text, template, marker)] + kept, True
