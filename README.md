# cocoon

A web chat UI for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — turn the terminal into a chat room.

Cocoon is a starting point, not a finished product. The codebase is small (~800 lines) and meant to be forked and modified. Swap the theme, add features, connect it to Telegram or Discord, change whatever you want.

If you are syncing features from a private deployment, read
[`docs/extension-boundaries.md`](docs/extension-boundaries.md) first so private
memory, personal pages, games, and secrets stay out of the reusable core.

## Who is this for?

- You want to **chat with Claude from your phone** — but Claude Code only runs in a terminal
- You're building an **AI companion** and need a cozy UI, not a developer console
- You want the full power of Claude Code (tools, memory, hooks, MCP) but with a **chat interface your non-technical partner / friend can use**
- You run Claude Code on a server / desktop and want to **talk to it from anywhere**

## What it does

Cocoon runs Claude Code inside tmux and renders the conversation as a chat interface in your browser. The default frontend (served at `/`) is a structured chat page — bubbles, quote-replies, emoji reactions, stickers, image upload, wallpaper-derived theming, offline cache — reading a structured message stream. A simpler legacy UI that parses raw terminal output directly lives at `/chat`. You talk to Claude Code exactly as it runs in the terminal, but through a clean, mobile-friendly web page. All Claude Code features (tools, memory, hooks, MCP servers, slash commands) work as-is — cocoon is a rendering layer, not a replacement. Switch providers with [CC Switch](https://github.com/farion1231/cc-switch); cocoon doesn't care which backend you use.

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
./start.sh --doctor
./start.sh
```

On first run the script generates a random access token (saved to `.env`) and creates `frontend/config.js` from the template. Open `http://localhost:8080/` in your browser and enter the token on the login page.

Edit `frontend/config.js` to set the display names, avatars, and site title — every personal parameter of the chat page lives there. See [`docs/frontend.md`](docs/frontend.md) for the full frontend/API reference.

> **⚠️ Security warning — read before deploying**
>
> Cocoon gives web access to a real Claude Code terminal. Anyone with your token can read/write files, run shell commands, and use every tool Claude Code has access to. This is not a sandboxed chatbot — it's full terminal control through a browser.
>
> By default cocoon binds to `127.0.0.1`, so it is only reachable from the same machine. To expose it to another device, set `COCOON_HOST=0.0.0.0` and change the default token first. The start script refuses non-local binds with the default token.
>
> ```bash
> # Always set a strong random token
> COCOON_TOKEN=$(openssl rand -hex 24) COCOON_HOST=0.0.0.0 ./start.sh
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
wsl --install -d Ubuntu-24.04
# restart Windows if WSL asks you to, then open Ubuntu
sudo apt update
sudo apt install -y tmux python3 python3-pip python3-venv nodejs npm
npm install -g @anthropic-ai/claude-code
```

> **Why tmux?** Claude Code is a terminal application — there's no API to talk to it programmatically. Cocoon uses tmux as a virtual terminal: it sends your messages via `tmux send-keys` and reads Claude's responses via `tmux capture-pane`. This is the same terminal you'd interact with manually, just automated. Cocoon itself doesn't call any API — Claude Code handles all the model communication. You just need a working Claude Code installation (which requires an Anthropic account or API access through Bedrock/Vertex).

### Configuration

All settings are environment variables:

| Variable | Default | Description |
|---|---|---|
| `COCOON_HOST` | `127.0.0.1` | Server bind address. Use `0.0.0.0` only when you intentionally expose cocoon to another device |
| `COCOON_PORT` | `8080` | Server port |
| `COCOON_TOKEN` | `cocoon-default-token` | Auth token for the web UI |
| `COCOON_SESSION` | `cocoon-cc` | tmux session name |
| `COCOON_TMUX_HISTORY_LIMIT` | `20000` | tmux scrollback/history lines retained for capture |
| `COCOON_WORK_DIR` | current directory | Working directory for Claude Code |
| `COCOON_STATE_DIR` | `COCOON_WORK_DIR/.cocoon` | Directory for cocoon state files |
| `COCOON_START_COMMAND` | `claude` | Command sent inside tmux when cocoon starts or reloads Claude Code |
| `COCOON_LAUNCHER_PATTERN` | empty | Optional `pgrep -f` pattern used to avoid interrupting a custom launcher while it is still starting |
| `COCOON_CONVERSATIONS_DIR` | `COCOON_WORK_DIR/.cocoon/conversations` | Optional read-only JSONL history directory for `/history` |
| `COCOON_EXTENSIONS_FILE` | `COCOON_WORK_DIR/.cocoon/extensions.json` | Optional read-only extension/link registry for `/extensions` |
| `COCOON_AUTO_RELOAD_PAUSE_FILE` | `COCOON_STATE_DIR/.forge_auto_reload_paused` | Pause marker used by optional reload integrations |
| `COCOON_AUTO_RELOAD_LOG_FILE` | `COCOON_STATE_DIR/.forge_auto_reload.log` | Log file used by optional reload integrations |
| `COCOON_AUTO_RELOAD_ENABLED` | `0` | Enables optional automatic reload integrations. The bundled core does not start a monitor by default |
| `COCOON_AUTO_RELOAD_STATE_FILE` | `COCOON_STATE_DIR/.auto_reload.json` | Cooldown state file for optional automatic reload integrations |
| `COCOON_AUTO_RELOAD_DRYRUN_FILE` | `COCOON_STATE_DIR/.auto_reload_dryrun` | Dry-run marker for optional automatic reload integrations |
| `COCOON_AUTO_RELOAD_FORCE_FILE` | `COCOON_STATE_DIR/.auto_reload_force` | Manual force marker for optional automatic reload integrations |
| `COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD` | `125000` | Context token threshold for optional automatic reload decisions |
| `COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD_1M` | `600000` | Context token threshold when a 1M-window model is detected |
| `COCOON_AUTO_RELOAD_IDLE_MIN_CONTEXT` | `200000` | Minimum context tokens before idle-cache reload decisions are considered |
| `COCOON_AUTO_RELOAD_IDLE_SECONDS` | `3600` | Idle seconds before idle-cache reload decisions are considered |
| `COCOON_AUTO_RELOAD_COOLDOWN_SECONDS` | `600` | Cooldown seconds between optional automatic reload attempts |
| `COCOON_AUTO_RELOAD_CHECK_INTERVAL_SECONDS` | `30` | Default polling interval for optional automatic reload integrations |
| `COCOON_RELOAD_COMMAND` | empty | Optional command sent to tmux by `POST /reload-session` |
| `COCOON_RELOAD_LOCK_DIR` | `COCOON_STATE_DIR/.reload.lock` | Lock directory for manual reload integrations |
| `COCOON_RELOAD_LOCK_STALE_SECONDS` | `300` | Seconds before a reload lock can be reclaimed |
| `COCOON_UPLOAD_DIR` | system temp / `cocoon-uploads` | Directory for uploaded files |
| `COCOON_MAX_UPLOAD_MB` | `0` | Optional upload size cap in MB. `0` keeps uploads unlimited |
| `COCOON_TTS_PROVIDER` | `none` | Optional TTS provider. Set to `minimax` to enable `/tts/say` |
| `COCOON_TTS_DIR` | system temp / `cocoon-tts` | Directory for generated TTS audio |
| `COCOON_TTS_MAX_TEXT_CHARS` | `800` | Maximum text length accepted by `/tts/say` |
| `COCOON_TTS_MAX_AUDIO_FILES` | `40` | Number of generated `.mp3` files retained in `COCOON_TTS_DIR` |
| `COCOON_AUTO_DISMISS_PROMPTS` | `1` | Auto-dismiss common Claude Code terminal prompts. Set to `0` to require manual confirmation |
| `MINIMAX_API_KEY` | empty | MiniMax API key, required when `COCOON_TTS_PROVIDER=minimax` |
| `MINIMAX_VOICE_ID` | empty | MiniMax voice ID, required when TTS is enabled |
| `MINIMAX_TTS_MODEL` | `speech-2.8-hd` | MiniMax TTS model |
| `MINIMAX_TTS_URL` | `https://api.minimaxi.chat/v1/t2a_v2` | MiniMax TTS endpoint |
| `COCOON_SERVE_FRONTEND` | `1` | Serve the bundled chat frontend at `/`. Set to `0` when a reverse proxy serves the pages |
| `COCOON_FRONTEND_DIR` | `cocoon/frontend` | Directory the bundled frontend is served from |
| `COCOON_CLEAN_START_COMMAND` | `COCOON_START_COMMAND` | Launch command used by `POST /clean-session` for a context-free session |
| `COCOON_REACTIONS_FILE` | `COCOON_STATE_DIR/reactions.json` | Storage for the chat page's emoji reactions |
| `COCOON_FILES_URL_PREFIX` | `/bridge/files/` | URL prefix used in `GET /recent-images` responses; set to `/files/` for self-serving deployments |

Example:

```bash
COCOON_TOKEN=my-secret COCOON_PORT=3000 COCOON_WORK_DIR=/path/to/project ./start.sh

# Expose to another device on your private network:
COCOON_TOKEN=$(openssl rand -hex 24) COCOON_HOST=0.0.0.0 ./start.sh
```

### Optional TTS

Cocoon can expose a small TTS API and render generated audio as voice bubbles. TTS is off by default.

```bash
COCOON_TTS_PROVIDER=minimax \
MINIMAX_API_KEY=your-api-key \
MINIMAX_VOICE_ID=your-voice-id \
./start.sh
```

Endpoints:

- `POST /tts/say` with `{"text":"hello"}` generates an mp3 and returns its URL
- `GET /tts/latest` returns the latest generated audio metadata
- `GET /tts/audio/<id>.mp3` serves generated audio with the same token protection as uploads
- `GET /raw-output` mirrors `/output` for clients that need the unprocessed terminal capture

The chat UI renders voice markers like `[[cocoon_voice:<id>]]` and direct `/tts/audio/<id>.mp3` links as playable voice bubbles.

## Features

- **Chat UI** — messages parsed from terminal output into clean bubbles
- **Markdown rendering** — bold, italic, code blocks, tables, lists, links
- **Tool call folding** — file reads, bash commands, etc. collapsed by default
- **File upload** — attach images and files to messages
- **File listing** — optional `/files` endpoint for clients to inspect uploaded files
- **Optional TTS** - generate mp3 audio and render voice bubbles when configured
- **Light / dark theme** — follows system preference, toggleable
- **Custom avatars & background** — stored in localStorage
- **Auto-start** — opens Claude Code automatically on first visit
- **Mobile-friendly** — designed for phones, works on desktop too
- **Typing indicator** — shows when Claude is thinking
- **Auto-dismiss prompts** — handles resume, rating, and settings prompts automatically
- **Terminal view** — see raw Claude Code output via sidebar toggle
- **Emoji reactions & quote replies** — long-press a bubble to react or quote (structured frontend)
- **Stickers** — upload once, send from the emoji panel (structured frontend)
- **Wallpaper theming** — UI colors derived from your wallpaper (structured frontend)
- **Mood effects** — Pelle d'Umore emotional-skin runtime (CC BY 4.0, by Cu & Lunedì)
- **Any API backend** — cocoon wraps the terminal, not the API. Use [CC Switch](https://github.com/farion1231/cc-switch) to switch Claude Code between Anthropic, AWS Bedrock, Google Vertex, OpenRouter, or any supported provider — your chat UI stays the same

## Architecture

```
cocoon/
├── start.sh          # one-click launcher
├── server.py         # FastAPI routes
├── config.py         # env-based configuration
├── requirements.txt
├── frontend/         # structured chat frontend (chat.html, login, config, mood runtime)
└── bridge/
    ├── tmux.py       # tmux interaction (capture, send, status)
    ├── live_archive.py  # structured message stream (/chat_pure) and archive sync
    ├── reactions.py  # emoji reactions and recent-image listing
    ├── frontend_routes.py  # serves the bundled frontend
    ├── auth.py       # token checks and /login exchange
    ├── session.py    # tmux session startup and configurable Claude launcher
    ├── history.py    # read-only JSONL conversation history helpers
    ├── extensions.py # optional extension/link registry helpers
    ├── prompts.py    # auto-dismiss Claude Code prompts
    ├── uploads.py    # file upload handling
    ├── tts.py        # optional TTS generation and audio serving
    └── ui.py         # chat UI (HTML/CSS/JS)
```

## Limitations

**Cocoon depends on Claude Code's terminal output format.** The chat UI parses raw terminal text into messages. If a Claude Code update changes how output is rendered (new progress bars, different formatting, UI chrome changes), the parser may need updating. The terminal view (`/terminal`) always shows the unprocessed output as a fallback.

**Web only.** Cocoon renders to a browser. It doesn't include renderers for messaging platforms (Telegram, Discord, etc.) — but the architecture makes this straightforward to add: the `/output` API returns parsed JSON that any client can consume.

**Single conversation, no reroll.** The default setup is one tmux session, one conversation at a time, no regenerate button. Cocoon wraps the full Claude Code CLI, so all native features (slash commands, MCP servers, `Esc Esc` to reroll, `CLAUDE.md` for personality) work as-is. If you need parallel sessions or a reroll button in the UI, the architecture doesn't prevent it.

**Don't run as root.** Claude login state is per user, so root and your normal Linux user have separate Claude sessions. Cocoon refuses root by default. Create a normal user and run cocoon there. If you intentionally want root anyway, set `COCOON_ALLOW_ROOT=1`.

## Troubleshooting

Run the doctor first:

```bash
./start.sh --doctor
```

It checks the common setup mistakes before the server starts: missing `tmux`, missing `claude`, root user, Windows `claude.exe` inside WSL, unsafe default token exposure, and port availability.

**Windows: tmux is not available natively**

tmux doesn't run on Windows directly. You need WSL (Windows Subsystem for Linux):

1. Open PowerShell **as Administrator** and run `wsl --install`
2. Restart your computer
3. Open the Ubuntu terminal that appears in Start Menu
4. Inside Ubuntu/WSL, install everything: `sudo apt update && sudo apt install -y tmux python3 python3-pip python3-venv nodejs npm`
5. Install Claude Code inside Ubuntu/WSL: `npm install -g @anthropic-ai/claude-code`
6. Run `claude` inside Ubuntu/WSL once and finish login/authentication there
7. Clone and run cocoon inside Ubuntu/WSL: `./start.sh --doctor && ./start.sh`

Everything (cocoon, claude, tmux) must run inside the same WSL environment and the same Linux user. Don't mix Windows and WSL paths. Don't use the Windows `claude.exe` from WSL; install the Linux Claude Code CLI inside Ubuntu/WSL.

If `wsl --install -d Ubuntu-24.04` installs the app but does not finish the first Linux setup, run `ubuntu2404.exe install --root` once from PowerShell, then open Ubuntu again. If `apt install` is very slow in WSL, switch Ubuntu to a faster mirror before installing packages. For example:

```bash
sudo cp /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.bak
sudo sed -i 's#http://archive.ubuntu.com/ubuntu#https://mirrors.tuna.tsinghua.edu.cn/ubuntu#g; s#http://security.ubuntu.com/ubuntu#https://mirrors.tuna.tsinghua.edu.cn/ubuntu#g' /etc/apt/sources.list.d/ubuntu.sources
sudo apt update
```

When launching cocoon from Windows, keep the WSL process alive. A short command like `wsl ... "nohup ... &"` may exit and stop the server with it. Prefer opening an Ubuntu terminal and running `./start.sh` there, or use a long-lived WSL process manager.

**Claude login disappeared after restart**

You probably restarted cocoon as a different Linux user, often `root`. Claude Code stores login/session state under the current user's home directory, so root cannot see the normal user's Claude login.

Expected shape:

```text
same normal Linux user owns: uvicorn server:app, tmux cocoon session, claude
root owns: none of the cocoon uvicorn/tmux/claude processes
```

Fix it by stopping the wrong root-owned server/session, then start cocoon again as your normal Linux user. In WSL, prefer opening the Ubuntu terminal as that user and running `./start.sh` there. If you must launch from PowerShell, specify the user explicitly, for example:

```powershell
wsl -u cocoon -- bash -lc 'cd /path/to/cocoon && ./start.sh'
```

**PowerShell quoting or non-ASCII text looks wrong in WSL**

PowerShell can expand `$()` and variables before WSL sees the Linux command. For complex Linux commands, run them inside Ubuntu instead of wrapping them in PowerShell. Also avoid using PowerShell-to-WSL command strings to validate non-ASCII chat text; test real chat input through the browser.

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

Start cocoon with a non-default host and a strong token:

```bash
COCOON_TOKEN=$(openssl rand -hex 24) COCOON_HOST=0.0.0.0 ./start.sh
```

Then find your computer's local IP and open it on your phone:

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

MIT. The bundled mood/fx runtime under `frontend/src/` is
[Pelle d'Umore](https://cunedi.uk) by Cu & Lunedì, CC BY 4.0 — see
`frontend/src/LICENSE`.
