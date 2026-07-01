"""Status route registration."""

from __future__ import annotations


def register_status_route(app, *, status) -> None:
    app.get("/status")(status)
