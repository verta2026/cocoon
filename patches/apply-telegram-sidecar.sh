#!/usr/bin/env bash
# Apply the telegram sidecar patch to the official plugin's cached copy.
# Safe to re-run: refuses when the patch is already applied, keeps a .orig
# backup, and restores it on a failed apply. Plugin upgrades replace the
# cached file — just run this again afterwards.
set -euo pipefail

PLUGIN_VERSION="${TELEGRAM_PLUGIN_VERSION:-0.0.6}"
TARGET="${1:-$HOME/.claude/plugins/cache/claude-plugins-official/telegram/$PLUGIN_VERSION/server.ts}"
PATCH_FILE="$(cd "$(dirname "$0")" && pwd)/telegram-sidecar.patch"

if [ ! -f "$TARGET" ]; then
    echo "plugin file not found: $TARGET" >&2
    echo "install the plugin first, or pass the server.ts path as the first argument" >&2
    exit 1
fi

if grep -q "TELEGRAM_SIDECAR_DIR" "$TARGET"; then
    echo "already patched: $TARGET"
    exit 0
fi

cp "$TARGET" "$TARGET.orig"
if patch --quiet "$TARGET" < "$PATCH_FILE"; then
    echo "patched: $TARGET (backup at $TARGET.orig)"
    echo "set TELEGRAM_SIDECAR_DIR in the environment Claude Code starts from,"
    echo "then restart the session (the plugin process reloads on session swap)."
else
    mv "$TARGET.orig" "$TARGET"
    echo "patch did not apply cleanly — plugin version mismatch? ($PLUGIN_VERSION expected)" >&2
    echo "original restored: $TARGET" >&2
    exit 1
fi
