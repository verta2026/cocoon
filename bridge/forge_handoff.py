"""Generic forge handoff preparation helpers."""

from __future__ import annotations

from bridge.forge_replay import replay_payload
from bridge.forge_turns import close_at_final_assistant


def build_handoff_state(
    window: dict,
    skipped_candidates: list[dict],
    *,
    allow_open_turn: bool = False,
    replay_created_at: str | None = None,
) -> dict:
    selection = close_at_final_assistant(window["kept"], allow_open_turn=allow_open_turn)
    warnings = list(selection.warnings)
    if window.get("grew_backward"):
        warnings.append(
            "no real user message inside either zone budget; grew dialogue zone backward "
            f"to index {window['dialogue_start_index']} (over token budget) to avoid losing the session"
        )
    if window.get("tool_pair_repairs"):
        warnings.append(f"repaired {window['tool_pair_repairs']} event(s) with orphaned tool_use/tool_result blocks")
    if skipped_candidates:
        warnings.append(f"skipped {len(skipped_candidates)} newer candidate session(s); see skipped_candidates")

    replay = replay_payload(selection.trimmed_tail, "", created_at=replay_created_at)
    if replay:
        warnings.append(
            f"{len(replay['messages'])} real user message(s) trimmed after final assistant text; "
            "queued for replay into the new window"
        )

    return {
        "kept": selection.kept,
        "trimmed_tail": selection.trimmed_tail,
        "warnings": warnings,
        "terminal_type_before_trim": selection.terminal_type_before_trim,
        "terminal_type": selection.terminal_type,
        "replay": replay,
    }
