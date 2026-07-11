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


def wait_for_claude_tui(session_name: str, timeout=20) -> bool:
    """Wait until the Claude Code TUI has finished drawing.

    claude_running() flips true the moment the `claude` process owns the pane,
    but for the first few seconds the TUI is still initializing and keystrokes
    sent then are swallowed — a fresh install loses the user's very first
    message this way. "Drawn" means either an idle input prompt or an active
    generation; both accept (or queue) typed input safely.
    """
    deadline = time.time() + timeout
    markers = ("? for shortcuts", "bypass permissions", "⏵⏵", "❯", "esc to interrupt")
    while time.time() < deadline:
        screen = tmux_capture(session_name, 80)
        tail = "\n".join(screen.splitlines()[-24:])
        if any(marker in tail for marker in markers):
            return True
        time.sleep(1)
    return False


def wait_for_claude_ready(
    session_name: str,
    timeout=70,
    auto_dismiss: bool = True,
    auto_accept_settings_warning: bool = False,
):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not claude_running(session_name):
            time.sleep(1)
            continue
        if auto_dismiss:
            if dismiss_resume_summary_prompt(session_name):
                time.sleep(2)
                continue
            if dismiss_rating_prompt(session_name):
                time.sleep(1)
                continue
            # The settings warning flags a real config problem; accepting it
            # silently hides that, so it needs its own explicit opt-in. The
            # folder-trust prompt stays under the general flag — headless
            # startup can't get past it any other way.
            if auto_accept_settings_warning and dismiss_settings_warning_prompt(session_name):
                time.sleep(2)
                continue
            if dismiss_trust_prompt(session_name):
                time.sleep(2)
                continue
        screen = tmux_capture(session_name, 80)
        tail = "\n".join(screen.splitlines()[-24:])
        if "esc to interrupt" in tail or "Compacting conversation" in tail:
            time.sleep(1)
            continue
        # Newer CLI shells idle with a permissions banner or a bare input
        # prompt instead of the "? for shortcuts" hint; any of these while
        # not generating means the session is ready for input.
        ready_markers = ("? for shortcuts", "bypass permissions", "⏵⏵", "❯")
        if any(marker in tail for marker in ready_markers):
            return True
        time.sleep(1)
    return False
