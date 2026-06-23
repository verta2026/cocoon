"""Optional text-to-speech support."""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse

from config import (
    MINIMAX_API_KEY,
    MINIMAX_TTS_MODEL,
    MINIMAX_TTS_URL,
    MINIMAX_VOICE_ID,
    TTS_PROVIDER,
)


MAX_TEXT_CHARS = 800
MAX_AUDIO_FILES = 40
ALLOWED_EMOTIONS = {
    "happy",
    "sad",
    "angry",
    "calm",
    "whisper",
    "surprised",
    "fearful",
    "disgusted",
}
AUDIO_NAME_RE = re.compile(r"^[a-f0-9]{16,64}\.mp3$")


def _latest_path(tts_dir: Path) -> Path:
    return tts_dir / "latest.json"


def _audio_id(text: str, emotion: Optional[str]) -> str:
    seed = f"{time.time()}:{emotion or ''}:{text}".encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:20]


def _audio_path(tts_dir: Path, audio_id: str) -> Path:
    return tts_dir / f"{audio_id}.mp3"


def _public_meta(meta: dict) -> dict:
    audio_id = str(meta.get("id", ""))
    return {
        "id": audio_id,
        "url": f"/tts/audio/{audio_id}.mp3" if audio_id else "",
        "text": meta.get("text", ""),
        "emotion": meta.get("emotion", ""),
        "created_at": meta.get("created_at", ""),
        "source": meta.get("source", ""),
        "bytes": meta.get("bytes", 0),
    }


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _cleanup_audio_files(tts_dir: Path) -> None:
    files = []
    for path in tts_dir.glob("*.mp3"):
        try:
            files.append((path.stat().st_mtime, path))
        except OSError:
            continue
    for _, path in sorted(files, reverse=True)[MAX_AUDIO_FILES:]:
        try:
            path.unlink()
        except OSError:
            pass


def _save_latest(
    tts_dir: Path,
    audio_id: str,
    text: str,
    emotion: Optional[str],
    source: str,
    size: int,
) -> dict:
    meta = {
        "id": audio_id,
        "text": text,
        "emotion": emotion or "",
        "source": source,
        "bytes": size,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    _write_json(_latest_path(tts_dir), meta)
    _cleanup_audio_files(tts_dir)
    return meta


def latest_tts(tts_dir: Path) -> dict:
    path = _latest_path(tts_dir)
    if not path.exists():
        return {"ok": True, "latest": _public_meta({})}
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        meta = {}
    return {"ok": True, "latest": _public_meta(meta)}


def _decode_minimax_audio(raw: str) -> bytes:
    try:
        return bytes.fromhex(raw)
    except ValueError:
        padded = raw + "=" * (-len(raw) % 4)
        return base64.b64decode(padded)


def _call_minimax(text: str, emotion: Optional[str]) -> bytes:
    if not MINIMAX_API_KEY:
        raise RuntimeError("MINIMAX_API_KEY is not configured")
    if not MINIMAX_VOICE_ID:
        raise RuntimeError("MINIMAX_VOICE_ID is not configured")

    payload = {
        "model": MINIMAX_TTS_MODEL,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": MINIMAX_VOICE_ID,
            "speed": 0.95,
            "vol": 1.0,
            "pitch": 0,
            **({"emotion": emotion} if emotion else {}),
        },
        "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"},
    }
    req = urllib.request.Request(
        MINIMAX_TTS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {MINIMAX_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"MiniMax request failed: {detail or exc.reason}") from exc

    audio = (result.get("data") or {}).get("audio")
    if not audio:
        raise RuntimeError("No audio in MiniMax response")
    return _decode_minimax_audio(audio)


def synthesize_tts(
    tts_dir: Path,
    text: str,
    emotion: Optional[str] = None,
    source: str = "frontend",
) -> dict:
    text = (text or "").strip()
    emotion = (emotion or "").strip().lower() or None
    source = (source or "frontend").strip()[:80]

    if not text:
        raise HTTPException(400, "missing text")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(400, f"text too long; max {MAX_TEXT_CHARS} chars")
    if emotion and emotion not in ALLOWED_EMOTIONS:
        raise HTTPException(400, "invalid emotion")
    if TTS_PROVIDER != "minimax":
        raise HTTPException(503, "TTS is not configured")

    try:
        audio_bytes = _call_minimax(text, emotion)
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc

    tts_dir.mkdir(parents=True, exist_ok=True)
    audio_id = _audio_id(text, emotion)
    _audio_path(tts_dir, audio_id).write_bytes(audio_bytes)
    meta = _save_latest(tts_dir, audio_id, text, emotion, source, len(audio_bytes))
    return {"ok": True, "audio": _public_meta(meta)}


def serve_tts_audio(tts_dir: Path, audio_name: str):
    if not AUDIO_NAME_RE.match(audio_name):
        raise HTTPException(400, "invalid audio id")
    path = (tts_dir / audio_name).resolve()
    if not path.is_relative_to(tts_dir.resolve()):
        raise HTTPException(403, "Forbidden")
    if not path.exists():
        raise HTTPException(404, "Audio not found")
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "private, max-age=86400"},
    )
