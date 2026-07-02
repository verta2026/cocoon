"""Generic OpenAI-compatible summary provider helpers."""

from __future__ import annotations

import json
import ssl
import urllib.request
from pathlib import Path
from typing import Any, Callable

from bridge.forge_io import read_json


DISABLED_PROVIDERS = {"", "none", "off", "disabled"}
REQUIRED_CONFIG_KEYS = ("api_key", "base_url", "model")


def load_deepseek_config(config_path: Path) -> dict[str, Any] | None:
    config = read_json(config_path)
    if isinstance(config.get("deepseek"), dict):
        config = config["deepseek"]
    if not all(config.get(key) for key in REQUIRED_CONFIG_KEYS):
        return None
    return config


def extract_summary_marker(text: str | None, marker: str) -> str:
    text = (text or "").strip()
    if marker and marker in text:
        return text.split(marker, 1)[1].strip()
    return text


def build_summary_messages(previous_summary: str, dropped_text: str, system_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Previous cumulative summary:\n"
                f"{previous_summary or '(none)'}\n\n"
                "Raw conversation that will be dropped:\n"
                f"{dropped_text or '(none)'}\n\n"
                "Return the new cumulative summary."
            ),
        },
    ]


def call_openai_compatible_summary(
    previous_summary: str,
    dropped_text: str,
    config: dict[str, Any],
    system_prompt: str,
    marker: str,
    *,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 90,
) -> tuple[str, str]:
    payload = {
        "model": config["model"],
        "messages": build_summary_messages(previous_summary, dropped_text, system_prompt),
        "stream": False,
        "temperature": 0.2,
        "max_tokens": 6000,
    }
    request = urllib.request.Request(
        config["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        context = ssl.create_default_context()
        with urlopen(request, timeout=timeout, context=context) as response:
            output = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return "", f"deepseek-error:{type(exc).__name__}"

    choices = output.get("choices") or []
    if not choices:
        return "", "deepseek-empty"
    message = choices[0].get("message") or {}
    text = (message.get("content") or message.get("reasoning_content") or "").strip()
    summary = extract_summary_marker(text, marker)
    if not summary:
        return "", "deepseek-empty"
    return summary, "updated"


def call_summary_provider(
    provider: str,
    previous_summary: str,
    dropped_text: str,
    *,
    config_path: Path,
    system_prompt: str,
    marker: str,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[str, str]:
    provider_name = (provider or "").strip().lower()
    if provider_name in DISABLED_PROVIDERS:
        return "", "provider-disabled"
    if provider_name != "deepseek":
        return "", f"unsupported-provider:{provider_name}"

    config = load_deepseek_config(config_path)
    if not config:
        return "", "missing-config"
    return call_openai_compatible_summary(
        previous_summary,
        dropped_text,
        config,
        system_prompt,
        marker,
        urlopen=urlopen,
    )
