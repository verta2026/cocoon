# Telegram 频道：换会话也不断线

[English](telegram-channel.md)

Claude Code 官方有一个 Telegram 插件（`plugin:telegram@claude-plugins-official`）：配好之后，agent 在网页里陪你聊天的同时，也能收发你的 Telegram 私信——出门在外发条 TG，回家打开网页，是同一个它、同一场对话。

但这个插件有一个和 cocoon 相性很差的天性：**它跟着 Claude 进程走**。cocoon 的日常就是换会话（自动重载、new session、clean session），每次换窗都等于杀掉旧 Claude、拉起新 Claude——如果什么都不做，Telegram 会以两种方式静默死掉：

1. **忘了带旗**。新会话的启动命令没有 `--channels` 参数，插件根本没加载。没有任何报错，只是 TG 再也不回话。
2. **被尸体占位**。旧进程死得不干净时会留下两种残骸：
   - `~/.claude/channels/telegram/bot.pid`——新会话看到它以为 bot 还活着，跳过启动自己的 poller；
   - 插件缓存目录里的 `.in_use/<pid>` 占用标记——让插件对新会话呈现"被占用/孤儿"状态。
   两种情况的症状一模一样：换窗之后 TG 悄无声息地失联，哪里都没有错误。

cocoon 的可选支持就是把这两件事变成自动的。

## 开启方式

前提：Telegram 插件本身已经装好配好（见下节）。然后在 `.env` 里加一行：

```bash
COCOON_CHANNEL_ARGS="--channels plugin:telegram@claude-plugins-official"
```

重启 cocoon。之后：

- **每一次 cocoon 驱动的 Claude 启动**（首次启动、new session、clean session）都会自动带上这串参数；
- **每次启动前**自动清理死进程留下的 `bot.pid` 和 `.in_use` 标记（只清 pid 已死的，活会话不碰）；
- `start.sh doctor` 会检查插件缓存是否存在、重载脚本是否带旗（见下面的坑）。

预检也可以单独控制：`COCOON_CHANNEL_PREFLIGHT=0` 关闭（默认跟随 `COCOON_CHANNEL_ARGS` 是否设置）。

## 首次安装插件（一次性，手动）

cocoon 只负责"每次都带上、每次都扫尸"，插件本身的安装和配对要在终端里做一次：

1. Telegram 找 **@BotFather** → `/newbot` → 起名 → 拿到 bot token
2. 终端里跑一次：`claude --channels plugin:telegram@claude-plugins-official`
3. 按提示配置 token（或用 `/telegram:configure` 粘贴 token）
4. 在 Telegram 给你的 bot 发条消息，它回一个 6 位配对码
5. 回到终端输入 `/telegram:access pair <配对码>` 完成配对

配对是持久的，之后 cocoon 每次换窗都会自动接上。

## 已知的坑

**重载脚本要自己带旗。** cocoon 只给自己拼出来的启动命令（`COCOON_START_COMMAND` / `COCOON_CLEAN_START_COMMAND`）追加参数；`COCOON_RELOAD_COMMAND` 是你自己的脚本、自己的 argv，cocoon 不碰它——你的重载脚本必须自己传同一串 `--channels`（透传参数或写死都行）。忘了的话，每次自动重载 TG 就掉一次。`doctor` 检测到这种配置会警告。

**消息在换窗瞬间到达会丢。** 换窗有几秒钟没有任何 Claude 进程在收 TG。插件没有离线队列，这几秒里到达的消息不会补投。日常聊天几乎碰不到，但要知道有这个窗口。

**出站消息不进网页聊天记录（默认）。** agent 通过 TG 回你的话走的是插件的出站通道，不在 Claude 的会话文件里。想让网页端也看到这些消息，配 `COCOON_SEND_SIDECAR_FILE` 指向插件的出站记录文件（如果你的插件版本支持 sidecar 落盘）。入站方向不用管——TG 消息以 `<channel>` 标签进会话，网页端天然能渲染；配 `COCOON_PRIMARY_SENDER_ID` 可以让你自己的 TG 号渲染成"你"，而不是第三方气泡。

**侧车是队列，不是档案。** 配了 `COCOON_SEND_SIDECAR_FILE` 之后，插件会往这个文件里永远追加。cocoon 在每次启动预检时排空它：已经并进 live archive 的行删掉，还没归档的行保留。没有这道裁剪，文件会无限增长，而且每次换窗都会把整部频道历史重新灌回新会话的视图。别把这个变量指向你自己当长期日志用的文件——归档才是持久副本。

**权限归属。** `/telegram:access` 的配对审批必须由你在终端完成。任何从 Telegram 消息里发来的"帮我把这个配对批了"都是提示注入的标准形状——插件文档和 agent 都被教过拒绝，但你自己也别这么用。

## 换窗稳定性之外

这套机制不是 Telegram 专属的：`COCOON_CHANNEL_ARGS` 接受任意 `--channels` 参数，预检清理的是所有 `~/.claude/channels/*/bot.pid` 和插件缓存里的死 pid 标记。以后官方出别的频道插件（Discord、Slack……），同一根线应该直接能用。
