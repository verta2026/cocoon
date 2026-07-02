"""Generic forge event sanitization helpers."""

from __future__ import annotations

import copy

from bridge.forge_plan_core import is_channel_message, role_of


def sanitize_content(role: str, content, assistant_blocks: set[str], user_blocks: set[str]):
    if isinstance(content, str):
        return content if content.strip() else None
    if not isinstance(content, list):
        return None
    allowed = assistant_blocks if role == "assistant" else user_blocks
    kept = []
    for block in content:
        if isinstance(block, dict) and block.get("type") in allowed:
            kept.append(copy.deepcopy(block))
    return kept or None


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def is_runtime_noise(
    role: str | None,
    content,
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
) -> bool:
    text = content_text(content).strip()
    if role == "assistant":
        return any(text.startswith(prefix) for prefix in assistant_prefixes)
    if role == "user":
        return any(marker in text for marker in user_markers)
    return False


def is_runtime_noise_event(
    event: dict,
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
) -> bool:
    message = event.get("message") or {}
    return is_runtime_noise(role_of(event), message.get("content"), assistant_prefixes, user_markers)


def filter_runtime_noise_turns(
    events: list[dict],
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
) -> list[dict]:
    filtered = []
    skip_assistant_replies = False
    for event in events:
        if event.get("type") == "user":
            if is_runtime_noise_event(event, assistant_prefixes, user_markers):
                skip_assistant_replies = True
                continue
            skip_assistant_replies = False
        elif skip_assistant_replies and event.get("type") == "assistant":
            continue
        filtered.append(event)
    return filtered


def sanitize_event(
    event: dict,
    assistant_blocks: set[str],
    user_blocks: set[str],
    assistant_prefixes: tuple[str, ...] = (),
) -> dict | None:
    if event.get("type") not in {"user", "assistant"}:
        return None
    if event.get("isMeta") is True and not is_channel_message(event):
        return None
    role = role_of(event)
    if role not in {"user", "assistant"}:
        return None
    if event.get("type") != role:
        return None
    message = event.get("message")
    if not isinstance(message, dict):
        return None
    content = sanitize_content(role, message.get("content"), assistant_blocks, user_blocks)
    if content is None:
        return None
    if role == "assistant" and is_runtime_noise(role, content, assistant_prefixes, ()):
        return None

    clean = copy.deepcopy(event)
    clean["message"]["content"] = content
    clean["message"].pop("usage", None)
    clean["message"].pop("diagnostics", None)
    clean.pop("requestId", None)
    return clean


def sanitize_events(
    rows: list[dict],
    assistant_blocks: set[str],
    user_blocks: set[str],
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
) -> list[dict]:
    sanitized = [
        event
        for event in (sanitize_event(row, assistant_blocks, user_blocks, assistant_prefixes) for row in rows)
        if event is not None
    ]
    return filter_runtime_noise_turns(sanitized, assistant_prefixes, user_markers)
