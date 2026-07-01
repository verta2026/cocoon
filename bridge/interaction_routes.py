"""Start/send interaction route registration."""

from __future__ import annotations


def register_interaction_routes(app, *, start_session, send_message) -> None:
    app.post("/start")(start_session)
    app.post("/send")(send_message)
