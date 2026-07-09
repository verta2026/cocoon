"""Generic TTS audio metadata and file helpers."""

from __future__ import annotations

import datetime
import hashlib
import os
import time
from typing import Any


def validate_tts_request(
    text: str,
    emotion: str | None,
    *,
    max_text_chars: int,
    allowed_emotions: set[str] | frozenset[str],
) -> tuple[str, str | None]:
    """Normalize and validate a TTS text/emotion request."""
    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("missing text")
    if len(normalized) > max_text_chars:
        raise ValueError(f"text too long; max {max_text_chars} chars")
    if emotion and emotion not in allowed_emotions:
        raise ValueError("invalid emotion")
    return normalized, emotion


def normalize_required_text(text: str) -> str:
    """Strip text and require a non-empty value."""
    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("missing text")
    return normalized


def make_audio_id(text: str, emotion: str | None, *, now: float | None = None) -> str:
    """Create a short stable-shape audio id from timestamp, emotion, and text."""
    timestamp = time.time() if now is None else now
    seed = f"{timestamp}:{emotion or ''}:{text}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:20]


def audio_file_path(tts_dir: str, audio_id: str) -> str:
    """Return the mp3 path for an audio id."""
    return os.path.join(tts_dir, f"{audio_id}.mp3")


def public_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Return the public metadata shape for latest/generated TTS audio."""
    audio_id = meta.get("id", "")
    return {
        "id": audio_id,
        "url": f"/tts/audio/{audio_id}.mp3" if audio_id else "",
        "text": meta.get("text", ""),
        "emotion": meta.get("emotion", ""),
        "created_at": meta.get("created_at", ""),
        "source": meta.get("source", ""),
        "bytes": meta.get("bytes", 0),
    }


def latest_meta(
    *,
    audio_id: str,
    text: str,
    emotion: str | None,
    source: str,
    size: int,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build the latest-audio metadata record."""
    return {
        "id": audio_id,
        "text": text,
        "emotion": emotion or "",
        "source": source,
        "bytes": size,
        "created_at": created_at or datetime.datetime.now().isoformat(timespec="seconds"),
    }


def cleanup_audio_files(tts_dir: str, *, max_files: int) -> None:
    """Keep only the newest mp3 files in a TTS directory."""
    files = []
    for name in os.listdir(tts_dir):
        if not name.endswith(".mp3"):
            continue
        path = os.path.join(tts_dir, name)
        try:
            files.append((os.path.getmtime(path), path))
        except OSError:
            pass
    for _, path in sorted(files, reverse=True)[max_files:]:
        try:
            os.unlink(path)
        except OSError:
            pass


def is_valid_audio_id(audio_id: str) -> bool:
    """Reject empty or path-like audio ids."""
    return bool(audio_id) and "/" not in audio_id and "\\" not in audio_id
