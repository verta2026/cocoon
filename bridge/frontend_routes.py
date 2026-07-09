"""Serve the bundled chat frontend from the reference server."""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse

from bridge.paths import safe_child_path

_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
}


def _serve(path: Path) -> FileResponse:
    media_type = _MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media_type)


def config_js_path(frontend_dir: Path) -> Path:
    """The instance config, falling back to the shipped template."""
    instance = frontend_dir / "config.js"
    return instance if instance.is_file() else frontend_dir / "config.example.js"


def register_frontend_routes(app, *, frontend_dir: Path) -> None:
    frontend_dir = Path(frontend_dir)

    @app.get("/")
    async def frontend_index():
        return _serve(safe_child_path(frontend_dir, "chat.html"))

    @app.get("/login.html")
    async def frontend_login():
        return _serve(safe_child_path(frontend_dir, "login.html"))

    @app.get("/config.js")
    async def frontend_config():
        return _serve(config_js_path(frontend_dir))

    @app.get("/src/{name}")
    async def frontend_src(name: str):
        return _serve(safe_child_path(frontend_dir / "src", name))

    @app.get("/{name}.png")
    async def frontend_image(name: str):
        return _serve(safe_child_path(frontend_dir, f"{name}.png", suffix=".png"))
