"""Generic forge summary injection helpers."""

from __future__ import annotations

import copy
from datetime import datetime, timezone


DEFAULT_SUMMARY_FLAG_FIELD = "forgeSummary"
DEFAULT_WRAPPER_TEMPLATE = (
    "<system-reminder>\n"
    "Earlier conversation memory, automatically prepared as background context. "
    "This is not a new user request.\n\n"
    "{summary}\n"
    "</system-reminder>"
)


def summary_body(summary_text: str, marker: str) -> str:
    body = summary_text.strip()
    if marker and body.startswith(marker):
        body = body[len(marker) :].strip()
    return body


def synthetic_summary_event(
    summary_text: str,
    template: dict,
    marker: str,
    *,
    flag_field: str = DEFAULT_SUMMARY_FLAG_FIELD,
    wrapper_template: str = DEFAULT_WRAPPER_TEMPLATE,
) -> dict:
    new_event = copy.deepcopy(template) if isinstance(template, dict) else {}
    now = datetime.now(timezone.utc).isoformat()
    text = wrapper_template.format(summary=summary_body(summary_text, marker))
    new_event.update(
        {
            "type": "user",
            "isMeta": False,
            flag_field: True,
            "timestamp": now,
            "message": {"role": "user", "content": [{"type": "text", "text": text}]},
        }
    )
    new_event.pop("requestId", None)
    return new_event


def inject_summary_event(
    kept: list[dict],
    summary_text: str,
    marker: str,
    *,
    flag_field: str = DEFAULT_SUMMARY_FLAG_FIELD,
    wrapper_template: str = DEFAULT_WRAPPER_TEMPLATE,
) -> tuple[list[dict], bool]:
    if not summary_text.strip() or not kept:
        return kept, False
    template = next((event for event in kept if event.get("type") == "user"), kept[0])
    return [
        synthetic_summary_event(
            summary_text,
            template,
            marker,
            flag_field=flag_field,
            wrapper_template=wrapper_template,
        )
    ] + kept, True
