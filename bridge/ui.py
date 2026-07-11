from __future__ import annotations

# 遗留内嵌聊天页已退役：聊天 UI 只有 /app/ 的 React 构建一个版本。

TERMINAL_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>cocoon terminal</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#1a1a2e; color:#e0e0e0; font-family:'Courier New',monospace; font-size:13px; height:100vh; display:flex; flex-direction:column; }
.toolbar { background:#16132a; padding:8px 16px; display:flex; align-items:center; gap:12px; border-bottom:1px solid #333; flex-shrink:0; }
.toolbar a { color:#c8b496; text-decoration:none; font-size:0.85rem; }
.toolbar a:hover { text-decoration:underline; }
.toolbar .title { color:#888; font-size:0.8rem; }
#terminal { flex:1; overflow-y:auto; padding:12px; white-space:pre-wrap; word-break:break-all; line-height:1.5; }
.input-row { display:flex; gap:8px; padding:8px 12px; background:#16132a; border-top:1px solid #333; flex-shrink:0; }
.input-row input { flex:1; background:#222; border:1px solid #444; color:#e0e0e0; padding:8px 12px; border-radius:6px; font-family:inherit; font-size:13px; }
.input-row button { background:#c8b496; color:#1a1a2e; border:none; padding:8px 16px; border-radius:6px; cursor:pointer; font-weight:600; }
</style>
</head>
<body>
<div class="toolbar">
  <a href="/app/">&larr; chat</a>
  <span class="title">raw terminal</span>
</div>
<pre id="terminal">loading...</pre>
<div class="input-row">
  <input id="raw-input" placeholder="send raw keys..." onkeydown="if(event.key==='Enter')sendRaw()">
  <button onclick="sendRaw()">send</button>
</div>
<script>
const TOKEN = localStorage.getItem('cocoon_token') || '';  // 绝不从 URL 读 token：查询串会进日志/历史
const H = {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'};
function isClaudeUiNoise(line) {
  const t = (line || '').trim();
  if (!t) return false;
  if (/^[│┃]/.test(t)) return true;
  if (/^[│┃|]+$/.test(t)) return true;
  // Claude Code 2.1.x chrome: input-box frame/rulers, prompt, shortcut hints,
  // version/auto-update banner (wraps across lines, so bare */_ runs too)
  if (/^[╭╮╰╯─━╌╍═_*]+$/.test(t)) return true;
  if (/^[╭╰❯]/.test(t)) return true;
  if (/\? for shortcuts|← for agents/.test(t)) return true;
  if (/globalVersion|latestVersion|Auto-update (?:failed|available)|Run \*{0,2}\/doctor/.test(t)) return true;
  if (/Claude Code v|^\s*▐▛|^\s*▝▜|^Resume this session/.test(line || '')) return true;
  if (/^(?:Haiku|Sonnet|Opus)\s+\d|Claude\s+(?:Pro|Max|Code)|Organization|\/[A-Za-z0-9_.\/-]+\/cocoon\b/i.test(t)) return true;
  if (/^[│┃|]?\s*(?:Welcome back|Tips for getting started|Run \/init to create a CLAUDE\.md file|What's new|\/release-notes for more|Added sandbox\.credentials|Added org-configured model restrictions|Added mouse click support)\b/i.test(t)) return true;
  if (/^\s*[│┃|].*(?:Welcome back|Tips for getting started|Run \/init|What's new|\/release-notes|Added sandbox\.credentials|Added org-configured|Added mouse click support)/i.test(line || '')) return true;
  if (/^\*?\s*(?:✶|✽|✻|✢|✳|✸|✹|✺|✱|✲|✦|✧)\s*\*?.*(?:Thinking|Thought|Brewed|Brewing|Cooked|Saut[eé]ed|思考|Elapsed|Took|Used|\d+(?:\.\d+)?\s*(?:s|sec|secs|second|seconds|秒|ms|m)\b)/i.test(t)) return true;
  if (/^\*?\s*(?:✶|✽|✻|✢|✳|✸|✹|✺|✱|✲|✦|✧)\s*\*?(?:Thinking|Thought|Brewed|Brewing|Cooked|Saut[eé]ed|思考|Elapsed|Took|Used)?\s*(?:for\s*)?\d+(?:\.\d+)?\s*(?:s|sec|secs|second|seconds|秒|ms|m)\*?$/i.test(t)) return true;
  if (/^\*?\s*(?:Thinking|Thought|Brewed|Brewing|Cooked|Saut[eé]ed|思考|Elapsed|Took|Used)\s*(?:for\s*)?\d+(?:\.\d+)?\s*(?:s|sec|secs|second|seconds|秒|ms|m)\*?$/i.test(t)) return true;
  return false;
}
function filterRawOutput(text) {
  // 连续空行折叠成一个：tmux 抓屏的 pane 大半是空的，别让读者滚一屏空白
  return (text || '').split('\n').filter(line => !isClaudeUiNoise(line))
    .join('\n').replace(/\n{3,}/g, '\n\n').trim();
}
async function refresh() {
  try {
    const r = await fetch('/output?lines=1500', { headers: H });
    const el = document.getElementById('terminal');
    const wasNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    el.textContent = r.ok ? filterRawOutput(await r.text()) || '(empty)' : '(no output)';
    if (wasNearBottom) el.scrollTop = el.scrollHeight;
  } catch(e) {}
}
async function sendRaw() {
  const inp = document.getElementById('raw-input');
  const text = inp.value.trim();
  if (!text) return;
  await fetch('/send', {method:'POST', headers:H, body:JSON.stringify({text})});
  inp.value = '';
  setTimeout(refresh, 500);
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


def terminal_html() -> str:
    return TERMINAL_HTML
