"""Generic reload control state for session handoff integrations."""

from __future__ import annotations

import asyncio
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


def choose_reload_reason(
    *,
    force: bool,
    tail_text: str,
    context_tokens: int,
    active_threshold: int,
    idle_seconds: float,
    idle_min_context: int,
    idle_threshold_seconds: int,
) -> str:
    if force:
        return "manual-force"
    if "API Error:" in (tail_text or ""):
        return "api-error"
    if active_threshold > 0 and context_tokens >= active_threshold:
        return f"context-tokens:{context_tokens}/{active_threshold}"
    if context_tokens >= idle_min_context and idle_seconds >= idle_threshold_seconds:
        return f"idle-cache-expired:{context_tokens}@{int(idle_seconds / 60)}min"
    return ""


def choose_reload_action(reason: str, *, recent: bool, force: bool, dryrun: bool) -> str:
    if not reason:
        return "skip"
    if recent and not force:
        return "skip"
    if dryrun and not force:
        return "dry-run"
    return "fire"


def build_reload_decision(
    *,
    force: bool,
    tail_text: str,
    context_tokens: int,
    active_threshold: int,
    idle_seconds: float,
    idle_min_context: int,
    idle_threshold_seconds: int,
    recent: bool,
    dryrun: bool,
) -> dict:
    reason = choose_reload_reason(
        force=force,
        tail_text=tail_text,
        context_tokens=context_tokens,
        active_threshold=active_threshold,
        idle_seconds=idle_seconds,
        idle_min_context=idle_min_context,
        idle_threshold_seconds=idle_threshold_seconds,
    )
    action = choose_reload_action(reason, recent=recent, force=force, dryrun=dryrun)
    return {
        "action": action,
        "reason": reason,
        "force": force,
        "recent": recent,
        "dryrun": dryrun,
        "context_tokens": context_tokens,
        "active_threshold": active_threshold,
    }


def evaluate_auto_reload_once(
    *,
    force_file: Path,
    dryrun_file: Path,
    state_file: Path,
    cooldown_seconds: int,
    tail_text: str,
    context_tokens: int,
    active_threshold: int,
    idle_seconds: float,
    idle_min_context: int,
    idle_threshold_seconds: int,
    consume_force: bool = True,
) -> dict:
    force = reload_marker_pending(force_file)
    decision = build_reload_decision(
        force=force,
        tail_text=tail_text,
        context_tokens=context_tokens,
        active_threshold=active_threshold,
        idle_seconds=idle_seconds,
        idle_min_context=idle_min_context,
        idle_threshold_seconds=idle_threshold_seconds,
        recent=recent_auto_reload(state_file, cooldown_seconds),
        dryrun=dryrun_file.exists(),
    )
    if consume_force and force and decision["reason"] == "manual-force":
        decision["force_consumed"] = consume_reload_marker(force_file)
    else:
        decision["force_consumed"] = False
    return decision


def run_auto_reload_tick(
    *,
    force_file: Path,
    dryrun_file: Path,
    state_file: Path,
    log_file: Path,
    cooldown_seconds: int,
    tail_text: str,
    context_tokens: int,
    active_threshold: int,
    idle_seconds: float,
    idle_min_context: int,
    idle_threshold_seconds: int,
) -> dict:
    decision = evaluate_auto_reload_once(
        force_file=force_file,
        dryrun_file=dryrun_file,
        state_file=state_file,
        cooldown_seconds=cooldown_seconds,
        tail_text=tail_text,
        context_tokens=context_tokens,
        active_threshold=active_threshold,
        idle_seconds=idle_seconds,
        idle_min_context=idle_min_context,
        idle_threshold_seconds=idle_threshold_seconds,
    )
    if decision["action"] == "dry-run":
        log_auto_reload(log_file, f"DRY-RUN would fire: {decision['reason']}", throttle=300)
    elif decision["action"] == "fire":
        log_auto_reload(log_file, f"firing: {decision['reason']}")
        mark_auto_reload(state_file, decision["reason"], context_tokens)
    return decision


async def auto_reload_monitor_loop(
    *,
    tick_func: Callable[[], dict],
    context_tokens_func: Callable[[], int],
    active_threshold_func: Callable[[], int],
    default_interval_seconds: int,
    startup_delay_seconds: int = 0,
    sleep_func: Callable[[int], object] = asyncio.sleep,
    print_func: Callable[..., None] = print,
    stop_func: Callable[[], bool] | None = None,
) -> list[dict]:
    decisions = []
    if startup_delay_seconds > 0:
        await sleep_func(startup_delay_seconds)
    while True:
        if stop_func and stop_func():
            return decisions
        try:
            decision = tick_func()
            reason = decision.get("reason") if isinstance(decision, dict) else str(decision or "")
            if reason:
                print_func(f"[auto-reload] {reason}", flush=True)
        except Exception as exc:
            decision = {"action": "error", "error": type(exc).__name__, "message": str(exc)}
            print_func(f"[auto-reload] error: {type(exc).__name__}: {exc}", flush=True)
        decisions.append(decision)
        context_tokens = context_tokens_func()
        active_threshold = active_threshold_func()
        interval = reload_monitor_interval(context_tokens, active_threshold, default_interval_seconds)
        await sleep_func(interval)


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


def set_reload_marker(marker_file: Path, enabled: bool, label: str) -> dict:
    marker_file.parent.mkdir(parents=True, exist_ok=True)
    if enabled:
        marker_file.write_text(
            f"{label} {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n",
            encoding="utf-8",
        )
    else:
        try:
            marker_file.unlink()
        except FileNotFoundError:
            pass
    return {"pending": marker_file.exists()}


def reload_marker_pending(marker_file: Path) -> bool:
    return marker_file.exists()


def consume_reload_marker(marker_file: Path) -> bool:
    if not marker_file.exists():
        return False
    try:
        marker_file.unlink()
    except OSError:
        return False
    return True


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
