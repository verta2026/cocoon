"""Generic forge event planning helpers."""

from __future__ import annotations

import copy
import json
import uuid
from collections.abc import Callable


def role_of(event: dict) -> str | None:
    message = event.get("message")
    return message.get("role") if isinstance(message, dict) else None


def content_blocks(content) -> list[str]:
    if isinstance(content, str):
        return ["string"] if content.strip() else []
    if isinstance(content, list):
        return [block.get("type") for block in content if isinstance(block, dict)]
    return []


def is_channel_message(event: dict) -> bool:
    message = event.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content", "")
    return isinstance(content, str) and "<channel source=" in content


def is_real_user(event: dict) -> bool:
    if event.get("type") != "user" or role_of(event) != "user":
        return False
    if event.get("isMeta") is True and not is_channel_message(event):
        return False
    message = event.get("message") or {}
    blocks = content_blocks(message.get("content"))
    return any(block_type in {"string", "text"} for block_type in blocks)


def estimate_tokens(event: dict) -> int:
    return max(1, len(json.dumps(event, ensure_ascii=False, separators=(",", ":"))) // 3)


def choose_kept(events: list[dict], retain_tokens: int) -> tuple[list[dict], int, int, int]:
    accumulated = 0
    cut = 0
    for index in range(len(events) - 1, -1, -1):
        accumulated += estimate_tokens(events[index])
        if accumulated > retain_tokens:
            cut = index + 1
            break
    keep_start = None
    for index in range(cut, len(events)):
        if is_real_user(events[index]):
            keep_start = index
            break
    if keep_start is None:
        # Autonomous stretches (tool work with no real user message inside the
        # retain window) must not disqualify the whole session: grow the window
        # backward to the last real user message instead of losing the newest
        # window entirely.
        for index in range(cut - 1, -1, -1):
            if is_real_user(events[index]):
                keep_start = index
                break
    if keep_start is None:
        raise ValueError("no real user message found in session")
    return events[keep_start:], cut, keep_start, accumulated


def forge_events(
    kept: list[dict],
    new_session_id: str,
    *,
    rewrite_event_uuids: bool = True,
    uuid_factory: Callable[[], str] | None = None,
) -> tuple[list[dict], dict[str, str]]:
    uuid_factory = uuid_factory or (lambda: str(uuid.uuid4()))
    forged = []
    previous_uuid = None
    uuid_map = {}
    for event in kept:
        new_event = copy.deepcopy(event)
        old_uuid = new_event.get("uuid")
        if rewrite_event_uuids or not old_uuid:
            new_uuid = uuid_factory()
            if old_uuid:
                uuid_map[old_uuid] = new_uuid
            new_event["uuid"] = new_uuid
        else:
            new_uuid = old_uuid
        new_event["sessionId"] = new_session_id
        new_event["parentUuid"] = previous_uuid
        previous_uuid = new_uuid
        forged.append(new_event)
    return forged, uuid_map


def validate_chain(events: list[dict]) -> None:
    seen = set()
    missing = []
    for index, event in enumerate(events):
        parent = event.get("parentUuid")
        event_uuid = event.get("uuid")
        if parent is not None and parent not in seen:
            missing.append({"index": index, "parentUuid": parent, "uuid": event_uuid})
        if event_uuid in seen:
            raise ValueError(f"duplicate uuid in forged events: {event_uuid}")
        seen.add(event_uuid)
    if missing:
        raise ValueError(f"forged chain has missing parents: {missing[:3]}")
