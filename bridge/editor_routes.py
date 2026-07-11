"""File editor routes — browse, read, write and download inside a sandboxed tree.

The editor page (frontend/editor.html) drives these. All paths are relative to
a configured root and pass two gates: the lexical filter from
presence.editor_files (no "..", no blocked prefixes/files) and a resolved-path
containment check so symlinks cannot lead outside the root. Writes only touch
files that already exist — the editor edits a workspace, it does not create or
delete anything.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Request, Response
from fastapi.responses import FileResponse, JSONResponse

from presence.editor_files import (
    download_content_type,
    download_filename_header,
    is_safe_relative_path,
    with_utf8_bom_if_needed,
)

# Extensions that get a UTF-8 BOM on download so Excel/Notepad detect the
# encoding (same list the reference presence server uses).
BOM_EXTENSIONS = {".md", ".txt", ".csv", ".tsv", ".log"}


def resolve_editor_path(root: Path, rel: str, *, blocked_prefixes, blocked_files) -> Path | None:
    """Map a client-supplied relative path to an absolute one, or None if it
    fails any gate: lexical filter, or resolving (symlinks included) to a
    location outside the root."""
    rel = rel.strip("/")
    if rel and not is_safe_relative_path(
        rel, blocked_prefixes=blocked_prefixes, blocked_files=blocked_files
    ):
        return None
    root = root.resolve()
    candidate = (root / rel) if rel else root
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return resolved


def register_editor_routes(
    app,
    *,
    verify_token,
    verify_media_token,
    bridge_token: str,
    root: Path,
    blocked_prefixes,
    blocked_files,
    max_bytes: int = 0,
) -> None:
    root = Path(root)

    def _resolve(rel: str) -> Path | None:
        return resolve_editor_path(
            root, rel, blocked_prefixes=blocked_prefixes, blocked_files=blocked_files
        )

    def _err(status: int, message: str) -> JSONResponse:
        # The editor page reads {"error": ...}; keep that shape instead of
        # FastAPI's {"detail": ...}.
        return JSONResponse({"error": message}, status_code=status)

    @app.get("/editor/ls")
    async def editor_ls(request: Request, path: str = ""):
        verify_token(request)
        rel = path.strip("/")
        abs_path = _resolve(rel)
        if abs_path is None:
            return _err(403, "blocked path")
        if not abs_path.is_dir():
            return _err(404, "not a directory")
        items = []
        for name in sorted(os.listdir(abs_path)):
            child_rel = f"{rel}/{name}" if rel else name
            if not is_safe_relative_path(
                child_rel, blocked_prefixes=blocked_prefixes, blocked_files=blocked_files
            ):
                continue
            if name.startswith("."):
                continue
            child = abs_path / name
            is_dir = child.is_dir()
            try:
                size = 0 if is_dir else child.stat().st_size
            except OSError:
                continue
            items.append({"name": name, "dir": is_dir, "size": size})
        return {"path": rel, "items": items}

    @app.get("/editor/read")
    async def editor_read(request: Request, path: str = ""):
        verify_token(request)
        rel = path.strip("/")
        abs_path = _resolve(rel) if rel else None
        if abs_path is None:
            return _err(403, "blocked path")
        if not abs_path.is_file():
            return _err(404, "not found")
        if max_bytes and abs_path.stat().st_size > max_bytes:
            return _err(413, "file too large")
        try:
            content = abs_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return _err(400, "binary file")
        return {"path": rel, "content": content}

    @app.post("/editor/write")
    async def editor_write(request: Request):
        verify_token(request)
        body = await request.json()
        rel = str(body.get("path", "")).strip("/")
        content = body.get("content")
        if not rel or content is None or not isinstance(content, str):
            return _err(400, "missing path or content")
        if max_bytes and len(content.encode("utf-8")) > max_bytes:
            return _err(413, "content too large")
        abs_path = _resolve(rel)
        if abs_path is None:
            return _err(403, "blocked path")
        if not abs_path.is_file():
            return _err(404, "file not found")
        abs_path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": rel, "size": len(content)}

    @app.get("/editor/download")
    async def editor_download(request: Request, path: str = "", token: str = None):
        # Download rides an <a href> which cannot carry an Authorization
        # header; the HttpOnly session cookie authenticates it. The token
        # query param exists for signature compatibility but is ignored —
        # query-string tokens leak into logs (see bridge.auth).
        verify_media_token(request, bridge_token, token)
        rel = path.strip("/")
        abs_path = _resolve(rel) if rel else None
        if abs_path is None:
            return _err(403, "blocked path")
        if not abs_path.is_file():
            return _err(404, "not found")
        filename = abs_path.name
        # BOM 兼容只对小文本文件有意义；其余（含大文件）流式发，
        # read_bytes 全量进内存对大文件是内存放大面
        suffix = abs_path.suffix.lower()
        if suffix not in BOM_EXTENSIONS or abs_path.stat().st_size > 16 * 1024 * 1024:
            return FileResponse(
                abs_path,
                media_type=download_content_type(filename),
                headers={"Content-Disposition": download_filename_header(filename)},
            )
        data = abs_path.read_bytes()
        data = with_utf8_bom_if_needed(data, filename, BOM_EXTENSIONS)
        return Response(
            content=data,
            media_type=download_content_type(filename),
            headers={"Content-Disposition": download_filename_header(filename)},
        )
