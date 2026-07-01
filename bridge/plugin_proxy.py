"""Generic plugin proxy helpers."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping

from fastapi import HTTPException


def proxy_path(
    path: str,
    method: str,
    *,
    get_paths: Mapping[str, str],
    post_paths: Mapping[str, str],
    service_name: str = "Plugin",
    dynamic_get_path: Callable[[str], str] | None = None,
) -> str:
    normalized = (path or "").strip("/")
    if method == "GET" and dynamic_get_path is not None:
        target = dynamic_get_path(normalized)
        if target:
            return target
    table = get_paths if method == "GET" else post_paths
    target = table.get(normalized)
    if not target:
        raise HTTPException(404, f"{service_name} API path is not exposed")
    return target


def json_proxy_request(
    api_base: str,
    target: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    service_name: str = "Plugin",
    timeout: int = 10,
    opener: Callable = urllib.request.urlopen,
) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(f"{api_base}{target}", data=data, headers=headers, method=method)
    try:
        with opener(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
        except Exception:
            parsed = {"error": detail or exc.reason}
        raise HTTPException(exc.code, parsed)
    except Exception as exc:
        raise HTTPException(502, f"{service_name} service unavailable: {type(exc).__name__}")
