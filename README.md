# cocoon

A web chat UI for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — turn the terminal into a chat room.

## Who is this for?

- You want to **chat with Claude from your phone** — but Claude Code only runs in a terminal
- You're building an **AI companion** and need a cozy UI, not a developer console
- You want the full power of Claude Code (tools, memory, hooks, MCP) but with a **chat interface your non-technical partner / friend can use**
- You run Claude Code on a server / desktop and want to **talk to it from anywhere**

## What it does

Cocoon polls the terminal through tmux, parses the raw output, and renders it as a chat interface in your browser. You talk to Claude Code exactly as it runs in the terminal, but through a clean, mobile-friendly web page. All Claude Code features (tools, memory, hooks, MCP servers, slash commands) work as-is — cocoon is a rendering layer, not a replacement. Switch providers with [CC Switch](https://github.com/farion1231/cc-switch); cocoon doesn't care which backend you use.

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

> **⚠️ Security warning — read before deploying**
>
> Cocoon gives web access to a real Claude Code terminal. Anyone with your token can read/write files, run shell commands, and use every tool Claude Code has access to. This is not a sandboxed chatbot — it's full terminal control through a browser.
>
> **Change the default token immediately.** The default is `cocoon-default-token` and the server binds `0.0.0.0` (all interfaces). If you're on a VPS with a public IP and forget to change the token, anyone can find and control your terminal.
>
> ```bash
> # Always set a strong random token
> COCOON_TOKEN=$(openssl rand -hex 24) ./start.sh
> ```
>
> **For remote access, use a private network** — Tailscale, SSH tunnel, or VPN. Exposing cocoon directly to the public internet (even with a strong token) is not recommended. If you must, put it behind HTTPS + Cloudflare with a long random token, and understand the risk: a leaked token = full terminal access.

### Requirements

- **Python 3.9+**
- **tmux** — cocoon runs Claude Code inside a tmux session. This is how it captures output without needing a separate API integration
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

> **Why tmux?** Claude Code is a terminal application — there's no API to talk to it programmatically. Cocoon uses tmux as a virtual terminal: it sends your messages via `tmux send-keys` and reads Claude's responses via `tmux capture-pane`. This is the same terminal you'd interact with manually, just automated. Cocoon itself doesn't call any API — Claude Code handles all the model communication. You just need a working Claude Code installation (which requires an Anthropic account or API access through Bedrock/Vertex).

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

**Single conversation, no reroll.** The default setup is one tmux session, one conversation at a time, no regenerate button. Cocoon wraps the full Claude Code CLI, so all native features (slash commands, MCP servers, `Esc Esc` to reroll, `CLAUDE.md` for personality) work as-is. If you need parallel sessions or a reroll button in the UI, the architecture doesn't prevent it.

**Don't run as root.** Claude Code disables `--dangerously-skip-permissions` when run as root, which means every tool call will prompt for confirmation. Create a normal user and run cocoon from there.

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

`localhost` only works on the machine running cocoon. See [Accessing from your phone](#accessing-from-your-phone-or-anywhere) below.

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

### Domain + VPS

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
