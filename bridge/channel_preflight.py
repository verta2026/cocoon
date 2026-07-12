"""Clean stale channel-plugin state before (re)launching Claude Code.

Channel plugins (e.g. the official Telegram plugin) leave two kinds of
state on disk that outlive the Claude Code process that created them:

- ``~/.claude/channels/<name>/bot.pid`` — the poller's pid file. If the
  process died without cleanup, the next session sees a "running" bot,
  skips starting its own poller, and inbound messages silently stop.
- ``~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/.in_use/<pid>``
  — per-session ownership markers. Stale markers from dead sessions make
  the plugin look busy/orphaned to the next launch.

Both failure modes surface as "Telegram just stopped answering" with no
error anywhere, typically right after a session swap. This preflight
removes only state whose owning pid is provably dead; live sessions are
never touched, so running it before every launch is safe.

On Windows pid liveness cannot be probed safely from the stdlib
(``os.kill(pid, 0)`` terminates the process), so the preflight is a no-op
there.
"""

from __future__ import annotations

import os
from pathlib import Path


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _read_pid(text: str) -> int | None:
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _clean_pid_files(channels_dir: Path, actions: list[str]) -> None:
    for pid_file in channels_dir.glob("*/bot.pid"):
        try:
            pid = _read_pid(pid_file.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if pid is None or not _pid_alive(pid):
            try:
                pid_file.unlink()
                actions.append(f"removed stale {pid_file}")
            except OSError:
                pass


def _clean_in_use_markers(cache_dir: Path, actions: list[str]) -> None:
    # cache/<marketplace>/<plugin>/<version>/.in_use/<pid>
    for in_use in cache_dir.glob("*/*/*/.in_use"):
        live = 0
        try:
            markers = list(in_use.iterdir())
        except OSError:
            continue
        for marker in markers:
            pid = _read_pid(marker.name)
            if pid is not None and _pid_alive(pid):
                live += 1
                continue
            try:
                marker.unlink()
                actions.append(f"removed stale marker {marker}")
            except OSError:
                live += 1  # could not remove: treat as live so we stay conservative
        if live == 0:
            orphan_flag = in_use.parent / ".orphaned_at"
            if orphan_flag.exists():
                try:
                    orphan_flag.unlink()
                    actions.append(f"removed {orphan_flag}")
                except OSError:
                    pass


def clean_stale_channel_state(claude_home: Path | None = None) -> list[str]:
    """Remove dead-pid channel state; returns a log of actions taken."""
    if os.name == "nt":
        return []
    home = claude_home or (Path.home() / ".claude")
    actions: list[str] = []
    channels_dir = home / "channels"
    if channels_dir.is_dir():
        _clean_pid_files(channels_dir, actions)
    cache_dir = home / "plugins" / "cache"
    if cache_dir.is_dir():
        _clean_in_use_markers(cache_dir, actions)
    return actions
