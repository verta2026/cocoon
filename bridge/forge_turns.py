"""Generic forge turn-boundary helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClosedTurnSelection:
    kept: list[dict]
    trimmed_tail: list[dict]
    warnings: list[str]
    terminal_type_before_trim: str | None
    terminal_type: str | None


def has_text_content(event: dict) -> bool:
    content = (event.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(isinstance(block, dict) and block.get("type") == "text" for block in content)
    return False


def close_at_final_assistant(events: list[dict], *, allow_open_turn: bool = False) -> ClosedTurnSelection:
    """Close the window at the last assistant event that carries text.

    Tool-use-only assistant tails are not safe resume boundaries. Returning the
    trimmed tail lets callers replay real user messages instead of dropping
    them silently.
    """
    terminal_type_before_trim = events[-1].get("type") if events else None
    last_assistant = None
    for index in range(len(events) - 1, -1, -1):
        if events[index].get("type") == "assistant" and has_text_content(events[index]):
            last_assistant = index
            break
    if last_assistant is None:
        raise ValueError("no text-bearing assistant message found in kept history")

    warnings = []
    kept = events
    trimmed_tail = list(events[last_assistant + 1 :])
    if trimmed_tail:
        warnings.append(
            f"trimmed {len(trimmed_tail)} trailing event(s) after final assistant text; "
            f"previous terminal type was {terminal_type_before_trim}"
        )
        if allow_open_turn:
            warnings.append("allow_open_turn was provided, but trailing events were still trimmed for resume safety")
        kept = events[: last_assistant + 1]
    terminal_type = kept[-1].get("type") if kept else None
    return ClosedTurnSelection(kept, trimmed_tail, warnings, terminal_type_before_trim, terminal_type)
