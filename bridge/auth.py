"""Generic bridge authentication helpers."""

from __future__ import annotations

import hmac

from fastapi import HTTPException, Request


def token_matches(candidate: str | None, expected: str) -> bool:
    return hmac.compare_digest(candidate or "", expected or "")


def bearer_token_matches(auth: str, expected: str) -> bool:
    if not auth.startswith("Bearer "):
        return False
    return token_matches(auth.split(" ", 1)[1], expected)


def request_token_matches(
    request: Request,
    expected: str,
    *,
    cookie_name: str = "token",
    query_name: str = "token",
) -> bool:
    auth = request.headers.get("Authorization", "")
    cookie_token = request.cookies.get(cookie_name, "")
    query_token = request.query_params.get(query_name, "")
    return (
        bearer_token_matches(auth, expected)
        or token_matches(cookie_token, expected)
        or token_matches(query_token, expected)
    )


def verify_request_token(
    request: Request,
    expected: str,
    *,
    cookie_name: str = "token",
    query_name: str = "token",
) -> None:
    if request_token_matches(request, expected, cookie_name=cookie_name, query_name=query_name):
        return
    raise HTTPException(403, "Bad token")
