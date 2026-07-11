"""Generic bridge authentication helpers."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


def token_matches(candidate: str | None, expected: str) -> bool:
    # Fail closed on an empty expected token: an unset/blank server token must
    # never authenticate an anonymous ("") request. Without this guard both sides
    # normalize to "" and hmac.compare_digest("", "") returns True (fail-open).
    if not expected:
        return False
    return hmac.compare_digest(candidate or "", expected)


def bearer_token_matches(auth: str, expected: str) -> bool:
    if not auth.startswith("Bearer "):
        return False
    return token_matches(auth.split(" ", 1)[1], expected)


def request_token_matches(
    request: Request,
    expected: str,
    *,
    cookie_name: str = "token",
) -> bool:
    # Accept a Bearer header (XHR) or the HttpOnly session cookie (page nav and
    # <img>/<audio> requests, which the browser attaches automatically).
    # Query-string tokens are intentionally NOT accepted: a token in a URL leaks
    # into access logs, proxy logs, browser history and Referer headers — for
    # this service that is equivalent to handing over full terminal control.
    auth = request.headers.get("Authorization", "")
    cookie_token = request.cookies.get(cookie_name, "")
    return bearer_token_matches(auth, expected) or token_matches(cookie_token, expected)


def verify_request_token(
    request: Request,
    expected: str,
    *,
    cookie_name: str = "token",
) -> None:
    if request_token_matches(request, expected, cookie_name=cookie_name):
        return
    raise HTTPException(403, "Bad token")


def verify_media_token(request: Request, expected: str, query_token: str | None = None) -> None:
    # query_token is accepted for call-signature compatibility but ignored on
    # purpose (see request_token_matches): media authenticates via the HttpOnly
    # session cookie the browser sends automatically, or a Bearer header.
    if request_token_matches(request, expected):
        return
    raise HTTPException(403, "Bad token")


def login_payload(password: str, expected: str) -> dict:
    """Exchange the instance password for the API bearer token.

    The reference deployment uses a single shared secret; a deployment
    with separate login and API credentials can pass them accordingly.
    """
    if not expected or not token_matches(password, expected):
        raise HTTPException(403, "Bad password")
    return {"ok": True, "token": expected}


def register_auth_routes(app, *, login) -> None:
    app.post("/login")(login)
