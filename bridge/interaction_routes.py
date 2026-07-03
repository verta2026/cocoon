"""Start/send interaction route registration."""

from __future__ import annotations


def build_start_session_payload(message: str, session_name: str | None = None) -> dict:
    payload = {"message": message}
    if session_name is not None:
        payload["session"] = session_name
    return payload


def build_send_payload(
    *,
    sent: bool,
    length: int,
    reloaded: bool | None = None,
    reason: str | None = None,
) -> dict:
    payload = {"sent": sent}
    if reloaded is not None:
        payload["reloaded"] = reloaded
    if reason is not None:
        payload["reason"] = reason
    payload["length"] = length
    return payload


def register_interaction_routes(app, *, start_session, send_message) -> None:
    app.post("/start")(start_session)
    app.post("/send")(send_message)
