"""Terminal control route registration."""

from __future__ import annotations


def register_control_routes(app, *, send_escape) -> None:
    app.post("/escape")(send_escape)
