#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

: "${COCOON_PORT:=8080}"
: "${COCOON_TOKEN:=cocoon-default-token}"
: "${COCOON_SESSION:=cocoon-cc}"
: "${COCOON_WORK_DIR:=$(pwd)}"

if ! command -v tmux &>/dev/null; then
  echo "error: tmux is required. install it first (apt install tmux / brew install tmux)"
  exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "error: python3 is required"
  exit 1
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "installing dependencies..."
  pip3 install -r requirements.txt 2>/dev/null || pip3 install --break-system-packages -r requirements.txt
fi

if ! command -v claude &>/dev/null; then
  echo "error: claude (Claude Code CLI) must be installed and on PATH"
  echo "see: https://docs.anthropic.com/en/docs/claude-code"
  exit 1
fi

export COCOON_PORT COCOON_TOKEN COCOON_SESSION COCOON_WORK_DIR

echo "cocoon starting on http://localhost:${COCOON_PORT}/chat"
echo "  session:  ${COCOON_SESSION}"
echo "  workdir:  ${COCOON_WORK_DIR}"
echo "  token:    ${COCOON_TOKEN}"
echo ""

exec python3 -m uvicorn server:app --host 0.0.0.0 --port "${COCOON_PORT}"
