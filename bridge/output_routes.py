"""Output route registration."""

from __future__ import annotations


def clamp_messages_limit(limit: int, *, minimum: int = 20, maximum: int = 1000) -> int:
    return max(minimum, min(int(limit), maximum))


def build_messages_payload(
    *,
    messages: list,
    running: bool,
    busy: bool,
    source: str = "live-archive",
    auto_reload: str | None = None,
) -> dict:
    payload = {
        "messages": messages,
        "running": running,
        "busy": busy,
    }
    if auto_reload is not None:
        payload["auto_reload"] = auto_reload
    payload["source"] = source
    return payload


def build_chat_pure_payload(*, messages: list, running: bool, busy: bool) -> dict:
    """Payload for the incremental pure-chat stream (see live_archive.pure_chat_messages)."""
    return {
        "messages": messages,
        "running": running,
        "busy": busy,
    }


def register_output_routes(
    app, *, get_output, get_raw_output, get_messages=None, get_chat_pure=None
) -> None:
    app.get("/output")(get_output)
    if get_messages is not None:
        app.get("/messages")(get_messages)
    if get_chat_pure is not None:
        app.get("/chat_pure")(get_chat_pure)
    app.get("/raw-output")(get_raw_output)
