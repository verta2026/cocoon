"""Request authentication policy helpers for optional presence-style services."""

from __future__ import annotations

from collections.abc import Collection


TOKEN_ONLY = "token"
TOKEN_OR_COOKIE = "token_or_cookie"


def post_auth_mode(
    path: str,
    *,
    browser_write_paths: Collection[str] = (),
    token_only_paths: Collection[str] = (),
    default: str = TOKEN_ONLY,
) -> str:
    if path in browser_write_paths:
        return TOKEN_OR_COOKIE
    if path in token_only_paths:
        return TOKEN_ONLY
    return default
