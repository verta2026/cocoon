#!/usr/bin/env python3
"""
Cocoon — a web chat UI for Claude Code via tmux.

POST /send    — send a message to Claude Code
GET  /output  — get latest terminal output
GET  /status  — session status
POST /start   — start Claude Code session
GET  /raw-output — get latest raw terminal output
GET  /chat    — chat UI
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    AUTO_DISMISS_PROMPTS,
    AUTO_RELOAD_CHECK_INTERVAL_SECONDS,
    AUTO_RELOAD_CONTEXT_THRESHOLD,
    AUTO_RELOAD_CONTEXT_THRESHOLD_1M,
    AUTO_RELOAD_COOLDOWN_SECONDS,
    AUTO_RELOAD_DRYRUN_FILE,
    AUTO_RELOAD_ENABLED,
    AUTO_RELOAD_FORCE_FILE,
    AUTO_RELOAD_IDLE_MIN_CONTEXT,
    AUTO_RELOAD_IDLE_SECONDS,
    AUTO_RELOAD_LOG_FILE,
    AUTO_RELOAD_PAUSE_FILE,
    AUTO_RELOAD_STATE_FILE,
    CONVERSATIONS_DIR,
    EXTENSIONS_FILE,
    LAUNCHER_PROCESS_PATTERN,
    MAX_UPLOAD_BYTES,
    RELOAD_COMMAND,
    RELOAD_LOCK_DIR,
    RELOAD_LOCK_STALE_SECONDS,
    SESSION_NAME,
    START_COMMAND,
    TOKEN,
    TMUX_HISTORY_LIMIT,
    TTS_DIR,
    UPLOAD_DIR,
    WORK_DIR,
)
from bridge.session import (
    launcher_in_progress as _launcher_in_progress,
    start_claude as _start_claude,
    start_tmux_session as _start_tmux_session,
)
from bridge.history import (
    list_conversation_sessions as _list_conversation_sessions,
    read_conversation_messages as _read_conversation_messages,
)
from bridge.extensions import list_extensions as _list_extensions
from bridge.reload_control import (
    auto_reload_status as _auto_reload_status,
    reload_lock as _reload_lock,
    send_reload_command as _send_reload_command,
    set_auto_reload_paused as _set_auto_reload_paused,
    set_reload_marker as _set_reload_marker,
)
from bridge.tmux import (
    claude_busy as _claude_busy,
    claude_running as _claude_running,
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
    list_upload_files as _list_upload_files,
    save_upload_file as _save_upload_file,
    serve_upload_file as _serve_upload_file,
)
from bridge.tts import (
    latest_tts as _latest_tts,
    serve_tts_audio as _serve_tts_audio,
    synthesize_tts as _synthesize_tts,
)
from bridge.ui import CHAT_HTML, TERMINAL_HTML
from bridge.auth import (
    bearer_token_matches as _bearer_token_matches,
    token_matches as _token_matches,
    verify_request_token as _verify_request_token,
)

UPLOAD_DIR.mkdir(exist_ok=True)
TTS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Cocoon", docs_url=None)
SEND_LOCK = asyncio.Lock()
AUTO_RELOAD_TASK = None


def token_matches(candidate: str | None) -> bool:
    return _token_matches(candidate, TOKEN)


def bearer_token_matches(auth: str) -> bool:
    return _bearer_token_matches(auth, TOKEN)


def verify_token(request: Request):
    _verify_request_token(request, TOKEN)


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


def claude_running():
    return _claude_running(SESSION_NAME)


def tmux_capture(lines=200):
    return _tmux_capture(SESSION_NAME, lines)


def tmux_new_session():
    _start_tmux_session(SESSION_NAME, WORK_DIR, tmux_send)


def start_claude():
    _start_claude(START_COMMAND, tmux_clear_input, tmux_clear_scrollback, tmux_send)


def send_reload_command():
    return _send_reload_command(RELOAD_COMMAND, tmux_clear_input, tmux_clear_scrollback, tmux_send)


def dismiss_resume_summary_prompt():
    if not AUTO_DISMISS_PROMPTS:
        return False
    return _dismiss_resume_summary_prompt(SESSION_NAME)


def dismiss_rating_prompt():
    if not AUTO_DISMISS_PROMPTS:
        return False
    return _dismiss_rating_prompt(SESSION_NAME)


def dismiss_trust_prompt():
    if not AUTO_DISMISS_PROMPTS:
        return False
    return _dismiss_trust_prompt(SESSION_NAME)


def wait_for_claude_ready(timeout=70):
    return _wait_for_claude_ready(SESSION_NAME, timeout, auto_dismiss=AUTO_DISMISS_PROMPTS)


def captured_output_or_404(lines=1500):
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    return tmux_capture(lines)


def start_auto_reload_monitor(*, create_task=asyncio.create_task, monitor_coro=None):
    global AUTO_RELOAD_TASK
    if not AUTO_RELOAD_ENABLED:
        return None
    if AUTO_RELOAD_TASK is not None and not AUTO_RELOAD_TASK.done():
        return AUTO_RELOAD_TASK
    if monitor_coro is None:
        raise RuntimeError("Auto reload monitor coroutine is not configured")
    AUTO_RELOAD_TASK = create_task(monitor_coro)
    return AUTO_RELOAD_TASK


class Message(BaseModel):
    text: str


class TtsRequest(BaseModel):
    text: str
    emotion: Optional[str] = None
    source: str = "frontend"


class AutoReloadRequest(BaseModel):
    paused: bool


@app.get("/status")
async def status(request: Request):
    verify_token(request)
    alive = tmux_exists()
    command = pane_command() if alive else ""
    running = claude_running() if alive else False
    dismissed_resume = dismiss_resume_summary_prompt() if running else False
    dismissed_trust = dismiss_trust_prompt() if alive else False
    return {
        "session": SESSION_NAME,
        "alive": alive,
        "running": running,
        "command": command,
        "busy": claude_busy() if running else False,
        "auto_reload_paused": AUTO_RELOAD_PAUSE_FILE.exists(),
        "dismissed_resume": dismissed_resume,
        "dismissed_trust": dismissed_trust,
    }


@app.post("/start")
async def start_session(request: Request):
    verify_token(request)
    if tmux_exists():
        if claude_running():
            return {"message": "Session already running"}
        if _launcher_in_progress(LAUNCHER_PROCESS_PATTERN):
            raise HTTPException(409, "Launcher already in progress; not interrupting")
        start_claude()
        await asyncio.sleep(3)
        return {"message": "Claude started in existing session"}

    subprocess.run(["tmux", "set-option", "-g", "history-limit", str(TMUX_HISTORY_LIMIT)],
                   capture_output=True)
    tmux_new_session()
    await asyncio.sleep(1)
    start_claude()
    await asyncio.sleep(3)
    return {"message": "Session started", "session": SESSION_NAME}


@app.post("/send")
async def send_message(msg: Message, request: Request):
    verify_token(request)
    async with SEND_LOCK:
        if not tmux_exists():
            raise HTTPException(404, "No active session")

        if not claude_running():
            if _launcher_in_progress(LAUNCHER_PROCESS_PATTERN):
                raise HTTPException(409, "Launcher already in progress; not interrupting")
            start_claude()
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
async def get_output(request: Request, lines: int = 1500):
    verify_token(request)
    return PlainTextResponse(captured_output_or_404(lines))


@app.get("/raw-output")
async def get_raw_output(request: Request, lines: int = 1500):
    verify_token(request)
    return PlainTextResponse(captured_output_or_404(lines))


@app.get("/history")
async def history(request: Request):
    verify_token(request)
    return {"sessions": _list_conversation_sessions(CONVERSATIONS_DIR)}


@app.get("/history/{file_id:path}")
async def history_messages(file_id: str, request: Request):
    verify_token(request)
    return {"file": file_id, "messages": _read_conversation_messages(CONVERSATIONS_DIR, file_id)}


@app.get("/extensions")
async def extensions(request: Request):
    verify_token(request)
    return {"extensions": _list_extensions(EXTENSIONS_FILE)}


@app.get("/forge-auto-reload")
async def get_forge_auto_reload(request: Request):
    verify_token(request)
    return _auto_reload_status(AUTO_RELOAD_PAUSE_FILE)


@app.post("/forge-auto-reload")
async def set_forge_auto_reload(req: AutoReloadRequest, request: Request):
    verify_token(request)
    return _set_auto_reload_paused(AUTO_RELOAD_PAUSE_FILE, AUTO_RELOAD_LOG_FILE, req.paused)


@app.get("/reload-status")
async def reload_status(request: Request):
    verify_token(request)
    return {
        "reload_configured": bool(RELOAD_COMMAND),
        "auto_reload_enabled": AUTO_RELOAD_ENABLED,
        "auto_reload_paused": AUTO_RELOAD_PAUSE_FILE.exists(),
        "auto_reload_dryrun": AUTO_RELOAD_DRYRUN_FILE.exists(),
        "auto_reload_force_pending": AUTO_RELOAD_FORCE_FILE.exists(),
        "reload_lock_exists": RELOAD_LOCK_DIR.exists(),
        "reload_lock_stale_seconds": RELOAD_LOCK_STALE_SECONDS,
        "auto_reload_state_file": str(AUTO_RELOAD_STATE_FILE),
        "auto_reload_thresholds": {
            "context_tokens": AUTO_RELOAD_CONTEXT_THRESHOLD,
            "context_tokens_1m": AUTO_RELOAD_CONTEXT_THRESHOLD_1M,
            "idle_min_context": AUTO_RELOAD_IDLE_MIN_CONTEXT,
            "idle_seconds": AUTO_RELOAD_IDLE_SECONDS,
            "cooldown": AUTO_RELOAD_COOLDOWN_SECONDS,
            "check_interval": AUTO_RELOAD_CHECK_INTERVAL_SECONDS,
        },
    }


@app.post("/reload-force")
async def set_reload_force(request: Request):
    verify_token(request)
    return _set_reload_marker(AUTO_RELOAD_FORCE_FILE, True, "manual-force")


@app.delete("/reload-force")
async def clear_reload_force(request: Request):
    verify_token(request)
    return _set_reload_marker(AUTO_RELOAD_FORCE_FILE, False, "manual-force")


@app.post("/new-session")
async def new_session(request: Request):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    if claude_running():
        tmux_clear_input()
        tmux_send("/exit")
        for _ in range(40):
            await asyncio.sleep(0.5)
            dismiss_rating_prompt()
            if not claude_running():
                break
        else:
            raise HTTPException(409, "Claude did not exit; try again")
    tmux_clear_scrollback()
    if _launcher_in_progress(LAUNCHER_PROCESS_PATTERN):
        raise HTTPException(409, "Launcher already in progress; not interrupting")
    start_claude()
    ready = await asyncio.to_thread(wait_for_claude_ready)
    if not ready:
        return {"message": "Claude started but may still be loading"}
    return {"message": "New session started"}


@app.post("/continue-session")
async def continue_session(request: Request):
    verify_token(request)
    raise HTTPException(410, "continue-session is disabled; use new-session or a reload integration")


@app.post("/reload-session")
async def reload_session(request: Request):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    with _reload_lock(RELOAD_LOCK_DIR, RELOAD_LOCK_STALE_SECONDS) as locked:
        if not locked:
            raise HTTPException(409, "Reload already running")
        command = send_reload_command()
        if not command:
            raise HTTPException(501, "Reload command is not configured")
    return {"message": "Reload command sent", "command": command}


@app.post("/forge-reload-session")
async def forge_reload_session(request: Request):
    return await reload_session(request)


@app.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    verify_token(request)
    return _save_upload_file(UPLOAD_DIR, file, MAX_UPLOAD_BYTES)


@app.get("/files")
async def list_files(request: Request):
    verify_token(request)
    return {"files": _list_upload_files(UPLOAD_DIR)}


@app.get("/files/{filename}")
async def serve_file(filename: str, request: Request, token: str = None):
    auth = request.headers.get("Authorization", "")
    if bearer_token_matches(auth):
        pass
    elif token_matches(token):
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
    if bearer_token_matches(auth):
        pass
    elif token_matches(token):
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
