"""Cocoon configuration — all settings in one place."""

import os
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
AUTO_RELOAD_CONTEXT_THRESHOLD = _env_int("COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD", 125000, minimum=1)
AUTO_RELOAD_CONTEXT_THRESHOLD_1M = _env_int("COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD_1M", 600000, minimum=1)
AUTO_RELOAD_IDLE_MIN_CONTEXT = _env_int("COCOON_AUTO_RELOAD_IDLE_MIN_CONTEXT", 200000, minimum=1)
AUTO_RELOAD_IDLE_SECONDS = _env_int("COCOON_AUTO_RELOAD_IDLE_SECONDS", 3600, minimum=1)
AUTO_RELOAD_COOLDOWN_SECONDS = _env_int("COCOON_AUTO_RELOAD_COOLDOWN_SECONDS", 600, minimum=0)
AUTO_RELOAD_CHECK_INTERVAL_SECONDS = _env_int("COCOON_AUTO_RELOAD_CHECK_INTERVAL_SECONDS", 30, minimum=5)
RELOAD_COMMAND = os.environ.get("COCOON_RELOAD_COMMAND", "").strip()
RELOAD_LOCK_DIR = Path(os.environ.get("COCOON_RELOAD_LOCK_DIR", str(STATE_DIR / ".reload.lock")))
RELOAD_LOCK_STALE_SECONDS = _env_int("COCOON_RELOAD_LOCK_STALE_SECONDS", 300, minimum=1)
HOST = os.environ.get("COCOON_HOST", "127.0.0.1")
PORT = _env_int("COCOON_PORT", 8080, minimum=1)
TOKEN = os.environ.get("COCOON_TOKEN", "cocoon-default-token")
TMUX_HISTORY_LIMIT = _env_int("COCOON_TMUX_HISTORY_LIMIT", 20000, minimum=100)
UPLOAD_DIR = Path(
    os.environ.get("COCOON_UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "cocoon-uploads"))
)
MAX_UPLOAD_MB = _env_float("COCOON_MAX_UPLOAD_MB", 0, minimum=0)
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024) if MAX_UPLOAD_MB > 0 else 0
TTS_DIR = Path(os.environ.get("COCOON_TTS_DIR", str(Path(tempfile.gettempdir()) / "cocoon-tts")))
TTS_PROVIDER = os.environ.get("COCOON_TTS_PROVIDER", "none").strip().lower()
TTS_MAX_TEXT_CHARS = _env_int("COCOON_TTS_MAX_TEXT_CHARS", 800, minimum=1)
TTS_MAX_AUDIO_FILES = _env_int("COCOON_TTS_MAX_AUDIO_FILES", 40, minimum=1)
AUTO_DISMISS_PROMPTS = _env_bool("COCOON_AUTO_DISMISS_PROMPTS", True)

ASSISTANT_NAME = os.environ.get("COCOON_ASSISTANT_NAME", "Claude")
ASSISTANT_AVATAR = os.environ.get("COCOON_ASSISTANT_AVATAR", "")
USER_NAME = os.environ.get("COCOON_USER_NAME", "You")
USER_AVATAR = os.environ.get("COCOON_USER_AVATAR", "")

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_VOICE_ID = os.environ.get("MINIMAX_VOICE_ID", "")
MINIMAX_TTS_MODEL = os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-hd")
MINIMAX_TTS_URL = os.environ.get("MINIMAX_TTS_URL", "https://api.minimaxi.chat/v1/t2a_v2")
