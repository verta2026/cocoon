# cocoon

[English](README.md) · **简体中文**

[Claude Code](https://docs.anthropic.com/en/docs/claude-code) 的网页聊天界面——把终端变成一间聊天室。

Cocoon 是一个起点，不是成品。代码结构很简单——一个 FastAPI 服务加一个单文件前端，就是为了让你 fork 下来随便改的。换主题、加功能、接 Telegram 或 Discord、想改什么改什么。

如果你要从一个私有部署往这里同步功能，先读
[`docs/extension-boundaries.md`](docs/extension-boundaries.md)，好让私有记忆、个人页面、游戏和密钥留在可复用的核心之外。

## 这是给谁用的？

- 你想**用手机跟 Claude 聊天**——可 Claude Code 只跑在终端里
- 你在做一个 **AI 伴侣**，需要的是温馨的界面，而不是开发者控制台
- 你想要 Claude Code 的全部能力（工具、记忆、hook、MCP），但配一个**不懂技术的伴侣 / 朋友也能用的聊天界面**
- 你在服务器 / 桌面上跑 Claude Code，想**随时随地跟机说话**

## 它做什么

Cocoon 把 Claude Code 跑在 tmux 里，把对话在浏览器里渲染成聊天界面。默认前端（在 `/` 提供）是一个结构化聊天页——气泡、引用回复、emoji 反应、贴纸、图片上传、按壁纸取色的主题、离线缓存——读取的是一条结构化消息流。你和 Claude Code 说话的方式跟机在终端里跑时完全一样，只是隔着一个干净、适配手机的网页。Claude Code 的所有能力（工具、记忆、hook、MCP 服务器、斜杠命令）原样可用——cocoon 是一层渲染，不是替代品。用 [CC Switch](https://github.com/farion1231/cc-switch) 切换后端；cocoon 不在乎你用哪个。

## 工作原理

```
浏览器 ←→ FastAPI 服务 ←→ tmux 会话 ←→ Claude Code CLI
```

1. 服务在 tmux 会话里启动 Claude Code
2. 你的消息通过 `tmux send-keys` 发进终端
3. 服务通过 `tmux capture-pane` 抓取终端输出
4. JavaScript 把终端输出解析成聊天气泡（用户、助手、工具调用）
5. 每 2 秒轮询一次，保持界面同步

## 快速上手

```bash
git clone https://github.com/verta2026/cocoon.git
cd cocoon
chmod +x start.sh
./start.sh --doctor
./start.sh
```

首次运行时，脚本会生成一个随机访问令牌（存进 `.env`），并从模板创建 `frontend/config.js` 和 `frontend/config.private.json`。在浏览器里打开 `http://localhost:8080/`，在登录页输入令牌。

编辑 `frontend/config.private.json` 设置显示名、头像和频道名映射——身份信息放这里，只在登录后经 `/app-config` 下发。`frontend/config.js` 只放公开的基础项（站点标题、API 前缀、存储命名空间）：它未认证即可拉取（登录页要用），任何能识别身份的内容都不要写进去。完整的前端 / API 参考见 [`docs/frontend.md`](docs/frontend.md)。

> **⚠️ 安全警告——部署前必读**
>
> Cocoon 把一个真实的 Claude Code 终端开放到了网页上。任何拿到你令牌的人都能读写文件、执行 shell 命令、使用 Claude Code 能碰到的每一个工具。这不是一个沙箱里的聊天机器人——这是通过浏览器对终端的完全控制。
>
> 默认情况下 cocoon 绑定到 `127.0.0.1`，所以只有本机能访问。要暴露给另一台设备，设 `COCOON_HOST=0.0.0.0`，并**先改掉默认令牌**。启动脚本会拒绝「默认令牌 + 非本地绑定」的组合。
>
> ```bash
> # 永远设一个强随机令牌
> COCOON_TOKEN=$(openssl rand -hex 24) COCOON_HOST=0.0.0.0 ./start.sh
> ```
>
> **远程访问请走私有网络**——Tailscale、SSH 隧道或 VPN。不建议把 cocoon 直接暴露到公网（哪怕有强令牌）。如果非要这么做，请放在 HTTPS + Cloudflare 后面并配一个长随机令牌，同时明白风险：令牌一旦泄露 = 完全的终端访问权。

### 环境要求

- **Python 3.10+**
- **Node.js 18+ / npm**——聊天页是 React 构建产物；首次运行 `start.sh` 会自动 build
- **tmux**——cocoon 把 Claude Code 跑在 tmux 会话里。这正是它无需单独 API 集成就能抓取输出的方式
- **[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)**——已安装并登录（终端里 `claude` 命令可用）

#### 安装 tmux

```bash
# macOS
brew install tmux

# Ubuntu / Debian
sudo apt install tmux

# Fedora
sudo dnf install tmux

# Arch
sudo pacman -S tmux

# Windows（用 WSL）
wsl --install -d Ubuntu-24.04
# 如果 WSL 要求重启 Windows 就重启，然后打开 Ubuntu
sudo apt update
sudo apt install -y tmux python3 python3-pip python3-venv nodejs npm
npm install -g @anthropic-ai/claude-code
```

> **为什么用 tmux？** Claude Code 是一个终端应用——没有可编程调用的 API。Cocoon 把 tmux 当作虚拟终端用：通过 `tmux send-keys` 发消息，通过 `tmux capture-pane` 读 Claude 的回复。这跟你手动交互的是同一个终端，只是自动化了。Cocoon 本身不调用任何 API——所有与模型的通信都由 Claude Code 处理。你只需要一个能正常工作的 Claude Code 安装（这需要一个 Anthropic 账号，或通过 Bedrock/Vertex 的 API 访问）。

### 配置

所有设置都是环境变量：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `COCOON_HOST` | `127.0.0.1` | 服务绑定地址。只有在你有意把 cocoon 暴露给另一台设备时才用 `0.0.0.0` |
| `COCOON_PORT` | `8080` | 服务端口 |
| `COCOON_TOKEN` | `cocoon-default-token` | 网页界面的鉴权令牌 |
| `COCOON_SESSION` | `cocoon-cc` | tmux 会话名 |
| `COCOON_TMUX_HISTORY_LIMIT` | `20000` | 为抓取保留的 tmux 回滚 / 历史行数 |
| `COCOON_WORK_DIR` | 当前目录 | Claude Code 的工作目录 |
| `COCOON_STATE_DIR` | `COCOON_WORK_DIR/.cocoon` | cocoon 状态文件目录 |
| `COCOON_START_COMMAND` | `claude` | cocoon 启动或重载 Claude Code 时发进 tmux 的命令 |
| `COCOON_LAUNCHER_PATTERN` | 空 | 可选的 `pgrep -f` 模式，用于避免在自定义启动器还没起来时打断它 |
| `COCOON_CONVERSATIONS_DIR` | `COCOON_WORK_DIR/.cocoon/conversations` | 可选的只读 JSONL 历史目录，供 `/history` 使用 |
| `COCOON_EXTENSIONS_FILE` | `COCOON_WORK_DIR/.cocoon/extensions.json` | 可选的只读扩展 / 链接注册表，供 `/extensions` 使用 |
| `COCOON_AUTO_RELOAD_PAUSE_FILE` | `COCOON_STATE_DIR/.forge_auto_reload_paused` | 可选重载集成使用的暂停标记 |
| `COCOON_AUTO_RELOAD_LOG_FILE` | `COCOON_STATE_DIR/.forge_auto_reload.log` | 可选重载集成使用的日志文件 |
| `COCOON_AUTO_RELOAD_ENABLED` | `0` | 启动内置的自动重载监控器。需要同时配置 `COCOON_RELOAD_COMMAND`：当真实上下文占用（从会话 jsonl 读取）越过阈值且 Claude 空闲时，自动发送重载命令 |
| `COCOON_AUTO_RELOAD_STATE_FILE` | `COCOON_STATE_DIR/.auto_reload.json` | 可选自动重载集成的冷却状态文件 |
| `COCOON_AUTO_RELOAD_DRYRUN_FILE` | `COCOON_STATE_DIR/.auto_reload_dryrun` | 可选自动重载集成的 dry-run 标记 |
| `COCOON_AUTO_RELOAD_FORCE_FILE` | `COCOON_STATE_DIR/.auto_reload_force` | 可选自动重载集成的手动强制标记 |
| `COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD` | `125000` | 可选自动重载决策的上下文 token 阈值 |
| `COCOON_AUTO_RELOAD_CONTEXT_THRESHOLD_1M` | `600000` | 检测到 1M 窗口模型时的上下文 token 阈值 |
| `COCOON_AUTO_RELOAD_IDLE_MIN_CONTEXT` | `200000` | 考虑「空闲缓存重载」决策前所需的最小上下文 token 数 |
| `COCOON_AUTO_RELOAD_IDLE_SECONDS` | `3600` | 考虑「空闲缓存重载」决策前的空闲秒数 |
| `COCOON_AUTO_RELOAD_COOLDOWN_SECONDS` | `600` | 可选自动重载尝试之间的冷却秒数 |
| `COCOON_AUTO_RELOAD_CHECK_INTERVAL_SECONDS` | `30` | 自动重载监控器的默认轮询间隔（接近阈值时降到 10 秒） |
| `COCOON_AUTO_RELOAD_STARTUP_DELAY_SECONDS` | `120` | 服务启动后监控器首次检查前的延迟 |
| `COCOON_CLAUDE_SETTINGS_FILE` | `~/.claude/settings.json` | Claude Code 设置文件，只用于检测 `[1m]` 上下文窗口模型 |
| `COCOON_RELOAD_COMMAND` | 空 | `POST /reload-session` 和自动重载监控器发给 tmux 的命令（例如你的 forge 启动器） |
| `COCOON_RELOAD_LOCK_DIR` | `COCOON_STATE_DIR/.reload.lock` | 手动重载集成的锁目录 |
| `COCOON_RELOAD_LOCK_STALE_SECONDS` | `300` | 重载锁可被回收前的秒数 |
| `COCOON_UPLOAD_DIR` | 系统临时目录 / `cocoon-uploads` | 上传文件的目录 |
| `COCOON_MAX_UPLOAD_MB` | `200` | 上传大小上限（MB）。`0` 表示不限 |
| `COCOON_TTS_PROVIDER` | `none` | 可选的 TTS 提供方。设为 `minimax` 以启用 `/tts/say` |
| `COCOON_TTS_DIR` | 系统临时目录 / `cocoon-tts` | 生成的 TTS 音频目录 |
| `COCOON_TTS_MAX_TEXT_CHARS` | `800` | `/tts/say` 接受的最大文本长度 |
| `COCOON_TTS_MAX_AUDIO_FILES` | `40` | `COCOON_TTS_DIR` 里保留的 `.mp3` 文件数 |
| `COCOON_REACTION_NOTIFY` | `1` | 用户贴表情时给 agent 发一条 `[reaction]` 提醒。设为 `0` 则表情只留在前端 |
| `COCOON_REACTION_NOTIFY_TEMPLATE` | 内置 | 提醒的措辞；占位符 `{user}` `{emoji}` `{excerpt}`。默认版会请 agent 跟你商量把称呼换成你的名字 |
| `COCOON_AUTO_DISMISS_PROMPTS` | `1` | 自动关掉常见的 Claude Code 终端弹窗（resume 摘要、评分、目录信任）。设为 `0` 则需手动确认 |
| `COCOON_AUTO_ACCEPT_SETTINGS_WARNING` | `0` | 连 Claude Code 的 settings 警告也自动接受。默认关——那个警告通常意味着配置文件坏了，值得看一眼 |
| `COCOON_STICKER_MAX_MB` | `5` | 贴纸上传的独立大小上限（MB） |
| `COCOON_TRUST_FORWARDED_PROTO` | `0` | 前面有可信的 TLS 终止反代（nginx/Caddy/Cloudflare）时设为 `1`，登录 cookie 才会带 `Secure`。默认关：否则任意客户端伪造头就能翻转 cookie 属性 |
| `MINIMAX_API_KEY` | 空 | MiniMax API key，`COCOON_TTS_PROVIDER=minimax` 时必填 |
| `MINIMAX_VOICE_ID` | 空 | MiniMax voice ID，启用 TTS 时必填 |
| `MINIMAX_TTS_MODEL` | `speech-2.8-hd` | MiniMax TTS 模型 |
| `MINIMAX_TTS_URL` | `https://api.minimaxi.chat/v1/t2a_v2` | MiniMax TTS 端点 |
| `COCOON_SERVE_FRONTEND` | `1` | 在 `/` 提供自带的聊天前端。反向代理自己服务页面时设为 `0` |
| `COCOON_FRONTEND_DIR` | `cocoon/frontend` | 自带前端的服务目录 |
| `COCOON_CLEAN_START_COMMAND` | `COCOON_START_COMMAND` | `POST /clean-session` 用来起一个无上下文会话的启动命令 |
| `COCOON_REACTIONS_FILE` | `COCOON_STATE_DIR/reactions.json` | 聊天页 emoji 反应的存储 |
| `COCOON_FILES_URL_PREFIX` | `/bridge/files/` | `GET /recent-images` 响应里用的 URL 前缀；自服务部署设为 `/files/` |

示例：

```bash
COCOON_TOKEN=my-secret COCOON_PORT=3000 COCOON_WORK_DIR=/path/to/project ./start.sh

# 暴露给私有网络上的另一台设备：
COCOON_TOKEN=$(openssl rand -hex 24) COCOON_HOST=0.0.0.0 ./start.sh
```

### 可选的 TTS

Cocoon 能暴露一个小的 TTS API，并把生成的音频渲染成语音气泡。TTS 默认关闭。

```bash
COCOON_TTS_PROVIDER=minimax \
MINIMAX_API_KEY=your-api-key \
MINIMAX_VOICE_ID=your-voice-id \
./start.sh
```

端点：

- `POST /tts/say` 带 `{"text":"hello"}` 生成一个 mp3 并返回它的 URL
- `GET /tts/latest` 返回最近生成的音频元数据
- `GET /tts/audio/<id>.mp3` 提供生成的音频，与上传共用同一套令牌保护
- `GET /raw-output` 镜像 `/output`，供需要未处理终端抓取的客户端使用

聊天界面会把 `[[cocoon_voice:<id>]]` 这样的语音标记，以及直接的 `/tts/audio/<id>.mp3` 链接，渲染成可播放的语音气泡。

## 功能

- **聊天界面**——从终端输出解析成干净的气泡
- **Markdown 渲染**——粗体、斜体、代码块、表格、列表、链接
- **工具调用折叠**——文件读取、bash 命令等默认折叠
- **文件上传**——给消息附上图片和文件
- **文件列表**——可选的 `/files` 端点，供客户端查看已上传文件
- **可选 TTS**——配置后生成 mp3 音频并渲染语音气泡
- **明 / 暗主题**——跟随系统偏好，可手动切换
- **自定义头像和背景**——存在 localStorage
- **自动启动**——首次访问自动打开 Claude Code
- **适配手机**——为手机设计，桌面也能用
- **输入指示**——Claude 思考时会显示
- **自动关弹窗**——自动处理 resume 摘要、评分、目录信任弹窗（settings 警告默认不自动，见配置表）
- **终端视图**——通过侧栏开关查看原始 Claude Code 输出
- **Emoji 反应和引用回复**——长按气泡可反应或引用（结构化前端）
- **贴纸**——上传一次，从 emoji 面板发送（结构化前端）
- **壁纸主题**——界面颜色从你的壁纸取色（结构化前端）
- **任意 API 后端**——cocoon 包的是终端，不是 API。用 [CC Switch](https://github.com/farion1231/cc-switch) 在 Anthropic、AWS Bedrock、Google Vertex、OpenRouter 或任何受支持的提供方之间切换 Claude Code——你的聊天界面不变

## 贴纸（表情包）

> 有一整份写给 agent 本人读的前端说明书——消息标记、贴纸、弹窗、礼节：
> [docs/for-your-agent.zh-CN.md](docs/for-your-agent.zh-CN.md)。
> 在 `CLAUDE.md` 里指一句，你的 agent 读一遍就住熟了。

贴纸是双向功能：你从面板发，**AI 也能发回来**——但 AI 从头到尾看不见图片，机读的是文字。

**聊天页里**（结构化前端）：输入栏的贴纸按钮打开面板，`＋` 上传图片（自动缩到
256px PNG），单点发送。**长按贴纸进入编辑**——改名字、改描述、或删除。描述比看起来
重要：AI 认识一张贴纸靠的就是这段文字，不是图。

**协议层**：一条贴纸消息就是一段文本——`[sticker:<文件名>|<名字>|<描述>]`
（名字和描述来自 `meta.json`，agent 直接读到贴纸的含义；不带竖线的裸
`[sticker:<文件名>]` 同样有效）。前端把这个标记渲染成
`/stickers/<文件名>` 的图片；其余所有环节（历史、桥、Claude 的会话记录）看到的都是纯文本。

**AI 看到的东西**：贴纸目录（`COCOON_STICKER_DIR`，默认 `<tmp>/cocoon-stickers`）里的
`meta.json`，把文件名映射到名字和描述：

```json
{ "happy_cat.png": { "name": "开心猫", "desc": "得意满足，干完活的时候用" } }
```

想让你的 AI 会用贴纸，在 `CLAUDE.md` 里给机指个路：

```markdown
贴纸：想在聊天里发贴纸，回复里写 [sticker:<文件名>]。
发之前先读 <贴纸目录>/meta.json 挑合适的——desc 字段写着每张的含义。
不要编造文件名。
```

描述要写给一个看不见图的读者——情绪加场合（"熬完大夜修完 bug 的虚脱胜利感"）
比描述画面（"一只躺着的猫"）有用得多。在面板里改名字或描述会直接更新 `meta.json`，
AI 下次翻的时候就是新的。

## 架构

```
cocoon/
├── start.sh          # 一键启动
├── server.py         # FastAPI 路由
├── config.py         # 基于环境变量的配置
├── requirements.txt
├── frontend/         # 静态资源（登录、编辑器、config、头像）
├── webapp/           # 聊天前端（React/Vite，服务于 /app/）
└── bridge/
    ├── tmux.py       # tmux 交互（抓取、发送、状态）
    ├── live_archive.py  # 结构化消息流（/chat_pure）和归档同步
    ├── reactions.py  # emoji 反应和最近图片列表
    ├── frontend_routes.py  # 提供自带前端
    ├── auth.py       # 令牌校验和 /login 交换
    ├── session.py    # tmux 会话启动和可配置的 Claude 启动器
    ├── history.py    # 只读 JSONL 对话历史辅助
    ├── extensions.py # 可选的扩展 / 链接注册表辅助
    ├── prompts.py    # 自动关闭 Claude Code 弹窗
    ├── uploads.py    # 文件上传处理
    ├── tts.py        # 可选的 TTS 生成和音频服务
    └── ui.py         # 聊天界面（HTML/CSS/JS）
```

### React 版前端

`webapp/` 就是聊天前端（Vite 构建）。首次运行 `start.sh` 会自动构建；手动重建：

```bash
cd webapp
npm install
npm run build     # 产出 webapp/dist（纯静态文件）
npm test          # 渲染器 + 解析器单元测试
```

服务器把构建产物挂在 `/app/`，`/` 直接跳转过去。Node.js 只在构建打包的
机器上需要——运行时不需要。

## 局限

**Cocoon 依赖 Claude Code 的终端输出格式。** 聊天界面把原始终端文本解析成消息。如果某次 Claude Code 更新改了输出的渲染方式（新的进度条、不同的格式、界面装饰变化），解析器可能需要更新。终端视图（`/terminal`）始终把未处理的输出作为兜底显示。

**仅网页。** Cocoon 渲染到浏览器。它不包含面向消息平台（Telegram、Discord 等）的渲染器——但架构让这很容易加：`/output` API 返回解析好的 JSON，任何客户端都能消费。

**单对话，无重roll。** 默认配置是一个 tmux 会话、一次一个对话、没有重新生成按钮。Cocoon 包的是完整的 Claude Code CLI，所以所有原生功能（斜杠命令、MCP 服务器、`Esc Esc` 重roll、`CLAUDE.md` 定制人格）原样可用。如果你需要并行会话或界面里的重roll 按钮，架构并不妨碍你加。

**别用 root 跑。** Claude 的登录状态是按用户隔离的，root 和你平时的 Linux 用户有各自独立的 Claude 会话。Cocoon 默认拒绝 root。建一个普通用户，在那里跑 cocoon。如果你确实有意要用 root，设 `COCOON_ALLOW_ROOT=1`。

## 排障

先跑 doctor：

```bash
./start.sh --doctor
```

它会在服务启动前检查常见的配置错误：缺 `tmux`、缺 `claude`、root 用户、WSL 里用了 Windows 的 `claude.exe`、默认令牌的不安全暴露、端口可用性。

**Windows：tmux 无法原生运行**

tmux 不能直接在 Windows 上跑，你需要 WSL（Windows Subsystem for Linux）：

1. 以**管理员身份**打开 PowerShell，运行 `wsl --install`
2. 重启电脑
3. 打开开始菜单里出现的 Ubuntu 终端
4. 在 Ubuntu/WSL 里装齐所有东西：`sudo apt update && sudo apt install -y tmux python3 python3-pip python3-venv nodejs npm`
5. 在 Ubuntu/WSL 里装 Claude Code：`npm install -g @anthropic-ai/claude-code`
6. 在 Ubuntu/WSL 里跑一次 `claude`，在那里完成登录 / 鉴权
7. 在 Ubuntu/WSL 里 clone 并运行 cocoon：`./start.sh --doctor && ./start.sh`

所有东西（cocoon、claude、tmux）必须在同一个 WSL 环境、同一个 Linux 用户下运行。别混用 Windows 和 WSL 的路径。别在 WSL 里用 Windows 的 `claude.exe`；在 Ubuntu/WSL 里装 Linux 版 Claude Code CLI。

如果 `wsl --install -d Ubuntu-24.04` 装好了应用但没完成首次 Linux 初始化，从 PowerShell 跑一次 `ubuntu2404.exe install --root`，然后再打开 Ubuntu。如果 WSL 里 `apt install` 很慢，装包前把 Ubuntu 换成更快的镜像源。例如：

```bash
sudo cp /etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list.d/ubuntu.sources.bak
sudo sed -i 's#http://archive.ubuntu.com/ubuntu#https://mirrors.tuna.tsinghua.edu.cn/ubuntu#g; s#http://security.ubuntu.com/ubuntu#https://mirrors.tuna.tsinghua.edu.cn/ubuntu#g' /etc/apt/sources.list.d/ubuntu.sources
sudo apt update
```

从 Windows 启动 cocoon 时，要让 WSL 进程保持存活。像 `wsl ... "nohup ... &"` 这样的短命令可能退出并把服务一起停掉。更好的做法是打开一个 Ubuntu 终端在那里跑 `./start.sh`，或者用一个长期存活的 WSL 进程管理器。

**重启后 Claude 登录没了**

你多半是以另一个 Linux 用户（通常是 `root`）重启了 cocoon。Claude Code 把登录 / 会话状态存在当前用户的 home 目录下，所以 root 看不到普通用户的 Claude 登录。

期望的样子：

```text
同一个普通 Linux 用户拥有：uvicorn server:app、tmux cocoon 会话、claude
root 拥有：cocoon 的 uvicorn/tmux/claude 进程一个都没有
```

修法：停掉那个错误的 root 拥有的服务 / 会话，然后以你平时的 Linux 用户重新启动 cocoon。在 WSL 里，最好以该用户打开 Ubuntu 终端在那里跑 `./start.sh`。如果非要从 PowerShell 启动，显式指定用户，例如：

```powershell
wsl -u cocoon -- bash -lc 'cd /path/to/cocoon && ./start.sh'
```

**PowerShell 的引号或非 ASCII 文本在 WSL 里显示不对**

PowerShell 可能在 WSL 看到 Linux 命令之前就展开了 `$()` 和变量。复杂的 Linux 命令请在 Ubuntu 里跑，别用 PowerShell 包起来。另外别用 PowerShell-到-WSL 的命令字符串去验证非 ASCII 的聊天文本；真实的聊天输入请通过浏览器测试。

**Claude Code 弹出「trust this folder」并卡住**

Cocoon 会自动关掉这个弹窗。如果还是卡住，可能是弹窗在 cocoon 状态检查之前就出现了。请求一次 `/status` 触发关闭——token 放在 `Authorization` 头里，**永远不要拼进 URL**（URL 里的 token 会漏进日志和浏览器历史）：

```
curl -H "Authorization: Bearer your-token" http://localhost:8080/status
```

或用 `POST /start` 重启。

**端口已被占用**

另一个进程在用 8080 端口。要么杀掉它，要么换个端口：

```bash
COCOON_PORT=3000 ./start.sh
```

**「No module named fastapi」**

启动脚本会自动装依赖，如果失败：

```bash
pip3 install -r requirements.txt
```

在 Debian/Ubuntu 上遇到 externally-managed Python 时，你可能需要 `--break-system-packages`，或者用 venv：

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
```

**手机连不上 localhost**

`localhost` 只在跑 cocoon 的那台机器上有效。见下面的[从手机（或任何地方）访问](#从手机或任何地方访问)。

## 从手机（或任何地方）访问

### 同一 WiFi（最简单）

用一个非默认 host 和强令牌启动 cocoon：

```bash
COCOON_TOKEN=$(openssl rand -hex 24) COCOON_HOST=0.0.0.0 ./start.sh
```

然后找到你电脑的局域网 IP，在手机上打开：

```bash
# Linux
hostname -I

# macOS
ifconfig | grep "inet " | grep -v 127.0.0.1
```

然后在手机上：`http://192.168.x.x:8080/`

### 从任何地方——Tailscale（推荐）

[Tailscale](https://tailscale.com/) 在你的设备之间建一个私有网络。个人使用免费，零配置。

1. 在电脑和手机上装 Tailscale（[下载](https://tailscale.com/download)）
2. 两台设备都登录
3. 你的电脑会拿到一个固定 IP，像 `100.x.x.x`——用 `tailscale ip` 查
4. 在手机上：`http://100.x.x.x:8080/`

到哪都能用——家里、咖啡馆、通勤路上。不用开端口，不用买域名，默认加密。

### 域名 + VPS

买个便宜域名，通过 Cloudflare 代理（免费 HTTPS + CDN），指向你的 VPS。完整分步指南：

**[docs/domain-guide.md](docs/domain-guide.md)**——Spaceship + Cloudflare + Caddy/nginx，总成本约 8 元 / 年。

### SSH 隧道（快且安全）

如果 cocoon 跑在远程服务器上，你只想从笔记本访问：

```bash
ssh -L 8080:localhost:8080 user@your-server
# 然后本地打开 http://localhost:8080/
```

## 致谢

forge 引擎——让 Claude Code 会话越过上下文上限无缝续命的换窗机制——
源自 **离落** 的原版 forge。cocoon 里的实现此后各自演化，
但这个想法和第一版能跑的设计属于离落。

## 许可证

MIT。
