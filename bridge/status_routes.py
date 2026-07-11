"""Status route registration."""

from __future__ import annotations


def build_status_payload(
    *,
    session_name: str,
    alive: bool,
    running: bool,
    command: str,
    busy: bool,
    auto_reload_paused: bool,
    dismissed_resume: bool,
    dismissed_trust: bool | None = None,
    mode: str | None = None,
    active_mode: str | None = None,
    auto_reload: str | None = None,
    context_tokens: int | None = None,
    active_threshold: int | None = None,
    context_window_1m: bool | None = None,
    idle_seconds: int | None = None,
    idle_min_context: int | None = None,
    check_interval_seconds: int | None = None,
    cooldown_seconds: int | None = None,
    session_bytes: int | None = None,
    live_archive: dict | None = None,
) -> dict:
    payload = {
        "session": session_name,
        "alive": alive,
        "running": running,
        "command": command,
        "busy": busy,
        "auto_reload_paused": auto_reload_paused,
        "dismissed_resume": dismissed_resume,
    }
    if dismissed_trust is not None:
        payload["dismissed_trust"] = dismissed_trust
    if mode is not None:
        payload["mode"] = mode
    if active_mode is not None:
        payload["active_mode"] = active_mode
    if auto_reload is not None:
        payload["auto_reload"] = auto_reload
    if context_tokens is not None:
        payload["context_tokens"] = context_tokens
    if active_threshold is not None:
        payload["auto_reload_thresholds"] = {
            "context_tokens": active_threshold,
            "window_1m": context_window_1m,
            "idle_seconds": idle_seconds,
            "idle_min_context": idle_min_context,
            "check_interval": check_interval_seconds,
            "cooldown": cooldown_seconds,
        }
    if session_bytes is not None:
        payload["session_bytes"] = session_bytes
    if live_archive is not None:
        payload["live_archive"] = live_archive
    return payload


def register_status_route(app, *, status) -> None:
    app.get("/status")(status)
