"""Cocoon configuration — all settings in one place."""

import os
import tempfile
from pathlib import Path

SESSION_NAME = os.environ.get("COCOON_SESSION", "cocoon-cc")
WORK_DIR = os.environ.get("COCOON_WORK_DIR", os.getcwd())
PORT = int(os.environ.get("COCOON_PORT", "8080"))
TOKEN = os.environ.get("COCOON_TOKEN", "cocoon-default-token")
UPLOAD_DIR = Path(
    os.environ.get("COCOON_UPLOAD_DIR", str(Path(tempfile.gettempdir()) / "cocoon-uploads"))
)
TTS_DIR = Path(os.environ.get("COCOON_TTS_DIR", str(Path(tempfile.gettempdir()) / "cocoon-tts")))
TTS_PROVIDER = os.environ.get("COCOON_TTS_PROVIDER", "none").strip().lower()

ASSISTANT_NAME = os.environ.get("COCOON_ASSISTANT_NAME", "Claude")
ASSISTANT_AVATAR = os.environ.get("COCOON_ASSISTANT_AVATAR", "")
USER_NAME = os.environ.get("COCOON_USER_NAME", "You")
USER_AVATAR = os.environ.get("COCOON_USER_AVATAR", "")

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_VOICE_ID = os.environ.get("MINIMAX_VOICE_ID", "")
MINIMAX_TTS_MODEL = os.environ.get("MINIMAX_TTS_MODEL", "speech-2.8-hd")
MINIMAX_TTS_URL = os.environ.get("MINIMAX_TTS_URL", "https://api.minimaxi.chat/v1/t2a_v2")
