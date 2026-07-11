"""Pick which Claude Code session JSONL the web UI mirrors.

Claude Code writes one JSONL per session into the project directory. "Newest
mtime wins" is wrong the moment a second Claude session runs in the same
workdir (e.g. the user also opens `claude` in a terminal): the web UI would
silently switch to — and archive — someone else's conversation. Selection is
therefore sticky: once a file is picked it stays picked until the file
disappears or cocoon itself (re)launches Claude.

Limitation: a relaunch done by hand inside the tmux pane (not through any
cocoon route) does not reset the pin; every cocoon-driven launch path must
call :func:`mark_session_launch`.
"""

from __future__ import annotations

import time


def new_pick_state() -> dict:
    return {"pinned": None, "launch_ts": 0.0}


def mark_session_launch(state: dict, now: float | None = None) -> None:
    """Record that cocoon just (re)launched Claude; the next pick re-binds."""
    state["launch_ts"] = time.time() if now is None else now
    state["pinned"] = None


def pick_session_jsonl(candidates, state: dict):
    """Choose the session file from ``candidates`` (iterable of (path, mtime)).

    - A pinned file that is still present always wins, regardless of other
      files' mtimes.
    - After a launch, the newest file written at/after ``launch_ts`` gets
      pinned. Until one appears (the new session's file can take a few
      seconds to materialise), fall back to the newest file *without*
      pinning, so the next poll can still bind to the right one.
    """
    files = {}
    for path, mtime in candidates:
        files[str(path)] = mtime
    pinned = state.get("pinned")
    if pinned and pinned in files:
        return pinned
    state["pinned"] = None
    if not files:
        return None
    launch_ts = state.get("launch_ts") or 0.0
    post_launch = {p: m for p, m in files.items() if m >= launch_ts}
    if post_launch:
        best = max(post_launch, key=post_launch.get)
        state["pinned"] = best
        return best
    return max(files, key=files.get)
