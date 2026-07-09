"""Generic plugin route registration."""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse


NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}


def register_json_plugin_routes(
    app,
    *,
    prefix: str,
    verify_token,
    api_request,
    state_payload=None,
    ui_html: str | None = None,
    ui_path: str | None = None,
    service_name: str = "Plugin",
) -> None:
    route_prefix = "/" + (prefix or "").strip("/")
    if route_prefix == "/":
        raise ValueError("plugin prefix is required")

    if state_payload is not None:
        @app.get(f"{route_prefix}/state")
        async def plugin_state(request: Request):
            verify_token(request)
            return state_payload()

    @app.get(f"{route_prefix}/api/{{path:path}}")
    async def plugin_api_get(path: str, request: Request):
        verify_token(request)
        return api_request(path, "GET")

    @app.post(f"{route_prefix}/api/{{path:path}}")
    async def plugin_api_post(path: str, request: Request):
        verify_token(request)
        body = await request.json()
        return api_request(path, "POST", body)

    if ui_html is not None:
        @app.get(ui_path or route_prefix, response_class=HTMLResponse)
        async def plugin_ui():
            if not ui_html:
                raise HTTPException(404, f"{service_name} UI not installed")
            return HTMLResponse(content=ui_html, headers=NO_CACHE_HEADERS)
