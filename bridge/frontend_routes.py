"""Serve the bundled chat frontend from the reference server."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

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


def load_private_config(frontend_dir: Path) -> dict:
    """Identity fields (names, avatars, channel-id map) live in
    config.private.json and are only handed out after auth — config.js is
    public (the login page needs it), so identity must not ride in it."""
    path = frontend_dir / "config.private.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def register_frontend_routes(app, *, frontend_dir: Path, verify_token=None) -> None:
    frontend_dir = Path(frontend_dir)

    @app.get("/")
    async def frontend_index():
        # 聊天 UI 只有 React 构建一个版本，根路径直通
        return RedirectResponse("/app/", status_code=307)

    if verify_token is not None:
        @app.get("/app-config")
        async def frontend_app_config(request: Request):
            verify_token(request)
            return load_private_config(frontend_dir)

    @app.get("/login.html")
    async def frontend_login():
        return _serve(safe_child_path(frontend_dir, "login.html"))

    @app.get("/editor.html")
    async def frontend_editor():
        return _serve(safe_child_path(frontend_dir, "editor.html"))

    @app.get("/frost_tile_gray.webp")
    async def frontend_frost_tile():
        # chat.css 的折叠线磨砂纹理用根绝对路径引用（家里由静态站服务，
        # 参考桥自己发）；不进 Vite——Node18 下 public 目录哈希路径会炸
        return _serve(safe_child_path(frontend_dir, "frost_tile_gray.webp"))

    @app.get("/vendor/{name}")
    async def frontend_vendor(name: str):
        # 三方 JS 本地化：marked/hljs/DOMPurify 锁版本入仓，不从 CDN 执行
        return _serve(safe_child_path(frontend_dir / "vendor", name))

    @app.get("/config.js")
    async def frontend_config():
        return _serve(config_js_path(frontend_dir))

    @app.get("/{name}.png")
    async def frontend_image(name: str):
        return _serve(safe_child_path(frontend_dir, f"{name}.png", suffix=".png"))


def register_webapp_routes(app, *, webapp_dist: Path, frontend_dir: Path | None = None) -> None:
    """Serve the React webapp build (webapp/dist) at /app/ alongside the
    classic frontend. Callers register this only when a build exists, so
    deployments without Node lose nothing. Assets use relative paths
    (vite base './'), hence the trailing-slash redirect."""
    webapp_dist = Path(webapp_dist)

    if frontend_dir is not None:
        @app.get("/app/config.js")
        async def webapp_config():
            # HTML 用相对路径 ./config.js 引它：挂在子路径反代（/test/app/）
            # 下也能拉到；内容和根 /config.js 完全同源
            return _serve(config_js_path(Path(frontend_dir)))

    @app.get("/app")
    async def webapp_root_redirect():
        return RedirectResponse("/app/", status_code=307)

    @app.get("/app/")
    async def webapp_index():
        if not (webapp_dist / "index.html").is_file():
            # 没构建时给指路牌而不是 404（根路径重定向到这里，裸 404 无从排查）
            return HTMLResponse(
                "<h3>React app not built yet</h3>"
                "<p>Run: <code>cd webapp &amp;&amp; npm install &amp;&amp; npm run build</code>, "
                "then restart the server.</p>",
                status_code=503,
            )
        return _serve(safe_child_path(webapp_dist, "index.html"))

    @app.get("/app/login.html")
    async def webapp_login():
        return _serve(safe_child_path(webapp_dist, "login.html"))

    @app.get("/app/assets/{name}")
    async def webapp_asset(name: str):
        return _serve(safe_child_path(webapp_dist / "assets", name))
