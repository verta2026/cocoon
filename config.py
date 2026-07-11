"""Cocoon configuration — all settings in one place."""

import os
import re
import tempfile
from pathlib import Path


def _env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_float(name: str, default: float, *, minimum: float | None = None) -> float:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


SESSION_NAME = os.environ.get("COCOON_SESSION", "cocoon-cc")
WORK_DIR = os.environ.get("COCOON_WORK_DIR", os.getcwd())
START_COMMAND = os.environ.get("COCOON_START_COMMAND", "claude")
LAUNCHER_PROCESS_PATTERN = os.environ.get("COCOON_LAUNCHER_PATTERN", "")
STATE_DIR = Path(os.environ.get("COCOON_STATE_DIR", str(Path(WORK_DIR) / ".cocoon")))
CONVERSATIONS_DIR = Path(
    os.environ.get("COCOON_CONVERSATIONS_DIR", str(STATE_DIR / "conversations"))
)
EXTENSIONS_FILE = Path(os.environ.get("COCOON_EXTENSIONS_FILE", str(STATE_DIR / "extensions.json")))
AUTO_RELOAD_PAUSE_FILE = Path(
    os.environ.get("COCOON_AUTO_RELOAD_PAUSE_FILE", str(STATE_DIR / ".forge_auto_reload_paused"))
)
AUTO_RELOAD_LOG_FILE = Path(os.environ.get("COCOON_AUTO_RELOAD_LOG_FILE", str(STATE_DIR / ".forge_auto_reload.log")))
AUTO_RELOAD_ENABLED = _env_bool("COCOON_AUTO_RELOAD_ENABLED", False)
AUTO_RELOAD_STATE_FILE = Path(os.environ.get("COCOON_AUTO_RELOAD_STATE_FILE", str(STATE_DIR / ".auto_reload.json")))
AUTO_RELOAD_DRYRUN_FILE = Path(os.environ.get("COCOON_AUTO_RELOAD_DRYRUN_FILE", str(STATE_DIR / ".auto_reload_dryrun")))
AUTO_RELOAD_FORCE_FILE = Path(os.environ.get("COCOON_AUTO_RELOAD_FORCE_FILE", str(STATE_DIR / ".auto_reload_force")))
AUTO_RELOAD_CONTEXT_THRESHOLD = _env_int("COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD", 125000, minimum=1)
AUTO_RELOAD_CONTEXT_THRESHOLD_1M = _env_int("COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD_1M", 600000, minimum=1)
AUTO_RELOAD_IDLE_MIN_CONTEXT = _env_int("COCOON_AUTO_RELOAD_IDLE_MIN_CONTEXT", 200000, minimum=1)
AUTO_RELOAD_IDLE_SECONDS = _env_int("COCOON_AUTO_RELOAD_IDLE_SECONDS", 3600, minimum=1)
AUTO_RELOAD_COOLDOWN_SECONDS = _env_int("COCOON_AUTO_RELOAD_COOLDOWN_SECONDS", 600, minimum=0)
AUTO_RELOAD_CHECK_INTERVAL_SECONDS = _env_int("COCOON_AUTO_RELOAD_CHECK_INTERVAL_SECONDS", 30, minimum=5)
RELOAD_COMMAND = os.environ.get("COCOON_RELOAD_COMMAND", "").strip()
# Launch command for a clean, context-free session (defaults to START_COMMAND).
CLEAN_START_COMMAND = os.environ.get("COCOON_CLEAN_START_COMMAND", "").strip() or START_COMMAND
# Where the chat page's message reactions are stored.
REACTIONS_FILE = Path(os.environ.get("COCOON_REACTIONS_FILE", str(STATE_DIR / "reactions.json")))
# Written by hooks/ask_pending.py (PreToolUse), read by the bridge; both
# sides must agree on this path for the web question picker to work.
ASK_STATE_FILE = Path(os.environ.get("COCOON_ASK_STATE_FILE", str(STATE_DIR / ".ask_pending.json")))
# URL prefix the API uses when returning served-file links to the chat page.
FILES_URL_PREFIX = os.environ.get("COCOON_FILES_URL_PREFIX", "/bridge/files/")
RELOAD_LOCK_DIR = Path(os.environ.get("COCOON_RELOAD_LOCK_DIR", str(STATE_DIR / ".reload.lock")))
RELOAD_LOCK_STALE_SECONDS = _env_int("COCOON_RELOAD_LOCK_STALE_SECONDS", 300, minimum=1)
# Serve the bundled chat frontend from the reference server.
SERVE_FRONTEND = _env_bool("COCOON_SERVE_FRONTEND", True)
FRONTEND_DIR = Path(
    os.environ.get("COCOON_FRONTEND_DIR", str(Path(__file__).resolve().parent / "frontend"))
)
HOST = os.environ.get("COCOON_HOST", "127.0.0.1")
PORT = _env_int("COCOON_PORT", 8080, minimum=1)
DEFAULT_TOKEN = "cocoon-default-token"
TOKEN = os.environ.get("COCOON_TOKEN", DEFAULT_TOKEN)
MIN_PUBLIC_TOKEN_LEN = 24
# Only honour X-Forwarded-Proto when a trusted TLS-terminating proxy sits in
# front. Off by default: otherwise any client could forge the header and flip
# the login cookie's Secure flag, locking a plain-HTTP deployment into a login
# loop (or, reversed, signing insecure cookies on an HTTPS site).
TRUST_FORWARDED_PROTO = _env_bool("COCOON_TRUST_FORWARDED_PROTO", False)
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", ""})


def is_local_bind(host: str) -> bool:
    return (host or "").strip() in _LOCAL_HOSTS


def validate_security(*, token: str = None, host: str = None) -> None:
    """Refuse to start on an insecure token/bind combination.

    Enforced in-process (not only in start.sh/doctor) so that running
    ``uvicorn server:app`` directly cannot silently come up fail-open or with a
    guessable token on a public interface — where a leaked token equals full
    terminal control. Empty token is rejected on any bind; the built-in default
    and short tokens are rejected on a non-local bind.
    """
    token = TOKEN if token is None else token
    host = HOST if host is None else host
    problems = []
    if not token:
        problems.append(
            "COCOON_TOKEN is empty — an empty token authenticates every request. "
            "Set COCOON_TOKEN to a strong random value."
        )
    if not is_local_bind(host):
        if token == DEFAULT_TOKEN:
            problems.append(
                f"COCOON_TOKEN is the built-in default on a public bind ({host}). "
                "Set a strong random COCOON_TOKEN before exposing the server."
            )
        elif token and len(token) < MIN_PUBLIC_TOKEN_LEN:
            problems.append(
                f"COCOON_TOKEN is too short ({len(token)} < {MIN_PUBLIC_TOKEN_LEN}) "
                f"for a public bind ({host})."
            )
    if problems:
        raise RuntimeError(
            "Cocoon refuses to start due to insecure configuration:\n  - "
            + "\n  - ".join(problems)
        )
TMUX_HISTORY_LIMIT = _env_int("COCOON_TMUX_HISTORY_LIMIT", 20000, minimum=100)
UPLOAD_DIR = Path(
    os.environ.get("COCOON_UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "cocoon-uploads"))
)
STICKER_DIR = Path(os.environ.get("COCOON_STICKER_DIR", str(Path(tempfile.gettempdir()) / "cocoon-stickers")))
# Default cap keeps a stray upload from filling the disk while still fitting
# large working files (design exports, archives) Claude may need; 0 = unlimited.
MAX_UPLOAD_MB = _env_float("COCOON_MAX_UPLOAD_MB", 200, minimum=0)
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024) if MAX_UPLOAD_MB > 0 else 0
# 贴纸是小图，独立上限：普通上传的 200MB 对它是无界放大面
STICKER_MAX_MB = _env_float("COCOON_STICKER_MAX_MB", 5, minimum=0)
STICKER_MAX_BYTES = int(STICKER_MAX_MB * 1024 * 1024) if STICKER_MAX_MB > 0 else 5 * 1024 * 1024
# Cloud-backed appearance choice (which wallpaper/avatar is selected)
LOOK_FILE = Path(os.environ.get("COCOON_LOOK_FILE", str(STATE_DIR / "chat_look.json")))
# File editor: browse/edit a sandboxed tree from the editor page. Root
# defaults to the work dir; paths are confined to it (symlinks resolved).
EDITOR_ROOT = Path(os.environ.get("COCOON_EDITOR_ROOT", WORK_DIR))
_EDITOR_EXTRA_BLOCKED = {
    p.strip().strip("/") for p in os.environ.get("COCOON_EDITOR_BLOCKED", "").split(",") if p.strip()
}
EDITOR_BLOCKED_PREFIXES = {".git", "node_modules", "__pycache__", ".cocoon"} | _EDITOR_EXTRA_BLOCKED
EDITOR_BLOCKED_FILES = {"config.private.json", ".env", ".vapid.json"}
EDITOR_MAX_MB = _env_float("COCOON_EDITOR_MAX_MB", 2, minimum=0)
EDITOR_MAX_BYTES = int(EDITOR_MAX_MB * 1024 * 1024) if EDITOR_MAX_MB > 0 else 0
TTS_DIR = Path(os.environ.get("COCOON_TTS_DIR", str(Path(tempfile.gettempdir()) / "cocoon-tts")))
TTS_PROVIDER = os.environ.get("COCOON_TTS_PROVIDER", "none").strip().lower()
TTS_MAX_TEXT_CHARS = _env_int("COCOON_TTS_MAX_TEXT_CHARS", 800, minimum=1)
TTS_MAX_AUDIO_FILES = _env_int("COCOON_TTS_MAX_AUDIO_FILES", 40, minimum=1)
AUTO_DISMISS_PROMPTS = _env_bool("COCOON_AUTO_DISMISS_PROMPTS", True)
# The Claude Code settings warning usually means a config file is broken;
# auto-accepting it hides a real problem, so it is opt-in separately.
AUTO_ACCEPT_SETTINGS_WARNING = _env_bool("COCOON_AUTO_ACCEPT_SETTINGS_WARNING", False)


def _default_claude_projects_dir(work_dir: str) -> str:
    # Claude Code stores each project's session jsonl under
    # ~/.claude/projects/<work dir with non-alphanumerics mapped to "-">.
    munged = re.sub(r"[^A-Za-z0-9]", "-", str(Path(work_dir).resolve()))
    return str(Path.home() / ".claude" / "projects" / munged)


# Live chat mirror (/messages): reads the Claude Code session jsonl directly.
LIVE_MESSAGES_ENABLED = _env_bool("COCOON_LIVE_MESSAGES_ENABLED", True)
CLAUDE_PROJECTS_DIR = Path(
    os.environ.get("COCOON_CLAUDE_PROJECTS_DIR", _default_claude_projects_dir(WORK_DIR))
)
LIVE_ARCHIVE_FILE = Path(
    os.environ.get("COCOON_LIVE_ARCHIVE_FILE", str(CONVERSATIONS_DIR / "_current_session.jsonl"))
)
LIVE_ARCHIVE_SYNC_SECONDS = _env_int("COCOON_LIVE_ARCHIVE_SYNC_SECONDS", 1, minimum=1)
# Optional jsonl a messaging plugin appends outgoing sends to; empty disables it.
SEND_SIDECAR_FILE = os.environ.get("COCOON_SEND_SIDECAR_FILE", "").strip()
# Inbound <channel> messages from this sender id render as the user;
# other senders render as third-party "channel" bubbles.
PRIMARY_SENDER_ID = os.environ.get("COCOON_PRIMARY_SENDER_ID", "").strip()

ASSISTANT_NAME = os.environ.get("COCOON_ASSISTANT_NAME", "Claude")
ASSISTANT_AVATAR = os.environ.get("COCOON_ASSISTANT_AVATAR", "")
USER_NAME = os.environ.get("COCOON_USER_NAME", "You")
USER_AVATAR = os.environ.get("COCOON_USER_AVATAR", "")

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_VOICE_ID = os.environ.get("MINIMAX_VOICE_ID", "")
MINIMAX_TTS_MODEL = os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-hd")
MINIMAX_TTS_URL = os.environ.get("MINIMAX_TTS_URL", "https://api.minimaxi.chat/v1/t2a_v2")
