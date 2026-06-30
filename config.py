"""Cocoon configuration — all settings in one place."""

import os
import tempfile
from pathlib import Path

SESSION_NAME = os.environ.get("COCOON_SESSION", "cocoon-cc")
WORK_DIR = os.environ.get("COCOON_WORK_DIR", os.getcwd())
START_COMMAND = os.environ.get("COCOON_START_COMMAND", "claude")
LAUNCHER_PROCESS_PATTERN = os.environ.get("COCOON_LAUNCHER_PATTERN", "")
CONVERSATIONS_DIR = Path(
    os.environ.get("COCOON_CONVERSATIONS_DIR", str(Path(WORK_DIR) / ".cocoon" / "conversations"))
)
HOST = os.environ.get("COCOON_HOST", "127.0.0.1")
PORT = int(os.environ.get("COCOON_PORT", "8080"))
TOKEN = os.environ.get("COCOON_TOKEN", "cocoon-default-token")
TMUX_HISTORY_LIMIT = int(os.environ.get("COCOON_TMUX_HISTORY_LIMIT", "20000"))
UPLOAD_DIR = Path(
    os.environ.get("COCOON_UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "cocoon-uploads"))
)
MAX_UPLOAD_MB = float(os.environ.get("COCOON_MAX_UPLOAD_MB", "0"))
MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024) if MAX_UPLOAD_MB > 0 else 0
TTS_DIR = Path(os.environ.get("COCOON_TTS_DIR", str(Path(tempfile.gettempdir()) / "cocoon-tts")))
TTS_PROVIDER = os.environ.get("COCOON_TTS_PROVIDER", "none").strip().lower()
AUTO_DISMISS_PROMPTS = os.environ.get("COCOON_AUTO_DISMISS_PROMPTS", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}

ASSISTANT_NAME = os.environ.get("COCOON_ASSISTANT_NAME", "Claude")
ASSISTANT_AVATAR = os.environ.get("COCOON_ASSISTANT_AVATAR", "")
USER_NAME = os.environ.get("COCOON_USER_NAME", "You")
USER_AVATAR = os.environ.get("COCOON_USER_AVATAR", "")

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_VOICE_ID = os.environ.get("MINIMAX_VOICE_ID", "")
MINIMAX_TTS_MODEL = os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-hd")
MINIMAX_TTS_URL = os.environ.get("MINIMAX_TTS_URL", "https://api.minimaxi.chat/v1/t2a_v2")
