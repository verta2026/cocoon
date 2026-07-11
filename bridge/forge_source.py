"""Generic forge source selection helpers."""

from __future__ import annotations

from pathlib import Path

from bridge.forge_session_files import iter_project_jsonl, load_jsonl, session_sort_key
from bridge.forge_window import build_window, window_is_viable


def build_source_window(
    source: str | Path,
    retain_tokens: int,
    dialogue_tokens: int,
    assistant_blocks: set[str],
    user_blocks: set[str],
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
) -> tuple[list[dict], dict]:
    rows = load_jsonl(Path(source))
    window = build_window(
        rows,
        retain_tokens,
        dialogue_tokens,
        assistant_blocks,
        user_blocks,
        assistant_prefixes,
        user_markers,
    )
    return rows, window


def select_forge_source(
    *,
    source: str | Path | None,
    project_dir: str | Path,
    retain_tokens: int,
    dialogue_tokens: int,
    assistant_blocks: set[str],
    user_blocks: set[str],
    assistant_prefixes: tuple[str, ...] = (),
    user_markers: tuple[str, ...] = (),
) -> tuple[Path, list[dict], dict, list[dict]]:
    if source:
        source_path = Path(source)
        rows, window = build_source_window(
            source_path,
            retain_tokens,
            dialogue_tokens,
            assistant_blocks,
            user_blocks,
            assistant_prefixes,
            user_markers,
        )
        if not window["kept"]:
            raise ValueError("no user/assistant text-bearing events found")
        return source_path, rows, window, []

    skipped = []
    candidates = sorted(
        iter_project_jsonl(Path(project_dir)),
        key=session_sort_key,
        reverse=True,
    )
    for candidate in candidates:
        rows, window = build_source_window(
            candidate,
            retain_tokens,
            dialogue_tokens,
            assistant_blocks,
            user_blocks,
            assistant_prefixes,
            user_markers,
        )
        if window_is_viable(window):
            return candidate, rows, window, skipped
        skipped.append(
            {
                "path": str(candidate),
                "clean_events": window["clean_events"],
                "reason": "no user + text-bearing assistant pair in kept window",
            }
        )

    raise ValueError("no forgeable session found with user and assistant text-bearing events")
