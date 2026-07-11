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


_CJK_RANGES = (
    (0x3000, 0x30FF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0xFF00, 0xFFEF),
)


def estimate_tokens(event: dict) -> int:
    message = event.get("message")
    if isinstance(message, dict):
        text = json.dumps(message.get("content"), ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    cjk = sum(1 for char in text if any(low <= ord(char) <= high for low, high in _CJK_RANGES))
    return cjk + max(1, (len(text) - cjk) // 4) + 8


def choose_kept(
    events: list[dict],
    retain_tokens: int,
    grow_backward_limit: int | None = None,
) -> tuple[list[dict], int, int, int]:
    accumulated = 0
    cut = 0
    for index in range(len(events) - 1, -1, -1):
        accumulated += estimate_tokens(events[index])
        if accumulated > retain_tokens:
            cut = index + 1
            break

    keep_start = len(events)
    for index in range(cut, len(events)):
        if is_real_user(events[index]):
            keep_start = index
            break
    if keep_start == len(events) and grow_backward_limit:
        total = 0
        for index in range(len(events) - 1, -1, -1):
            total += estimate_tokens(events[index])
            if total > grow_backward_limit:
                break
            if is_real_user(events[index]):
                keep_start = index
        if keep_start < len(events):
            accumulated = sum(estimate_tokens(event) for event in events[keep_start:])
    return events[keep_start:], cut, keep_start, accumulated


def _drop_blocks(event: dict, block_ids: set[str], block_type: str) -> dict | None:
    content = (event.get("message") or {}).get("content")
    if not isinstance(content, list):
        return event
    kept = [
        block
        for block in content
        if not (
            isinstance(block, dict)
            and block.get("type") == block_type
            and block.get("id" if block_type == "tool_use" else "tool_use_id") in block_ids
        )
    ]
    if not kept:
        return None
    event["message"]["content"] = kept
    return event


def repair_tool_pairs(events: list[dict]) -> tuple[list[dict], int]:
    uses = {}
    results = set()
    for index, event in enumerate(events):
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                uses[block.get("id")] = index
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                if block.get("tool_use_id") in uses:
                    results.add(block.get("tool_use_id"))

    orphan_uses = {tool_id for tool_id in uses if tool_id not in results}
    orphan_results = set()
    seen_uses = set()
    for event in events:
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                seen_uses.add(block.get("id"))
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                if block.get("tool_use_id") not in seen_uses:
                    orphan_results.add(block.get("tool_use_id"))

    if not orphan_uses and not orphan_results:
        return events, 0

    repaired = []
    repairs = 0
    for event in events:
        content = (event.get("message") or {}).get("content")
        before = len(content) if isinstance(content, list) else -1
        new_event = event
        if orphan_uses and event.get("type") == "assistant":
            new_event = _drop_blocks(copy.deepcopy(event), orphan_uses, "tool_use")
        if new_event is not None and orphan_results and new_event.get("type") == "user":
            if new_event is event:
                new_event = copy.deepcopy(event)
            new_event = _drop_blocks(new_event, orphan_results, "tool_result")
        if new_event is None:
            repairs += 1
            continue
        after = len(new_event["message"]["content"]) if isinstance(new_event.get("message", {}).get("content"), list) else -1
        if after != before:
            repairs += 1
        repaired.append(new_event)
    return repaired, repairs


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
