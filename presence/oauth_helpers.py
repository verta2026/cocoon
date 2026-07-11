"""Generic OAuth 2.0 helper functions."""

from __future__ import annotations

import base64
import hashlib
from urllib.parse import urlencode


def b64url_no_padding(data: bytes) -> str:
    """Return URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def pkce_s256_challenge(verifier: str) -> str:
    """Build the PKCE S256 code challenge for a verifier."""
    return b64url_no_padding(hashlib.sha256(verifier.encode()).digest())


def basic_auth_header(client_id: str | None, client_secret: str | None) -> str | None:
    """Build an OAuth Basic auth header when both client fields exist."""
    if not client_id or not client_secret:
        return None
    raw = f"{client_id}:{client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def authorization_url(base_url: str, params: dict[str, str]) -> str:
    """Append URL-encoded OAuth authorization params to a base URL."""
    return f"{base_url}?{urlencode(params)}"
