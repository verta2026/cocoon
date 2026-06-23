# cocoon

A web chat UI for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — no API key needed.

Cocoon polls the terminal through tmux, parses the raw output, and renders it as a chat interface in your browser. You talk to Claude Code exactly as it runs in the terminal, but through a clean, mobile-friendly web page.

## Why not use the API?

Claude Code is a full agent — not just a model. By wrapping the CLI instead of the API, cocoon inherits everything Claude Code already does for free:

- **Tools** — file editing, bash, web search, all built in
- **MCP servers** — connect to any external service without writing integration code
- **Memory** — persistent across sessions, managed by Claude Code itself
- **Hooks** — trigger shell commands on events (message sent, tool called, etc.)
- **Permissions** — fine-grained control over what Claude can do
- **Context management** — automatic summarization, `/compact`, session continuity
- **Slash commands** — `/init`, `/review`, `/cost`, everything works as-is
- **Multi-model** — switch providers with [CC Switch](https://github.com/farion1231/cc-switch); cocoon doesn't care which backend you use

If you build on the raw API, you'd reimplement all of the above from scratch. Cocoon gives you a chat UI on top of the full agent — no information loss, no feature gaps.

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

- **Python 3.9+**
- **tmux** — cocoon runs Claude Code inside a tmux session. This is how it captures output without needing an API key
- **[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)** — installed and authenticated (`claude` command works in terminal)

#### Installing tmux

```bash
# macOS
brew install tmux

# Ubuntu / Debian
sudo apt install tmux

# Fedora
sudo dnf install tmux

# Arch
sudo pacman -S tmux

# Windows (use WSL)
wsl --install          # if you don't have WSL yet
sudo apt install tmux  # inside WSL
```

> **Why tmux?** Claude Code is a terminal application — there's no API to talk to it programmatically. Cocoon uses tmux as a virtual terminal: it sends your messages via `tmux send-keys` and reads Claude's responses via `tmux capture-pane`. This is the same terminal you'd interact with manually, just automated. No API key, no token limits, no extra cost.

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
- **Terminal view** — see raw Claude Code output via sidebar toggle
- **Any API backend** — cocoon wraps the terminal, not the API. Use [CC Switch](https://github.com/farion1231/cc-switch) to switch Claude Code between Anthropic, AWS Bedrock, Google Vertex, OpenRouter, or any supported provider — your chat UI stays the same

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

## Limitations

**Cocoon depends on Claude Code's terminal output format.** The chat UI parses raw terminal text into messages. If a Claude Code update changes how output is rendered (new progress bars, different formatting, UI chrome changes), the parser may need updating. The terminal view (`/terminal`) always shows the unprocessed output as a fallback.

**Web only.** Cocoon renders to a browser. It doesn't include renderers for messaging platforms (Telegram, Discord, etc.) — but the architecture makes this straightforward to add: the `/output` API returns parsed JSON that any client can consume.

**Single conversation, no reroll.** One tmux session, one conversation at a time. There's no branching, no parallel threads, no "regenerate response" button. What was said was said. This is deliberate — cocoon was built for companionship, not productivity. If you want a different answer, say so in the chat like you would with a person.

## Troubleshooting

**Windows: tmux is not available natively**

tmux doesn't run on Windows directly. You need WSL (Windows Subsystem for Linux):

1. Open PowerShell **as Administrator** and run `wsl --install`
2. Restart your computer
3. Open the Ubuntu terminal that appears in Start Menu
4. Inside WSL, install everything: `sudo apt install tmux python3 python3-pip`
5. Install Claude Code inside WSL: `npm install -g @anthropic-ai/claude-code`
6. Run cocoon from WSL — not from PowerShell or cmd

Everything (cocoon, claude, tmux) must run inside the same WSL environment. Don't mix Windows and WSL paths.

**Claude Code shows "trust this folder" prompt and hangs**

Cocoon auto-dismisses this prompt. If it still hangs, the prompt may have appeared before cocoon's status check. Visit `/status` in your browser (e.g. `http://localhost:8080/status?token=your-token`) to trigger the dismiss, or restart with `POST /start`.

**Port already in use**

Another process is using port 8080. Either kill it or choose a different port:

```bash
COCOON_PORT=3000 ./start.sh
```

**"No module named fastapi"**

The start script auto-installs dependencies, but if it fails:

```bash
pip3 install -r requirements.txt
```

On Debian/Ubuntu with externally-managed Python, you may need `--break-system-packages` or use a venv:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**Phone can't reach localhost**

`localhost` only works on the machine running cocoon. To access from your phone on the same WiFi:

1. Find your computer's local IP: `hostname -I` (Linux) or `ifconfig | grep inet` (macOS)
2. Open `http://<your-ip>:8080/chat` on your phone
3. Make sure your firewall allows port 8080

## Accessing from your phone (or anywhere)

### Same WiFi (simplest)

Find your computer's local IP and open it on your phone:

```bash
# Linux
hostname -I

# macOS
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Then on your phone: `http://192.168.x.x:8080/chat`

### From anywhere — Tailscale (recommended)

[Tailscale](https://tailscale.com/) creates a private network between your devices. Free for personal use, zero configuration.

1. Install Tailscale on your computer and phone ([download](https://tailscale.com/download))
2. Sign in on both devices
3. Your computer gets a fixed IP like `100.x.x.x` — find it with `tailscale ip`
4. On your phone: `http://100.x.x.x:8080/chat`

Works from anywhere — home, café, commute. No ports to open, no domain to buy, encrypted by default.

### Domain + VPS (~8 RMB/year)

Buy a cheap domain, proxy through Cloudflare (free HTTPS + CDN), point to your VPS. Full step-by-step guide:

**[docs/domain-guide.md](docs/domain-guide.md)** — Spaceship + Cloudflare + Caddy/nginx, total cost ~8 RMB/year.

### SSH tunnel (quick & secure)

If cocoon runs on a remote server and you just want access from your laptop:

```bash
ssh -L 8080:localhost:8080 user@your-server
# then open http://localhost:8080/chat locally
```

## License

MIT
