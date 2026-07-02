"""Generic file and hashing helpers for forge-style reload scripts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha_text(text: str | None) -> str:
    """Return a SHA-256 hex digest for text, treating None as empty."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    """Read UTF-8 text and strip it, returning empty string when missing."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON object, returning empty dict when missing or invalid."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def atomic_write_text(path: Path, text: str) -> None:
    """Write UTF-8 text via a same-directory temp file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)
