"""Terminal control route registration."""

from __future__ import annotations

# 白名单键名 → tmux send-keys 键。终端页的方向/确认键只能从这里选，
# 任意字符串直达 send-keys 就是命令注入面
TERMINAL_KEYS = {
    "up": "Up",
    "down": "Down",
    "enter": "Enter",
    "esc": "Escape",
}


def resolve_terminal_key(name) -> str | None:
    if not isinstance(name, str):
        return None
    return TERMINAL_KEYS.get(name.strip().lower())


def register_control_routes(app, *, send_escape, send_key=None) -> None:
    app.post("/escape")(send_escape)
    if send_key is not None:
        app.post("/key")(send_key)
