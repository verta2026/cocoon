"""Output route registration."""

from __future__ import annotations


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


def register_output_routes(app, *, get_output, get_raw_output, get_messages=None) -> None:
    app.get("/output")(get_output)
    if get_messages is not None:
        app.get("/messages")(get_messages)
    app.get("/raw-output")(get_raw_output)
