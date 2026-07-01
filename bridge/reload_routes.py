"""Reload and session-control route registration."""

from __future__ import annotations

from pydantic import BaseModel


class AutoReloadRequest(BaseModel):
    paused: bool


def register_reload_routes(
    app,
    *,
    get_forge_auto_reload,
    set_forge_auto_reload,
    reload_status,
    set_reload_force,
    clear_reload_force,
    new_session,
    continue_session,
    reload_session,
    forge_reload_session,
) -> None:
    app.get("/forge-auto-reload")(get_forge_auto_reload)
    app.post("/forge-auto-reload")(set_forge_auto_reload)
    app.get("/reload-status")(reload_status)
    app.post("/reload-force")(set_reload_force)
    app.delete("/reload-force")(clear_reload_force)
    app.post("/new-session")(new_session)
    app.post("/continue-session")(continue_session)
    app.post("/reload-session")(reload_session)
    app.post("/forge-reload-session")(forge_reload_session)
