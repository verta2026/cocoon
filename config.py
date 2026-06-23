"""Cocoon configuration — all settings in one place."""

import os
from pathlib import Path

SESSION_NAME = os.environ.get("COCOON_SESSION", "cocoon-cc")
WORK_DIR = os.environ.get("COCOON_WORK_DIR", os.getcwd())
PORT = int(os.environ.get("COCOON_PORT", "8080"))
TOKEN = os.environ.get("COCOON_TOKEN", "cocoon-default-token")
UPLOAD_DIR = Path(os.environ.get("COCOON_UPLOAD_DIR", "/tmp/cocoon-uploads"))

ASSISTANT_NAME = os.environ.get("COCOON_ASSISTANT_NAME", "Claude")
ASSISTANT_AVATAR = os.environ.get("COCOON_ASSISTANT_AVATAR", "")
USER_NAME = os.environ.get("COCOON_USER_NAME", "You")
USER_AVATAR = os.environ.get("COCOON_USER_AVATAR", "")
