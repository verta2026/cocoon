"""Generic forge window construction helpers."""

from __future__ import annotations

from bridge.forge_plan_core import choose_kept, is_real_user, repair_tool_pairs
from bridge.forge_sanitize import clean_events, sanitize_event
from bridge.forge_turns import has_text_content


def build_window(
    rows: list[dict],
    raw_tokens: int,
    dialogue_tokens: int,
    assistant_blocks: set[str],
    user_blocks: set[str],
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
    raw_grow_factor: float = 1.5,
) -> dict:
    clean = clean_events(rows, assistant_prefixes, user_markers)
    raw_kept, _, raw_start, raw_scanned = choose_kept(
        clean,
        raw_tokens,
        grow_backward_limit=int(raw_tokens * raw_grow_factor),
    )
    head = clean[:raw_start]
    sanitized_head = [
        event
        for event in (
            sanitize_event(row, assistant_blocks, user_blocks, assistant_prefixes)
            for row in head
        )
        if event is not None
    ]
    dialogue_kept, _, dialogue_start, _ = choose_kept(sanitized_head, dialogue_tokens)
    grew_backward = False
    if not raw_kept and not dialogue_kept:
        for index in range(len(sanitized_head) - 1, -1, -1):
            if is_real_user(sanitized_head[index]):
                dialogue_kept = sanitized_head[index:]
                dialogue_start = index
                grew_backward = True
                break
    kept, repairs = repair_tool_pairs(dialogue_kept + raw_kept)
    return {
        "kept": kept,
        "dropped": sanitized_head[:dialogue_start],
        "clean_events": len(clean),
        "raw_zone_events": len(raw_kept),
        "raw_start_index": raw_start,
        "raw_scanned_tokens": raw_scanned,
        "dialogue_zone_events": len(dialogue_kept),
        "dialogue_start_index": dialogue_start,
        "tool_pair_repairs": repairs,
        "grew_backward": grew_backward,
    }


def window_is_viable(window: dict) -> bool:
    kept = window["kept"]
    has_user = any(event.get("type") == "user" for event in kept)
    has_assistant_text = any(
        event.get("type") == "assistant" and has_text_content(event)
        for event in kept
    )
    return has_user and has_assistant_text
