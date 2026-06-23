#!/usr/bin/env python3
"""
Cocoon — a web chat UI for Claude Code via tmux.

POST /send    — send a message to Claude Code
GET  /output  — get latest terminal output
GET  /status  — session status
POST /start   — start Claude Code session
GET  /chat    — chat UI
"""

import asyncio
import subprocess
import sys
import time
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import SESSION_NAME, WORK_DIR, TOKEN, UPLOAD_DIR, TTS_DIR
from bridge.tmux import (
    claude_busy as _claude_busy,
    pane_command as _pane_command,
    tmux_capture as _tmux_capture,
    tmux_clear_input as _tmux_clear_input,
    tmux_clear_scrollback as _tmux_clear_scrollback,
    tmux_exists as _tmux_exists,
    tmux_send as _tmux_send,
)
from bridge.prompts import (
    dismiss_rating_prompt as _dismiss_rating_prompt,
    dismiss_resume_summary_prompt as _dismiss_resume_summary_prompt,
    dismiss_settings_warning_prompt as _dismiss_settings_warning_prompt,
    dismiss_trust_prompt as _dismiss_trust_prompt,
    wait_for_claude_ready as _wait_for_claude_ready,
)
from bridge.uploads import (
    save_upload_file as _save_upload_file,
    serve_upload_file as _serve_upload_file,
)
from bridge.tts import (
    latest_tts as _latest_tts,
    serve_tts_audio as _serve_tts_audio,
    synthesize_tts as _synthesize_tts,
)
from bridge.ui import CHAT_HTML, TERMINAL_HTML

UPLOAD_DIR.mkdir(exist_ok=True)
TTS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Cocoon", docs_url=None)


def verify_token(request: Request):
    auth = request.headers.get("Authorization", "")
    cookie_token = request.cookies.get("token", "")
    query_token = request.query_params.get("token", "")
    if auth == f"Bearer {TOKEN}" or cookie_token == TOKEN or query_token == TOKEN:
        return
    raise HTTPException(403, "Bad token")


def tmux_exists():
    return _tmux_exists(SESSION_NAME)


def tmux_send(text):
    _tmux_send(SESSION_NAME, text)


def tmux_clear_input():
    _tmux_clear_input(SESSION_NAME)


def tmux_clear_scrollback():
    _tmux_clear_scrollback(SESSION_NAME)


def pane_command():
    return _pane_command(SESSION_NAME)


def claude_busy():
    return _claude_busy(SESSION_NAME)


def tmux_capture(lines=200):
    return _tmux_capture(SESSION_NAME, lines)


def dismiss_resume_summary_prompt():
    return _dismiss_resume_summary_prompt(SESSION_NAME)


def dismiss_rating_prompt():
    return _dismiss_rating_prompt(SESSION_NAME)


def wait_for_claude_ready(timeout=70):
    return _wait_for_claude_ready(SESSION_NAME, timeout)


class Message(BaseModel):
    text: str


class TtsRequest(BaseModel):
    text: str
    emotion: Optional[str] = None
    source: str = "frontend"


@app.get("/status")
async def status(request: Request):
    verify_token(request)
    alive = tmux_exists()
    command = pane_command() if alive else ""
    running = command == "claude"
    dismissed_resume = dismiss_resume_summary_prompt() if running else False
    dismissed_trust = _dismiss_trust_prompt(SESSION_NAME) if alive else False
    return {
        "session": SESSION_NAME,
        "alive": alive,
        "running": running,
        "command": command,
        "busy": claude_busy() if running else False,
        "dismissed_resume": dismissed_resume,
        "dismissed_trust": dismissed_trust,
    }


@app.post("/start")
async def start_session(request: Request):
    verify_token(request)
    if tmux_exists():
        if pane_command() == "claude":
            return {"message": "Session already running"}
        tmux_clear_input()
        tmux_clear_scrollback()
        tmux_send("claude")
        await asyncio.sleep(3)
        return {"message": "Claude started in existing session"}

    subprocess.run(["tmux", "set-option", "-g", "history-limit", "20000"],
                   capture_output=True)
    subprocess.run([
        "tmux", "new-session", "-d", "-s", SESSION_NAME,
        "-x", "500", "-y", "50",
        "-c", WORK_DIR,
    ], check=True)
    await asyncio.sleep(1)
    tmux_send("claude")
    await asyncio.sleep(3)
    return {"message": "Session started", "session": SESSION_NAME}


@app.post("/send")
async def send_message(msg: Message, request: Request):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")

    if pane_command() != "claude":
        tmux_send("claude")
        if msg.text and wait_for_claude_ready():
            tmux_send(msg.text.strip())
            return {"sent": True, "reloaded": True, "length": len(msg.text)}
        return {"sent": False, "reloaded": True, "length": len(msg.text)}

    if dismiss_resume_summary_prompt():
        if msg.text and wait_for_claude_ready():
            tmux_send(msg.text.strip())
            return {"sent": True, "reloaded": True, "length": len(msg.text)}
        return {"sent": False, "reloaded": True, "length": len(msg.text)}

    if msg.text:
        tmux_send(msg.text.strip())
    else:
        subprocess.run(
            ["tmux", "send-keys", "-t", SESSION_NAME, "Enter"],
            check=True,
        )
    return {"sent": True, "length": len(msg.text)}


@app.get("/output")
async def get_output(request: Request, lines: int = 100):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    return PlainTextResponse(tmux_capture(lines))


@app.post("/new-session")
async def new_session(request: Request):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    if pane_command() == "claude":
        tmux_clear_input()
        tmux_send("/exit")
        for _ in range(40):
            await asyncio.sleep(0.5)
            if pane_command() != "claude":
                tmux_send("claude")
                await asyncio.sleep(3)
                return {"message": "New session started"}
        raise HTTPException(409, "Claude did not exit; try again")
    tmux_send("claude")
    await asyncio.sleep(3)
    return {"message": "Claude started"}


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    verify_token(request)
    return _save_upload_file(UPLOAD_DIR, file)


@app.get("/files/{filename}")
async def serve_file(filename: str, request: Request, token: str = None):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth.split(" ", 1)[1] == TOKEN:
        pass
    elif token == TOKEN:
        pass
    else:
        raise HTTPException(403, "Bad token")
    return _serve_upload_file(UPLOAD_DIR, filename)


@app.get("/tts/latest")
async def tts_latest(request: Request):
    verify_token(request)
    return _latest_tts(TTS_DIR)


@app.post("/tts/say")
async def tts_say(req: TtsRequest, request: Request):
    verify_token(request)
    return _synthesize_tts(TTS_DIR, req.text, emotion=req.emotion, source=req.source)


@app.get("/tts/audio/{audio_name}")
async def tts_audio(audio_name: str, request: Request, token: str = None):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth.split(" ", 1)[1] == TOKEN:
        pass
    elif token == TOKEN:
        pass
    else:
        raise HTTPException(403, "Bad token")
    return _serve_tts_audio(TTS_DIR, audio_name)


@app.get("/terminal")
async def terminal_page(request: Request):
    verify_token(request)
    return HTMLResponse(TERMINAL_HTML)


@app.post("/escape")
async def send_escape(request: Request):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    subprocess.run(
        ["tmux", "send-keys", "-t", SESSION_NAME, "Escape"],
        check=True,
    )
    return {"sent": True, "key": "Escape"}


@app.get("/chat", response_class=HTMLResponse)
async def chat_ui():
    return HTMLResponse(
        content=CHAT_HTML,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
