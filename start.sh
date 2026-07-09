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
if [[ -z "${COCOON_TOKEN:-}" ]]; then
  COCOON_TOKEN="$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  echo "COCOON_TOKEN=${COCOON_TOKEN}" >> .env
  echo "generated a new access token and saved it to .env"
fi

# First run: create the instance frontend config from the template.
if [[ -f frontend/config.example.js && ! -f frontend/config.js ]]; then
  cp frontend/config.example.js frontend/config.js
  echo "created frontend/config.js — edit it to set names and avatars"
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

if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "installing dependencies..."
  pip3 install -r requirements.txt 2>/dev/null || pip3 install --break-system-packages -r requirements.txt
fi

if ! command -v claude &>/dev/null; then
  echo "error: claude (Claude Code CLI) must be installed and on PATH"
  echo "see: https://docs.anthropic.com/en/docs/claude-code"
  exit 1
fi

export COCOON_HOST COCOON_PORT COCOON_TOKEN COCOON_SESSION COCOON_WORK_DIR

echo "cocoon starting on http://${COCOON_HOST}:${COCOON_PORT}/"
echo "  login with the token below on the login page"
echo "  host:     ${COCOON_HOST}"
echo "  session:  ${COCOON_SESSION}"
echo "  workdir:  ${COCOON_WORK_DIR}"
echo "  token:    ${COCOON_TOKEN}"
echo "  legacy terminal-parsing UI: http://${COCOON_HOST}:${COCOON_PORT}/chat"
echo ""

exec python3 -m uvicorn server:app --host "${COCOON_HOST}" --port "${COCOON_PORT}"
