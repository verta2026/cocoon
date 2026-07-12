"""Session startup helpers for the tmux-backed Claude Code process."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable

from fastapi import HTTPException


def normalized_start_command(start_command: str | None) -> str:
    command = (start_command or "").strip()
    return command or "claude"


def compose_start_command(start_command: str | None, channel_args: str | None) -> str:
    """Append channel args (e.g. ``--channels plugin:telegram@...``) to a launch command.

    Skipped when the command already carries ``--channels`` so a user who put
    the flag into COCOON_START_COMMAND directly doesn't get it twice.
    """
    command = normalized_start_command(start_command)
    extra = (channel_args or "").strip()
    if not extra or "--channels" in command:
        return command
    return f"{command} {extra}"


def start_tmux_session(
    session_name: str,
    work_dir: str,
    tmux_send_func: Callable[[str], None],
) -> None:
    # 窗格尺寸决定 /terminal 的可读性：Claude Code 按列宽排版（500 列会把一段话
    # 挤成一根横线），TUI 一屏只保留行高那么多行（50 行 = 网页上看不到几行）
    args = [
        "tmux",
        "new-session",
        "-d",
        "-s",
        session_name,
        "-x",
        "140",
        "-y",
        "200",
    ]
    if os.name == "nt":
        args.extend(["cmd.exe", "/K"])
    else:
        args.extend(["-c", work_dir])

    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "tmux new-session failed").strip()
        raise HTTPException(500, detail)

    if os.name == "nt":
        safe_work_dir = work_dir.replace('"', "")
        tmux_send_func(f'cd /d "{safe_work_dir}"')


def launcher_in_progress(process_pattern: str | None) -> bool:
    pattern = (process_pattern or "").strip()
    if not pattern:
        return False
    result = subprocess.run(
        ["pgrep", "-f", pattern],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def start_claude(
    start_command: str | None,
    tmux_clear_input_func: Callable[[], None],
    tmux_clear_scrollback_func: Callable[[], None],
    tmux_send_func: Callable[[str], None],
) -> None:
    tmux_clear_input_func()
    tmux_clear_scrollback_func()
    tmux_send_func(normalized_start_command(start_command))
