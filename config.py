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
CONVERSATIONS_DIR = Path(
    os.environ.get("COCOON_CONVERSATIONS_DIR", str(Path(WORK_DIR) / ".cocoon" / "conversations"))
)
EXTENSIONS_FILE = Path(os.environ.get("COCOON_EXTENSIONS_FILE", str(Path(WORK_DIR) / ".cocoon" / "extensions.json")))
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
