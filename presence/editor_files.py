"""Generic file policy helpers for presence-style editor routes."""

from __future__ import annotations

import mimetypes
import os
from urllib.parse import quote


def is_safe_relative_path(
    rel_path: str,
    *,
    blocked_prefixes: set[str] | frozenset[str] = frozenset(),
    blocked_files: set[str] | frozenset[str] = frozenset(),
) -> bool:
    """Return False when a relative path escapes or matches blocked entries."""
    parts = rel_path.split("/")
    for part in parts:
        if part.startswith(".."):
            return False
    for blocked in blocked_prefixes:
        if rel_path.startswith(blocked):
            return False
    if os.path.basename(rel_path) in blocked_files:
        return False
    return True


def download_filename_header(filename: str) -> str:
    """Build an RFC 5987-compatible attachment filename header."""
    fallback = filename.encode("ascii", "ignore").decode("ascii").strip()
    fallback = fallback.replace("\\", "_").replace('"', "_")
    if not fallback or fallback.startswith("."):
        fallback = "download" + os.path.splitext(filename)[1]
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def download_content_type(filename: str) -> str:
    """Guess a download content type and add UTF-8 charset for text-like files."""
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    if content_type.startswith("text/") or filename.endswith((".md", ".json", ".py", ".js", ".css", ".html")):
        content_type += "; charset=utf-8"
    return content_type


def with_utf8_bom_if_needed(data: bytes, filename: str, bom_extensions: set[str] | frozenset[str]) -> bytes:
    """Prefix UTF-8 BOM for configured text file extensions when absent."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in bom_extensions and not data.startswith(b"\xef\xbb\xbf"):
        return b"\xef\xbb\xbf" + data
    return data
