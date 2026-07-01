"""Generic shared-file helpers for presence-style HTTP handlers."""

from __future__ import annotations

import os
from typing import Any


def resolve_shared_file_path(data_dir: str, fname: str, *, subdir: str = "shared") -> str | None:
    """Return an in-data-dir shared file path, or None for unsafe names."""
    if ".." in fname or "/" in fname:
        return None
    return os.path.join(data_dir, subdir, fname)


def list_shared_file_metadata(data_dir: str, *, subdir: str = "shared") -> list[dict[str, Any]]:
    """List regular files in the shared directory with public-safe metadata."""
    shared_dir = os.path.join(data_dir, subdir)
    files: list[dict[str, Any]] = []
    if os.path.isdir(shared_dir):
        for name in sorted(os.listdir(shared_dir)):
            fp = os.path.join(shared_dir, name)
            if os.path.isfile(fp):
                files.append({"name": name, "size": os.path.getsize(fp)})
    return files


def send_attachment(
    handler: Any,
    file_path: str,
    filename: str,
    *,
    include_body: bool,
    content_type: str = "application/octet-stream",
) -> None:
    """Send a local file through a BaseHTTPRequestHandler-like object."""
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(os.path.getsize(file_path)))
    handler.end_headers()
    if include_body:
        with open(file_path, "rb") as f:
            handler.wfile.write(f.read())
