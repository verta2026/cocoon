# cocoon

A web chat UI for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — no API key needed.

Cocoon polls the terminal through tmux, parses the raw output, and renders it as a chat interface in your browser. You talk to Claude Code exactly as it runs in the terminal, but through a clean, mobile-friendly web page.

## Why not use the API?

Claude Code is a CLI tool. It manages its own context, tools, memory, and permission system. The API gives you a raw model — Claude Code gives you an agent. Cocoon lets you use that agent from anywhere with a browser.

## How it works

```
browser ←→ FastAPI server ←→ tmux session ←→ Claude Code CLI
```

1. The server starts Claude Code inside a tmux session
2. Your messages are sent to the terminal via `tmux send-keys`
3. The server captures terminal output via `tmux capture-pane`
4. JavaScript parses the terminal output into chat bubbles (user, assistant, tool calls)
5. Polling every 2 seconds keeps the UI in sync

## Quick start

```bash
git clone https://github.com/verta2026/cocoon.git
cd cocoon
chmod +x start.sh
./start.sh
```

Open `http://localhost:8080/chat` in your browser. Enter the token when prompted (default: `cocoon-default-token`).

### Requirements

- Python 3.9+
- tmux
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated

### Configuration

All settings are environment variables:

| Variable | Default | Description |
|---|---|---|
| `COCOON_PORT` | `8080` | Server port |
| `COCOON_TOKEN` | `cocoon-default-token` | Auth token for the web UI |
| `COCOON_SESSION` | `cocoon-cc` | tmux session name |
| `COCOON_WORK_DIR` | current directory | Working directory for Claude Code |

Example:

```bash
COCOON_TOKEN=my-secret COCOON_PORT=3000 COCOON_WORK_DIR=/path/to/project ./start.sh
```

## Features

- **Chat UI** — messages parsed from terminal output into clean bubbles
- **Markdown rendering** — bold, italic, code blocks, tables, lists, links
- **Tool call folding** — file reads, bash commands, etc. collapsed by default
- **File upload** — attach images and files to messages
- **Light / dark theme** — follows system preference, toggleable
- **Custom avatars & background** — stored in localStorage
- **Auto-start** — opens Claude Code automatically on first visit
- **Mobile-friendly** — designed for phones, works on desktop too
- **Typing indicator** — shows when Claude is thinking
- **Auto-dismiss prompts** — handles resume, rating, and settings prompts automatically

## Architecture

```
cocoon/
├── start.sh          # one-click launcher
├── server.py         # FastAPI routes
├── config.py         # env-based configuration
├── requirements.txt
└── bridge/
    ├── tmux.py       # tmux interaction (capture, send, status)
    ├── prompts.py    # auto-dismiss Claude Code prompts
    ├── uploads.py    # file upload handling
    └── ui.py         # chat UI (HTML/CSS/JS)
```

## Accessing remotely

If running on a VPS, set a strong token and expose the port:

```bash
COCOON_TOKEN=$(openssl rand -hex 16) ./start.sh
```

Use SSH port forwarding for secure access:

```bash
ssh -L 8080:localhost:8080 user@your-server
```

Or put it behind a reverse proxy (nginx, caddy) with HTTPS.

## License

MIT
