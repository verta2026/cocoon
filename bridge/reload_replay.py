"""Generic reload replay-tail helpers."""

from __future__ import annotations

import json
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path


def current_resume_sid(projects_dir: Path) -> str:
    result = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True)
    sids = []
    for line in result.stdout.splitlines():
        if not line.startswith("claude "):
            continue
        match = re.search(r"--resume\s+([0-9a-fA-F-]{36})", line)
        if match:
            sids.append(match.group(1))
    if not sids:
        return ""
    if len(sids) == 1:
        return sids[0]
    best_sid, best_mtime = sids[0], 0.0
    for sid in sids:
        path = projects_dir / f"{sid}.jsonl"
        try:
            mtime = path.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best_sid = sid
        except OSError:
            pass
    return best_sid


def maybe_replay_forge_tail(
    replay_file: Path,
    current_resume_sid_func: Callable[[], str],
    tmux_send_func: Callable[[str], None],
    log_func: Callable[[str], None],
    stale_seconds: int = 6 * 3600,
    sleep_func: Callable[[float], None] = time.sleep,
) -> str:
    """Redeliver real user messages that arrived during a session swap."""
    if not replay_file.exists():
        return ""
    try:
        data = json.loads(replay_file.read_text(encoding="utf-8"))
    except Exception:
        replay_file.unlink(missing_ok=True)
        return ""
    sid = current_resume_sid_func()
    if not sid or data.get("new_sid") != sid:
        try:
            age = time.time() - replay_file.stat().st_mtime
        except OSError:
            age = stale_seconds + 1
        if age > stale_seconds:
            log_func(f"replay dropped stale pending file (for sid {str(data.get('new_sid', ''))[:8]})")
            replay_file.unlink(missing_ok=True)
        return ""
    messages = [
        message.get("text", "")
        for message in data.get("messages", [])
        if str(message.get("text", "")).strip()
    ]
    replay_file.unlink(missing_ok=True)
    for text in messages:
        tmux_send_func(text)
        sleep_func(1)
    log_func(f"replayed {len(messages)} message(s) trimmed at the last swap into {str(sid)[:8]}")
    return f"forge-tail-replay:{len(messages)}"
