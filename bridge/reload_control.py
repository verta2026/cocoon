"""Generic reload control state for session handoff integrations."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import shutil
import time
from pathlib import Path


def auto_reload_status(pause_file: Path) -> dict:
    return {"paused": pause_file.exists()}


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
