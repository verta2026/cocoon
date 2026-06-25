"""tmux interaction layer — capture, send, check status."""

from __future__ import annotations

import subprocess
import time
import re


OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)")
OSC8_LINK_RE = re.compile(
    r"\x1b\]8;[^;]*;([^\x07\x1b]*)(?:\x07|\x1b\\)(.*?)\x1b\]8;;(?:\x07|\x1b\\)",
    re.DOTALL,
)
CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SGR_RE = re.compile(r"\x1b\[([0-9;]*)m")


def ansi_to_markdown(text: str) -> str:
    """Keep simple terminal emphasis from tmux while dropping control codes."""
    def link_repl(match: re.Match[str]) -> str:
        url = match.group(1).strip()
        label = CSI_RE.sub("", OSC_RE.sub("", match.group(2))).strip()
        if not url or not label:
            return label
        return f"[{label}]({url})"

    text = OSC8_LINK_RE.sub(link_repl, text)
    text = OSC_RE.sub("", text)
    out: list[str] = []
    pos = 0
    bold = False
    italic = False

    def close_all() -> None:
        nonlocal bold, italic
        if italic:
            out.append("*")
            italic = False
        if bold:
            out.append("**")
            bold = False

    for match in SGR_RE.finditer(text):
        out.append(text[pos:match.start()])
        raw = match.group(1) or "0"
        codes = [0 if c == "" else int(c) for c in raw.split(";") if c == "" or c.isdigit()]
        if not codes:
            codes = [0]
        for code in codes:
            if code == 0:
                close_all()
            elif code == 1 and not bold:
                out.append("**")
                bold = True
            elif code == 3 and not italic:
                out.append("*")
                italic = True
            elif code == 22 and bold:
                if italic:
                    out.append("*")
                    italic = False
                out.append("**")
                bold = False
            elif code == 23 and italic:
                out.append("*")
                italic = False
        pos = match.end()

    out.append(text[pos:])
    close_all()
    return CSI_RE.sub("", "".join(out))


def tmux_exists(session_name: str) -> bool:
    r = subprocess.run(["tmux", "has-session", "-t", session_name], capture_output=True)
    return r.returncode == 0


def tmux_send(session_name: str, text: str) -> None:
    subprocess.run(["tmux", "send-keys", "-t", session_name, "-l", text], check=True)
    subprocess.run(["tmux", "send-keys", "-t", session_name, "Enter"], check=True)


def tmux_clear_input(session_name: str) -> None:
    subprocess.run(["tmux", "send-keys", "-t", session_name, "C-c"], check=True)
    time.sleep(0.1)
    subprocess.run(["tmux", "send-keys", "-t", session_name, "Escape"], check=True)
    subprocess.run(["tmux", "send-keys", "-t", session_name, "C-u"], check=True)


def tmux_clear_scrollback(session_name: str) -> None:
    subprocess.run(["tmux", "send-keys", "-t", session_name, "C-l"], check=True)
    subprocess.run(["tmux", "clear-history", "-t", session_name], check=True)


def pane_command(session_name: str) -> str:
    r = subprocess.run(
        ["tmux", "list-panes", "-t", session_name, "-F", "#{pane_current_command}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""


def tmux_capture(session_name: str, lines: int = 200) -> str:
    r = subprocess.run(
        ["tmux", "capture-pane", "-e", "-t", session_name, "-p", "-S", f"-{lines}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return ansi_to_markdown(r.stdout)


def claude_running(session_name: str) -> bool:
    if not tmux_exists(session_name):
        return False
    command = pane_command(session_name).lower()
    if command in ("claude", "claude.exe"):
        return True
    if command not in ("cmd.exe", "powershell.exe", "pwsh.exe"):
        return False
    screen = tmux_capture(session_name, 80)
    tail = "\n".join(screen.splitlines()[-40:])
    last_line = next((line.strip() for line in reversed(tail.splitlines()) if line.strip()), "")
    if re.match(r"^(?:PS\s+)?[A-Za-z]:\\.*>\s*$", last_line):
        return False
    return any(
        marker in tail
        for marker in (
            "Claude Code v",
            "? for shortcuts",
            "esc to interrupt",
            "Try \"",
            "Enter to confirm",
        )
    )


def claude_busy(session_name: str) -> bool:
    if not claude_running(session_name):
        return False
    screen = tmux_capture(session_name, 80)
    busy_markers = (
        "esc to interrupt",
        "Bash(",
        "Read(",
        "Web Search(",
        "Web Fetch(",
    )
    idle_markers = (
        "? for shortcuts",
        "MCP dialog dismissed",
        "Settings dialog dismissed",
    )
    tail = "\n".join(screen.splitlines()[-18:])
    if any(marker in tail for marker in idle_markers):
        return False
    if any(marker in tail for marker in busy_markers):
        return True
    return False
