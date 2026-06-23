"""Auto-dismiss Claude Code terminal prompts (resume, rating, settings)."""

from __future__ import annotations

import subprocess
import time

from bridge.tmux import claude_running, tmux_capture, tmux_exists


def dismiss_resume_summary_prompt(session_name: str):
    if not claude_running(session_name):
        return False
    screen = tmux_capture(session_name, 80)
    if "Resume from summary" in screen and "Enter to confirm" in screen:
        subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
        return True
    return False


def dismiss_rating_prompt(session_name: str):
    if not claude_running(session_name):
        return False
    screen = tmux_capture(session_name, 80)
    if "How is Claude doing this session" in screen and "0: Dismiss" in screen:
        subprocess.run(["tmux", "send-keys", "-t", session_name, "0"], check=True)
        return True
    return False


def dismiss_settings_warning_prompt(session_name: str):
    if not claude_running(session_name):
        return False
    screen = tmux_capture(session_name, 80)
    if "Settings Warning" in screen and "Enter to confirm" in screen and "Continue" in screen:
        subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
        return True
    return False


def dismiss_trust_prompt(session_name: str):
    if not tmux_exists(session_name):
        return False
    screen = tmux_capture(session_name, 80)
    if "trust this folder" in screen and "Enter to confirm" in screen:
        subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)
        return True
    return False


def wait_for_claude_ready(session_name: str, timeout=70):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not claude_running(session_name):
            time.sleep(1)
            continue
        if dismiss_resume_summary_prompt(session_name):
            time.sleep(2)
            continue
        if dismiss_rating_prompt(session_name):
            time.sleep(1)
            continue
        if dismiss_settings_warning_prompt(session_name):
            time.sleep(2)
            continue
        if dismiss_trust_prompt(session_name):
            time.sleep(2)
            continue
        screen = tmux_capture(session_name, 80)
        tail = "\n".join(screen.splitlines()[-24:])
        if "? for shortcuts" in tail and "esc to interrupt" not in tail and "Compacting conversation" not in tail:
            return True
        time.sleep(1)
    return False
