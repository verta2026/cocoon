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

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    AUTO_DISMISS_PROMPTS,
    CLAUDE_PROJECTS_DIR,
    LIVE_ARCHIVE_FILE,
    LIVE_ARCHIVE_SYNC_SECONDS,
    LIVE_MESSAGES_ENABLED,
    PRIMARY_SENDER_ID,
    SEND_SIDECAR_FILE,
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
    CLEAN_START_COMMAND,
    FILES_URL_PREFIX,
    FRONTEND_DIR,
    SERVE_FRONTEND,
    REACTIONS_FILE,
    RELOAD_COMMAND,
    RELOAD_LOCK_DIR,
    RELOAD_LOCK_STALE_SECONDS,
    SESSION_NAME,
    START_COMMAND,
    TOKEN,
    TMUX_HISTORY_LIMIT,
    STICKER_DIR,
    TTS_DIR,
    UPLOAD_DIR,
    WORK_DIR,
    validate_security,
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
from bridge.live_archive import (
    live_messages as _live_messages,
    pure_chat_messages as _pure_chat_messages,
    read_live_archive_rows as _read_live_archive_rows,
    sync_live_archive as _sync_live_archive,
)
from bridge.control_routes import register_control_routes
from bridge.history_routes import register_history_routes
from bridge.interaction_routes import (
    build_send_payload as _build_send_payload,
    build_start_session_payload as _build_start_session_payload,
    register_interaction_routes,
)
from bridge.output_routes import (
    build_chat_pure_payload as _build_chat_pure_payload,
    build_messages_payload as _build_messages_payload,
    clamp_messages_limit as _clamp_messages_limit,
    register_output_routes,
)
from bridge.status_routes import build_status_payload as _build_status_payload, register_status_route
from bridge.extensions import list_extensions as _list_extensions
from bridge.reload_control import (
    auto_reload_status as _auto_reload_status,
    reload_lock as _reload_lock,
    send_reload_command as _send_reload_command,
    set_auto_reload_paused as _set_auto_reload_paused,
    set_reload_marker as _set_reload_marker,
)
from bridge.reload_routes import (
    AutoReloadRequest,
    build_auto_reload_payload as _build_auto_reload_payload,
    build_session_action_payload as _build_session_action_payload,
    register_reload_routes,
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
from bridge.upload_routes import register_upload_routes
from bridge.stickers import (
    delete_sticker_file as _delete_sticker_file,
    edit_sticker_meta as _edit_sticker_meta,
    list_sticker_items as _list_sticker_items,
    load_sticker_meta as _load_sticker_meta,
    serve_sticker_file as _serve_sticker_file,
    upload_sticker_data as _upload_sticker_data,
    upload_sticker_file as _upload_sticker_file,
)
from bridge.sticker_routes import register_sticker_routes
from bridge.frontend_routes import register_frontend_routes
from bridge.reactions import (
    apply_reaction as _apply_reaction,
    load_reactions as _load_reactions,
    recent_image_entries as _recent_image_entries,
    register_reaction_routes,
)
from bridge.tts import (
    latest_tts as _latest_tts,
    serve_tts_audio as _serve_tts_audio,
    synthesize_tts as _synthesize_tts,
)
from bridge.tts_routes import register_tts_routes
from bridge.ui import CHAT_HTML, TERMINAL_HTML
from bridge.ui_routes import register_core_ui_routes
from bridge.auth import (
    bearer_token_matches as _bearer_token_matches,
    login_payload as _login_payload,
    register_auth_routes,
    token_matches as _token_matches,
    verify_media_token as _verify_media_token,
    verify_request_token as _verify_request_token,
)

UPLOAD_DIR.mkdir(exist_ok=True)
STICKER_DIR.mkdir(exist_ok=True)
TTS_DIR.mkdir(exist_ok=True)

# Fail fast in-process on an insecure token/bind combination, so a bare
# ``uvicorn server:app`` cannot come up fail-open or publicly exposed with a
# guessable token (start.sh / doctor guards alone are bypassable).
validate_security()

app = FastAPI(title="Cocoon", docs_url=None)
SEND_LOCK = asyncio.Lock()
AUTO_RELOAD_TASK = None


def token_matches(candidate: str | None) -> bool:
    return _token_matches(candidate, TOKEN)


def bearer_token_matches(auth: str) -> bool:
    return _bearer_token_matches(auth, TOKEN)


def verify_token(request: Request):
    _verify_request_token(request, TOKEN)


def verify_media_token(request: Request, expected: str = None, token: str = None):
    # register_upload_routes 以 (request, bridge_token, query_token) 三参调用；
    # expected 缺省回落 TOKEN，兼容按 (request, token) 两参直调的旧用法。
    _verify_media_token(request, expected if expected is not None else TOKEN, token)


register_upload_routes(
    app,
    verify_token=verify_token,
    verify_media_token=verify_media_token,
    save_upload_file=_save_upload_file,
    serve_upload_file=_serve_upload_file,
    list_upload_files=_list_upload_files,
    upload_dir=UPLOAD_DIR,
    max_upload_bytes=MAX_UPLOAD_BYTES,
    bridge_token=TOKEN,
)

register_sticker_routes(
    app,
    verify_token=verify_token,
    sticker_dir=STICKER_DIR,
    sticker_meta=STICKER_DIR / "meta.json",
    serve_sticker_file=_serve_sticker_file,
    list_sticker_items=_list_sticker_items,
    upload_sticker_file=_upload_sticker_file,
    edit_sticker_meta=_edit_sticker_meta,
    delete_sticker_file=_delete_sticker_file,
    load_sticker_meta=_load_sticker_meta,
    upload_sticker_data=_upload_sticker_data,
)

register_history_routes(
    app,
    verify_token=verify_token,
    list_conversation_sessions=_list_conversation_sessions,
    read_conversation_messages=_read_conversation_messages,
    conversations_dir=CONVERSATIONS_DIR,
    wrap_sessions=True,
    wrap_messages=True,
)


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


def start_claude_clean():
    _start_claude(CLEAN_START_COMMAND, tmux_clear_input, tmux_clear_scrollback, tmux_send)


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


async def status(request: Request):
    verify_token(request)
    alive = tmux_exists()
    command = pane_command() if alive else ""
    running = claude_running() if alive else False
    dismissed_resume = dismiss_resume_summary_prompt() if running else False
    dismissed_trust = dismiss_trust_prompt() if alive else False
    return _build_status_payload(
        session_name=SESSION_NAME,
        alive=alive,
        running=running,
        command=command,
        busy=claude_busy() if running else False,
        auto_reload_paused=AUTO_RELOAD_PAUSE_FILE.exists(),
        dismissed_resume=dismissed_resume,
        dismissed_trust=dismissed_trust,
    )


register_status_route(app, status=status)


async def start_session(request: Request):
    verify_token(request)
    if tmux_exists():
        if claude_running():
            return _build_start_session_payload("Session already running")
        if _launcher_in_progress(LAUNCHER_PROCESS_PATTERN):
            raise HTTPException(409, "Launcher already in progress; not interrupting")
        start_claude()
        await asyncio.sleep(3)
        return _build_start_session_payload("Claude started in existing session")

    subprocess.run(["tmux", "set-option", "-g", "history-limit", str(TMUX_HISTORY_LIMIT)],
                   capture_output=True)
    tmux_new_session()
    await asyncio.sleep(1)
    start_claude()
    await asyncio.sleep(3)
    return _build_start_session_payload("Session started", SESSION_NAME)


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
                return _build_send_payload(sent=True, reloaded=True, length=len(msg.text))
            return _build_send_payload(sent=False, reloaded=True, length=len(msg.text))

        if dismiss_resume_summary_prompt():
            if msg.text and wait_for_claude_ready():
                tmux_send(msg.text.strip())
                return _build_send_payload(sent=True, reloaded=True, length=len(msg.text))
            return _build_send_payload(sent=False, reloaded=True, length=len(msg.text))

        if msg.text:
            tmux_send(msg.text.strip())
        else:
            subprocess.run(
                ["tmux", "send-keys", "-t", SESSION_NAME, "Enter"],
                check=True,
            )
        return _build_send_payload(sent=True, length=len(msg.text))


class LoginRequest(BaseModel):
    password: str = ""


def _request_is_https(request: Request) -> bool:
    forwarded = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
    if forwarded:
        return forwarded == "https"
    return request.url.scheme == "https"


SESSION_COOKIE_MAX_AGE = 30 * 24 * 3600


async def login(req: LoginRequest, request: Request, response: Response):
    payload = _login_payload(req.password, TOKEN)  # raises 403 on bad password
    # Set an HttpOnly session cookie so the token never has to ride in a URL
    # (media/page nav authenticate via the cookie the browser sends automatically)
    # and is not readable by JavaScript. Secure when the request arrived over
    # HTTPS; SameSite=Lax so top-level same-site navigation (e.g. /terminal)
    # still carries it.
    response.set_cookie(
        "token",
        TOKEN,
        max_age=SESSION_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_request_is_https(request),
        path="/",
    )
    return payload


register_auth_routes(app, login=login)


register_interaction_routes(app, start_session=start_session, send_message=send_message)


async def get_reactions(request: Request):
    verify_token(request)
    return _load_reactions(REACTIONS_FILE)


async def post_reaction(request: Request):
    verify_token(request)
    body = await request.json()
    msg_id = str(body.get("msg_id", ""))
    emoji = str(body.get("emoji", ""))
    sender = str(body.get("from", "user"))
    if not msg_id or not emoji:
        raise HTTPException(400, "missing msg_id or emoji")
    data, _added = _apply_reaction(REACTIONS_FILE, msg_id=msg_id, emoji=emoji, sender=sender)
    return {"ok": True, "reactions": data}


async def recent_images(request: Request):
    verify_token(request)
    return _recent_image_entries([(UPLOAD_DIR, FILES_URL_PREFIX)])


register_reaction_routes(
    app,
    get_reactions=get_reactions,
    post_reaction=post_reaction,
    recent_images=recent_images,
)


async def get_output(request: Request, lines: int = 1500):
    verify_token(request)
    return PlainTextResponse(captured_output_or_404(lines))


async def get_raw_output(request: Request, lines: int = 1500):
    verify_token(request)
    return PlainTextResponse(captured_output_or_404(lines))


_LIVE_ARCHIVE_STATE = {"path": "", "mtime": 0.0, "checked": 0.0}


def current_session_jsonl():
    try:
        candidates = CLAUDE_PROJECTS_DIR.glob("*.jsonl")
        return max(candidates, key=lambda p: p.stat().st_mtime, default=None)
    except OSError:
        return None


def sync_live_archive(force=False):
    return _sync_live_archive(
        LIVE_ARCHIVE_FILE,
        _LIVE_ARCHIVE_STATE,
        LIVE_ARCHIVE_SYNC_SECONDS,
        current_session_jsonl,
        sidecar_file=Path(SEND_SIDECAR_FILE) if SEND_SIDECAR_FILE else None,
        force=force,
    )


async def get_messages(request: Request, limit: int = 300):
    verify_token(request)
    if not tmux_exists() and not claude_running():
        raise HTTPException(404, "No active session")
    limit = _clamp_messages_limit(limit)
    running = claude_running()
    if running:
        sync_live_archive()
    messages = _live_messages(
        _read_live_archive_rows(LIVE_ARCHIVE_FILE),
        limit,
        primary_sender_id=PRIMARY_SENDER_ID,
    )
    return _build_messages_payload(
        messages=messages,
        running=running,
        busy=claude_busy() if running else False,
    )


async def get_chat_pure(request: Request, since: str = ""):
    verify_token(request)
    running = claude_running() if tmux_exists() else False
    if running:
        sync_live_archive()
    messages = _pure_chat_messages(
        _read_live_archive_rows(LIVE_ARCHIVE_FILE),
        since,
        primary_sender_id=PRIMARY_SENDER_ID,
    )
    return _build_chat_pure_payload(
        messages=messages,
        running=running,
        busy=claude_busy() if running else False,
    )


register_output_routes(
    app,
    get_output=get_output,
    get_raw_output=get_raw_output,
    get_messages=get_messages if LIVE_MESSAGES_ENABLED else None,
    get_chat_pure=get_chat_pure if LIVE_MESSAGES_ENABLED else None,
)


@app.get("/extensions")
async def extensions(request: Request):
    verify_token(request)
    return {"extensions": _list_extensions(EXTENSIONS_FILE)}


async def get_forge_auto_reload(request: Request):
    verify_token(request)
    return _build_auto_reload_payload(_auto_reload_status(AUTO_RELOAD_PAUSE_FILE)["paused"])


async def set_forge_auto_reload(req: AutoReloadRequest, request: Request):
    verify_token(request)
    return _build_auto_reload_payload(
        _set_auto_reload_paused(
            AUTO_RELOAD_PAUSE_FILE, AUTO_RELOAD_LOG_FILE, req.paused, force=req.force
        )["paused"]
    )


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


async def set_reload_force(request: Request):
    verify_token(request)
    return _set_reload_marker(AUTO_RELOAD_FORCE_FILE, True, "manual-force")


async def clear_reload_force(request: Request):
    verify_token(request)
    return _set_reload_marker(AUTO_RELOAD_FORCE_FILE, False, "manual-force")


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
        return _build_session_action_payload("Claude started but may still be loading")
    return _build_session_action_payload("New session started")


async def clean_session(request: Request):
    """Exit the current session and launch a clean, context-free one.

    Same plumbing as a normal session but launched via CLEAN_START_COMMAND
    (no resume, no seeded context). Clean is a one-shot launch mode; it is
    never persisted as the default.
    """
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
    start_claude_clean()
    ready = await asyncio.to_thread(wait_for_claude_ready)
    if not ready:
        return _build_session_action_payload("Clean session starting", mode="clean")
    return _build_session_action_payload("Clean session started", mode="clean")


async def continue_session(request: Request):
    verify_token(request)
    raise HTTPException(410, "continue-session is disabled; use new-session or a reload integration")


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
    return _build_session_action_payload("Reload command sent", command=command)


async def forge_reload_session(request: Request):
    return await reload_session(request)


register_reload_routes(
    app,
    get_forge_auto_reload=get_forge_auto_reload,
    set_forge_auto_reload=set_forge_auto_reload,
    reload_status=reload_status,
    set_reload_force=set_reload_force,
    clear_reload_force=clear_reload_force,
    new_session=new_session,
    clean_session=clean_session,
    continue_session=continue_session,
    reload_session=reload_session,
    forge_reload_session=forge_reload_session,
)


register_tts_routes(
    app,
    verify_token=verify_token,
    verify_media_token=verify_media_token,
    latest_tts=_latest_tts,
    synthesize_tts=_synthesize_tts,
    serve_tts_audio=_serve_tts_audio,
    tts_dir=TTS_DIR,
)


async def terminal_page(request: Request):
    verify_token(request)
    return HTMLResponse(TERMINAL_HTML)


async def send_escape(request: Request):
    verify_token(request)
    if not tmux_exists():
        raise HTTPException(404, "No active session")
    subprocess.run(
        ["tmux", "send-keys", "-t", SESSION_NAME, "Escape"],
        check=True,
    )
    return {"sent": True, "key": "Escape"}


register_control_routes(app, send_escape=send_escape)


async def chat_ui():
    return HTMLResponse(
        content=CHAT_HTML,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


register_core_ui_routes(app, chat_ui=chat_ui, terminal_page=terminal_page)

if SERVE_FRONTEND and FRONTEND_DIR.is_dir():
    register_frontend_routes(app, frontend_dir=FRONTEND_DIR)
