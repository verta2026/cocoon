"""Generic Claude jsonl helpers for forge-style session handoff."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass

from bridge.summary import content_text, event_role, is_channel_event, is_runtime_noise


ASSISTANT_BLOCKS = {"thinking", "redacted_thinking", "text"}
USER_BLOCKS = {"text"}


@dataclass(frozen=True)
class RetainSelection:
    kept: list[dict]
    raw_cut_index: int
    keep_start_index: int
    estimated_tokens_scanned: int


def content_blocks(content) -> list[str]:
    if isinstance(content, str):
        return ["string"] if content.strip() else []
    if isinstance(content, list):
        return [block.get("type") for block in content if isinstance(block, dict)]
    return []


def sanitize_content(role: str, content):
    if isinstance(content, str):
        return content if content.strip() else None
    if not isinstance(content, list):
        return None
    allowed = ASSISTANT_BLOCKS if role == "assistant" else USER_BLOCKS
    kept = []
    for block in content:
        if isinstance(block, dict) and block.get("type") in allowed:
            kept.append(copy.deepcopy(block))
    return kept or None


def sanitize_event(event: dict) -> dict | None:
    if event.get("type") not in {"user", "assistant"}:
        return None
    if event.get("isMeta") is True and not is_channel_event(event):
        return None

    role = event_role(event)
    if role not in {"user", "assistant"}:
        return None
    if event.get("type") != role:
        return None

    message = event.get("message")
    if not isinstance(message, dict):
        return None
    content = sanitize_content(role, message.get("content"))
    if content is None:
        return None
    if role == "assistant" and is_runtime_noise(role, content):
        return None

    clean = copy.deepcopy(event)
    clean["message"]["content"] = content
    clean["message"].pop("usage", None)
    clean["message"].pop("diagnostics", None)
    clean.pop("requestId", None)
    return clean


def is_runtime_noise_event(event: dict) -> bool:
    message = event.get("message") or {}
    return is_runtime_noise(event_role(event), message.get("content"))


def filter_runtime_noise_turns(events: list[dict]) -> list[dict]:
    filtered = []
    skip_assistant_replies = False
    for event in events:
        if event.get("type") == "user":
            if is_runtime_noise_event(event):
                skip_assistant_replies = True
                continue
            skip_assistant_replies = False
        elif skip_assistant_replies and event.get("type") == "assistant":
            continue
        filtered.append(event)
    return filtered


def sanitize_events(rows: list[dict]) -> list[dict]:
    sanitized = [event for event in (sanitize_event(row) for row in rows) if event is not None]
    return filter_runtime_noise_turns(sanitized)


def is_real_user(event: dict) -> bool:
    if event.get("type") != "user" or event_role(event) != "user":
        return False
    if event.get("isMeta") is True and not is_channel_event(event):
        return False
    message = event.get("message") or {}
    blocks = content_blocks(message.get("content"))
    return any(block_type in {"string", "text"} for block_type in blocks)


def estimate_tokens(event: dict) -> int:
    return max(1, len(json.dumps(event, ensure_ascii=False, separators=(",", ":"))) // 3)


def event_text(event: dict) -> str:
    message = event.get("message") or {}
    return content_text(message.get("content")).strip()


def choose_kept(
    events: list[dict],
    retain_tokens: int,
    *,
    token_estimator: Callable[[dict], int] = estimate_tokens,
) -> RetainSelection:
    accumulated = 0
    raw_cut_index = 0
    for index in range(len(events) - 1, -1, -1):
        accumulated += token_estimator(events[index])
        if accumulated > retain_tokens:
            raw_cut_index = index + 1
            break

    keep_start_index = None
    for index in range(raw_cut_index, len(events)):
        if is_real_user(events[index]):
            keep_start_index = index
            break
    if keep_start_index is None:
        raise ValueError("no real user message found after cut point")

    return RetainSelection(
        kept=events[keep_start_index:],
        raw_cut_index=raw_cut_index,
        keep_start_index=keep_start_index,
        estimated_tokens_scanned=accumulated,
    )
