"""Core UI route registration."""

from __future__ import annotations

from fastapi.responses import HTMLResponse


def register_core_ui_routes(app, *, chat_ui, terminal_page, history_ui=None) -> None:
    if history_ui is not None:
        app.get("/chat-history", response_class=HTMLResponse)(history_ui)
    app.get("/terminal")(terminal_page)
    app.get("/chat", response_class=HTMLResponse)(chat_ui)
