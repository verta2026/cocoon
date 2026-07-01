"""Generic authentication helpers for optional presence-style services."""

from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import parse_qs


def cookie_matches(cookie_header: str, *, cookie_name: str, expected_value: str) -> bool:
    if not expected_value:
        return False
    prefix = f"{cookie_name}="
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(prefix):
            return hmac.compare_digest(part.split("=", 1)[1], expected_value)
    return False


def password_matches_sha256_prefix(password: str, expected_prefix: str) -> bool:
    if not expected_prefix:
        return False
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return digest.startswith(expected_prefix)


def auth_cookie_header(
    *,
    cookie_name: str,
    cookie_value: str,
    max_age_seconds: int,
    same_site: str = "Lax",
    secure: bool = True,
    http_only: bool = True,
    path: str = "/",
) -> str:
    parts = [
        f"{cookie_name}={cookie_value}",
        f"Path={path}",
        f"Max-Age={max_age_seconds}",
        f"SameSite={same_site}",
    ]
    if secure:
        parts.append("Secure")
    if http_only:
        parts.append("HttpOnly")
    return "; ".join(parts)


def parse_login_body(raw_body: bytes, content_type: str, query: dict[str, str]) -> dict[str, str]:
    body: dict[str, str] = {}
    if raw_body:
        try:
            if "application/json" in content_type:
                parsed = json.loads(raw_body)
                if isinstance(parsed, dict):
                    body.update(parsed)
            else:
                parsed = parse_qs(raw_body.decode("utf-8", errors="replace"))
                body.update({key: values[-1] if values else "" for key, values in parsed.items()})
        except json.JSONDecodeError:
            body = {}
    body.update(query)
    return body
