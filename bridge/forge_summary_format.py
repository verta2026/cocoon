"""Generic summary input formatting helpers for forge reload."""

from __future__ import annotations

from bridge.forge_plan_core import is_channel_message, role_of
from bridge.forge_sanitize import content_text, is_runtime_noise


def event_timestamp(event: dict) -> str:
    return event.get("timestamp") or event.get("created_at") or ""


def event_speaker(
    event: dict,
    assistant_name: str = "assistant",
    user_name: str = "user",
    channel_name: str = "channel",
) -> str:
    role = role_of(event)
    if role == "assistant":
        return assistant_name
    if is_channel_message(event):
        return channel_name
    if role == "user":
        return user_name
    return role or "unknown"


def clamp_middle(
    text: str | None,
    max_chars: int,
    omitted_template: str = "[... omitted {omitted} chars from the middle ...]",
) -> str:
    text = text or ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(text) - head - tail
    return (
        text[:head].rstrip()
        + "\n\n"
        + omitted_template.format(omitted=omitted)
        + "\n\n"
        + text[-tail:].lstrip()
    )


def format_events_for_summary(
    events: list[dict],
    max_chars: int,
    *,
    assistant_name: str = "assistant",
    user_name: str = "user",
    channel_name: str = "channel",
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
    omitted_template: str = "[... omitted {omitted} chars from the middle ...]",
) -> str:
    lines = []
    for event in events:
        message = event.get("message") or {}
        role = role_of(event)
        content = message.get("content")
        if is_runtime_noise(role, content, assistant_prefixes, user_markers):
            continue
        text = content_text(content).strip()
        if not text:
            continue
        timestamp = event_timestamp(event)
        speaker = event_speaker(event, assistant_name, user_name, channel_name)
        heading = f"[{timestamp}] {speaker}" if timestamp else speaker
        lines.append(f"{heading}:\n{text}")
    return clamp_middle("\n\n".join(lines).strip(), max_chars, omitted_template)
