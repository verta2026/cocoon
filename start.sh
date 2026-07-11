#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Persisted local settings (created on first run).
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

: "${COCOON_PORT:=8080}"
: "${COCOON_HOST:=127.0.0.1}"
: "${COCOON_SESSION:=cocoon-cc}"
: "${COCOON_WORK_DIR:=$(pwd)}"

# First run: generate a random token and persist it, so the default
# token never survives past the very first start.
COCOON_TOKEN_IS_FRESH=0
if [[ -z "${COCOON_TOKEN:-}" ]]; then
  COCOON_TOKEN="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  echo "COCOON_TOKEN=${COCOON_TOKEN}" >> .env
  echo "generated a new access token and saved it to .env"
  COCOON_TOKEN_IS_FRESH=1
fi

# The token lives in .env — keep it out of other local users' reach.
if [[ -f .env ]]; then
  chmod 600 .env
fi

# First run: create the instance frontend configs from the templates.
# config.js is public (theme/site); config.private.json holds identity
# (names, avatars, channel ids) and is only served after auth.
if [[ -f frontend/config.example.js && ! -f frontend/config.js ]]; then
  cp frontend/config.example.js frontend/config.js
  echo "created frontend/config.js — edit it to set the site basics"
fi
if [[ -f frontend/config.private.example.json && ! -f frontend/config.private.json ]]; then
  cp frontend/config.private.example.json frontend/config.private.json
  echo "created frontend/config.private.json — edit it to set names and avatars"
fi

if [[ "${1:-}" == "--doctor" || "${1:-}" == "doctor" ]]; then
  if ! command -v python3 &>/dev/null; then
    echo "error: python3 is required to run cocoon doctor"
    exit 1
  fi
  exec python3 -m bridge.doctor
fi

if [[ "${COCOON_TOKEN}" == "cocoon-default-token" && "${COCOON_HOST}" != "127.0.0.1" && "${COCOON_HOST}" != "localhost" ]]; then
  echo "error: refusing to bind ${COCOON_HOST} with the default token"
  echo "set a strong COCOON_TOKEN before exposing cocoon outside this machine"
  exit 1
fi

if [[ "$(id -u)" == "0" && "${COCOON_ALLOW_ROOT:-}" != "1" ]]; then
  echo "error: refusing to run cocoon as root"
  echo "Claude login state is per user; run as a normal Linux user instead"
  echo "set COCOON_ALLOW_ROOT=1 only if you intentionally want a separate root Claude session"
  exit 1
fi

if ! command -v tmux &>/dev/null; then
  echo "error: tmux is required. install it first (apt install tmux / brew install tmux)"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "error: python3 is required"
  exit 1
fi

python3 -m bridge.doctor --strict

# Check every runtime dependency, not just fastapi — a machine that has
# fastapi but lacks uvicorn/multipart would otherwise skip the install and
# die at startup.
if ! python3 -c "import fastapi, uvicorn, multipart" 2>/dev/null; then
  echo "installing dependencies..."
  pip3 install -r requirements.txt 2>/dev/null || pip3 install --break-system-packages -r requirements.txt
fi

if ! python3 -c "import fastapi, uvicorn, multipart" 2>/dev/null; then
  echo "error: python dependencies missing after install (fastapi/uvicorn/python-multipart)"
  echo "install them manually: pip3 install -r requirements.txt"
  exit 1
fi

if ! command -v claude &>/dev/null; then
  echo "error: claude (Claude Code CLI) must be installed and on PATH"
  echo "see: https://docs.anthropic.com/en/docs/claude-code"
  exit 1
fi

export COCOON_HOST COCOON_PORT COCOON_TOKEN COCOON_SESSION COCOON_WORK_DIR

echo "cocoon starting on http://${COCOON_HOST}:${COCOON_PORT}/"
echo "  host:     ${COCOON_HOST}"
echo "  session:  ${COCOON_SESSION}"
echo "  workdir:  ${COCOON_WORK_DIR}"
# 只在首次生成、且真人对着终端时显示一次完整 token——
# 之后每次启动都回显的话，token 会留在 systemd/journal 和 CI 日志里
if [[ "${COCOON_TOKEN_IS_FRESH}" == "1" && -t 1 ]]; then
  echo "  token:    ${COCOON_TOKEN}   (shown once; stored in .env)"
else
  echo "  token:    <in .env — grep COCOON_TOKEN .env>"
fi
echo "  raw terminal: http://${COCOON_HOST}:${COCOON_PORT}/terminal"
echo "  first install? have your agent read docs/for-your-agent.md (中文: docs/for-your-agent.zh-CN.md)"

# React 前端是可选构建；但一份过期的 dist 比没有更糟——页面能开、功能却停在
# 上次 build 的那天（源码更新对它毫无作用），这类"旧盖新"故障极难自查
if [[ -f webapp/dist/index.html ]]; then
  if [[ -n "$(find webapp/src webapp/index.html webapp/login.html -newer webapp/dist/index.html -print -quit 2>/dev/null)" ]]; then
    echo ""
    echo "  ⚠ webapp/dist is OLDER than webapp/src — the React app at /app/ is stale."
    echo "    rebuild it:  cd webapp && npm install && npm run build"
  fi
else
  echo "  React app not built (optional): cd webapp && npm install && npm run build"
fi
echo ""

exec python3 -m uvicorn server:app --host "${COCOON_HOST}" --port "${COCOON_PORT}"
