"""TTS route registration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import Request
from pydantic import BaseModel


class TtsRequest(BaseModel):
    text: str
    emotion: Optional[str] = None
    source: str = "frontend"


def register_tts_routes(
    app,
    *,
    verify_token,
    verify_media_token,
    latest_tts,
    synthesize_tts,
    serve_tts_audio,
    tts_dir: Path,
    bridge_token: str,
) -> None:
    @app.get("/tts/latest")
    async def tts_latest(request: Request):
        verify_token(request)
        return latest_tts(tts_dir)

    @app.post("/tts/say")
    async def tts_say(req: TtsRequest, request: Request):
        verify_token(request)
        return synthesize_tts(tts_dir, req.text, emotion=req.emotion, source=req.source)

    @app.get("/tts/audio/{audio_name}")
    async def tts_audio(audio_name: str, request: Request, token: str = None):
        verify_media_token(request, bridge_token, token)
        return serve_tts_audio(tts_dir, audio_name)
