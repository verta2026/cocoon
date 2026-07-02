"""Generic forge turn-boundary helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClosedTurnSelection:
    kept: list[dict]
    warnings: list[str]
    terminal_type_before_trim: str | None
    terminal_type: str | None


def close_at_final_assistant(events: list[dict], *, allow_open_turn: bool = False) -> ClosedTurnSelection:
    terminal_type_before_trim = events[-1].get("type") if events else None
    last_assistant = None
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("type") == "assistant":
            last_assistant = index
            break
    if last_assistant is None:
        raise ValueError("no assistant message found in kept history")

    warnings = []
    kept = events
    if last_assistant != len(events) - 1:
        trailing = len(events) - last_assistant - 1
        warnings.append(
            f"trimmed {trailing} trailing non-assistant event(s) after final assistant; "
            f"previous terminal type was {terminal_type_before_trim}"
        )
        if allow_open_turn:
            warnings.append("allow_open_turn was provided, but trailing events were still trimmed for resume safety")
        kept = events[: last_assistant + 1]
    terminal_type = kept[-1].get("type") if kept else None
    return ClosedTurnSelection(kept, warnings, terminal_type_before_trim, terminal_type)
