"""Push notification route registration."""

from __future__ import annotations

from fastapi import Request


def register_push_routes(
    app,
    *,
    verify_token,
    push_public_key,
    push_status,
    push_subscribe,
) -> None:
    @app.get("/push/key")
    async def get_push_key(request: Request):
        verify_token(request)
        return push_public_key()

    @app.get("/push/status")
    async def get_push_status(request: Request):
        verify_token(request)
        return push_status()

    @app.post("/push/subscribe")
    async def subscribe_push(subscription: dict, request: Request):
        verify_token(request)
        return push_subscribe(subscription)
