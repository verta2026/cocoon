"""Environment checks for cocoon startup.

The doctor intentionally uses only the Python standard library so it can run
before FastAPI or other project dependencies are installed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import sys
from pathlib import Path


DEFAULT_TOKEN = "cocoon-default-token"


def _is_wsl() -> bool:
    try:
        version = Path("/proc/version").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return "microsoft" in version.lower() or "wsl" in version.lower()


def _is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _is_windows_claude(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.endswith(".exe") or normalized.startswith("/mnt/")


def _port_is_free(host: str, port: int) -> tuple[bool, str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
    except OSError as exc:
        return False, str(exc)
    return True, ""


def _print(status: str, message: str) -> None:
    print(f"{status} {message}")


def run_checks(strict: bool = False) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    host = os.environ.get("COCOON_HOST", "127.0.0.1")
    port_raw = os.environ.get("COCOON_PORT", "8080")
    token = os.environ.get("COCOON_TOKEN", DEFAULT_TOKEN)
    allow_root = os.environ.get("COCOON_ALLOW_ROOT") == "1"

    try:
        port = int(port_raw)
    except ValueError:
        errors.append(f"COCOON_PORT must be an integer, got {port_raw!r}")
        port = 0

    if sys.version_info < (3, 10):
        errors.append(f"Python 3.10+ is required, found {sys.version.split()[0]}")
    else:
        _print("ok", f"python {sys.version.split()[0]}")

    tmux_path = shutil.which("tmux")
    if tmux_path:
        _print("ok", f"tmux: {tmux_path}")
    else:
        errors.append("tmux is required. Install it inside the same Linux/WSL environment as cocoon.")

    claude_path = shutil.which("claude")
    if not claude_path:
        errors.append("claude is not on PATH. Install and authenticate Claude Code in this environment.")
    elif _is_windows_claude(claude_path):
        errors.append(
            f"claude resolves to a Windows path ({claude_path}). Install the Linux Claude Code CLI inside WSL."
        )
    else:
        _print("ok", f"claude: {claude_path}")
        # 登录态启发式：doctor 报 ready 但 Claude 没登录的话，首条消息会 401。
        # 凭证形态因平台/企业配置而异，所以只警告不拦截。
        cred = Path.home() / ".claude" / ".credentials.json"
        state = Path.home() / ".claude.json"
        logged_in = cred.exists()
        if not logged_in and state.exists():
            try:
                logged_in = '"oauthAccount"' in state.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                logged_in = False
        if logged_in:
            _print("ok", "claude login state found")
        else:
            warnings.append(
                "no Claude login state found for this user — run `claude` once and sign in, "
                "or the first message will fail with an auth error"
            )

    if _is_root() and not allow_root:
        errors.append(
            "cocoon should not run as root. Claude login state is per-user; run as a normal Linux user "
            "or set COCOON_ALLOW_ROOT=1 if you really know why."
        )
    elif _is_root():
        warnings.append("running as root because COCOON_ALLOW_ROOT=1 is set")
    else:
        _print("ok", f"user: {os.environ.get('USER') or os.environ.get('LOGNAME') or 'current user'}")

    home = Path.home()
    if not home.exists():
        errors.append(f"HOME does not exist: {home}")
    else:
        _print("ok", f"home: {home}")

    if _is_wsl():
        _print("ok", "WSL detected")
        if claude_path and _is_windows_claude(claude_path):
            errors.append("WSL detected, but claude points outside Linux. Use npm inside Ubuntu/WSL.")

    if token == DEFAULT_TOKEN and host not in {"127.0.0.1", "localhost"}:
        errors.append("refusing public bind with the default token. Set a strong COCOON_TOKEN first.")

    # The React build is the only frontend (/ redirects to /app/): without
    # webapp/dist the browser gets a placeholder page, not a chat. start.sh
    # builds it automatically when npm exists, so only its absence is fatal.
    npm_path = shutil.which("npm")
    dist_built = (Path(__file__).resolve().parent.parent / "webapp" / "dist" / "index.html").is_file()
    if dist_built:
        _print("ok", "web app built: webapp/dist")
    elif npm_path:
        _print("ok", f"npm: {npm_path} (web app not built yet — start.sh will build it)")
    else:
        errors.append(
            "web app is not built and npm is missing. Install Node.js, then: cd webapp && npm install && npm run build"
        )

    if port:
        free, reason = _port_is_free(host, port)
        if free:
            _print("ok", f"port available: {host}:{port}")
        elif strict:
            errors.append(f"port is not available on {host}:{port}: {reason}")
        else:
            warnings.append(f"port is not available on {host}:{port}: {reason}")

    for warning in warnings:
        _print("warn", warning)
    for error in errors:
        _print("error", error)

    if errors:
        _print("fail", "cocoon environment is not ready")
        return 1
    _print("ok", "cocoon environment looks ready")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether this environment can run cocoon.")
    parser.add_argument("--strict", action="store_true", help="treat occupied port as an error")
    args = parser.parse_args(argv)
    return run_checks(strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
