"""Generic forge report helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def count_thinking_blocks(events: list[dict]) -> int:
    count = 0
    for event in events:
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        count += sum(
            1
            for block in content
            if isinstance(block, dict) and block.get("type") in {"thinking", "redacted_thinking"}
        )
    return count


def build_forge_report(
    *,
    source: str | Path,
    new_sid: str,
    rows: list[dict],
    forged: list[dict],
    retained: list[dict],
    summary_injected: bool,
    summary_info: dict,
    window: dict,
    trimmed_tail: list[dict],
    replay: dict | None,
    terminal_type: str | None,
    warnings: list[str],
    skipped_candidates: list[dict] | None,
    token_estimator: Callable[[dict], int],
) -> dict:
    replay_messages = len(replay.get("messages") or []) if replay else 0
    return {
        "source": str(source),
        "new_sid": new_sid,
        "source_events": len(rows),
        "kept_events": len(forged),
        "retained_events": len(retained),
        "summary_injected": summary_injected,
        "summary_status": summary_info["status"],
        "summary_file": summary_info["file"],
        "summary_meta": summary_info["meta"],
        "summary_chars": summary_info["summary_chars"],
        "summary_dropped_events": summary_info["dropped_events"],
        "summary_dropped_chars": summary_info["dropped_chars"],
        "summary_provider": summary_info["provider"],
        "summary_prompt_file": summary_info["prompt_file"],
        "clean_events": window["clean_events"],
        "raw_zone_events": window["raw_zone_events"],
        "raw_start_index": window["raw_start_index"],
        "dialogue_zone_events": window["dialogue_zone_events"],
        "dialogue_start_index": window["dialogue_start_index"],
        "tool_pair_repairs": window["tool_pair_repairs"],
        "trimmed_tail_events": len(trimmed_tail),
        "replay_messages": replay_messages,
        "estimated_tokens_kept": sum(token_estimator(event) for event in forged),
        "terminal_type": terminal_type,
        "thinking_blocks_kept": count_thinking_blocks(forged),
        "warnings": list(warnings),
        "skipped_candidates": list(skipped_candidates or []),
        "written": False,
    }
