"""Generic reload control state for session handoff integrations."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable


def auto_reload_status(pause_file: Path) -> dict:
    return {"paused": pause_file.exists()}


def normalized_reload_command(command: str | None) -> str:
    return (command or "").strip()


def recent_auto_reload(state_file: Path, cooldown_seconds: int) -> bool:
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return time.time() - float(data.get("time", 0)) < cooldown_seconds
    except Exception:
        return False


def mark_auto_reload(state_file: Path, reason: str, context_tokens: int = 0) -> dict:
    data = {"time": time.time(), "reason": reason, "tokens": context_tokens}
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def session_idle_seconds(current_jsonl_path: Callable[[], Path | None]) -> float:
    path = current_jsonl_path()
    if not path:
        return 0
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0


def actual_model_from_session(current_jsonl_path: Callable[[], Path | None]) -> str:
    path = current_jsonl_path()
    if not path:
        return ""
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            handle.seek(max(0, handle.tell() - 262144))
            chunk = handle.read().decode("utf-8", "ignore")
    except OSError:
        return ""

    for line in reversed(chunk.splitlines()):
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") != "assistant" or event.get("isSidechain"):
            continue
        model = (event.get("message") or {}).get("model") or ""
        if model:
            return model
    return ""


def context_window_is_1m(current_jsonl_path: Callable[[], Path | None], settings_file: Path) -> bool:
    actual = actual_model_from_session(current_jsonl_path)
    if actual:
        return "[1m]" in actual
    try:
        config = json.loads(settings_file.read_text(encoding="utf-8"))
        return "[1m]" in (config.get("model") or "")
    except Exception:
        return False


def active_context_threshold(
    current_jsonl_path: Callable[[], Path | None],
    settings_file: Path,
    threshold: int,
    threshold_1m: int,
) -> int:
    if context_window_is_1m(current_jsonl_path, settings_file):
        return threshold_1m
    return threshold


def reload_monitor_interval(context_tokens: int, threshold: int, default_interval: int) -> int:
    interval = 10 if threshold > 0 and context_tokens >= threshold * 0.8 else default_interval
    return max(5, interval)


def log_auto_reload(log_file: Path, text: str, throttle: int = 0) -> None:
    try:
        if throttle and log_file.exists():
            if time.time() - log_file.stat().st_mtime < throttle:
                return
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except OSError:
        pass


def set_auto_reload_paused(pause_file: Path, log_file: Path, paused: bool) -> dict:
    pause_file.parent.mkdir(parents=True, exist_ok=True)
    if paused:
        pause_file.write_text(
            f"manual-pause {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n",
            encoding="utf-8",
        )
        log_auto_reload(log_file, "manual pause enabled")
    else:
        try:
            pause_file.unlink()
        except FileNotFoundError:
            pass
        log_auto_reload(log_file, "manual pause disabled")
    return auto_reload_status(pause_file)


def send_reload_command(
    command: str | None,
    tmux_clear_input_func: Callable[[], None],
    tmux_clear_scrollback_func: Callable[[], None],
    tmux_send_func: Callable[[str], None],
) -> str:
    command = normalized_reload_command(command)
    if not command:
        return ""
    tmux_clear_input_func()
    tmux_clear_scrollback_func()
    tmux_send_func(command)
    return command


@contextmanager
def reload_lock(lock_dir: Path, stale_seconds: int):
    acquired = False
    try:
        lock_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            lock_dir.mkdir()
            (lock_dir / "owner.json").write_text(
                json.dumps({"pid": os.getpid(), "time": time.time()}, ensure_ascii=False),
                encoding="utf-8",
            )
            acquired = True
        except FileExistsError:
            try:
                age = time.time() - lock_dir.stat().st_mtime
                if age > stale_seconds:
                    shutil.rmtree(lock_dir, ignore_errors=True)
                    lock_dir.mkdir()
                    (lock_dir / "owner.json").write_text(
                        json.dumps(
                            {"pid": os.getpid(), "time": time.time(), "stale_reclaimed": True},
                            ensure_ascii=False,
                        ),
                        encoding="utf-8",
                    )
                    acquired = True
            except Exception:
                acquired = False
        yield acquired
    finally:
        if acquired:
            shutil.rmtree(lock_dir, ignore_errors=True)
