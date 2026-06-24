from __future__ import annotations

CHAT_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta name="theme-color" content="#FBF5EC" id="meta-theme">
<meta name="mobile-web-app-capable" content="yes">
<script>
(function(){
  var s=localStorage.getItem('theme');
  var d=window.matchMedia('(prefers-color-scheme:dark)').matches;
  var dark=s==='dark'||(!s&&d);
  if(dark)document.documentElement.setAttribute('data-theme','dark');
  var m=document.querySelector('#meta-theme');
  if(m)m.setAttribute('content',dark?'#14111B':'#FBF5EC');
})();
</script>
<title>cocoon</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
:root {
  --bg: #F7F1E8;
  --panel: rgba(255,249,239,0.75);
  --card: rgba(255,253,252,0.72);
  --assistant-bg: rgba(255,248,236,0.92);
  --user-bg: rgba(255,248,236,0.92);
  --text: #342A22;
  --muted: #7C6A58;
  --accent: #8A6A4F;
  --accent-strong: #C4956A;
  --border: #e6d8c4;
  --user-border: #e6d8c4;
  --code-bg: #F1EADC;
  --shadow: 0 2px 10px rgba(70, 50, 30, 0.06);
}
[data-theme="dark"] {
  --bg: #0e0c14; --panel: rgba(22,19,30,0.72); --card: rgba(26,23,34,0.68);
  --assistant-bg: rgba(22,19,30,0.65); --user-bg: rgba(38,32,24,0.68);
  --text: #d4ccbc; --muted: #8a7e6a;
  --accent: #c8a060; --accent-strong: #dab878;
  --border: #2a2434; --user-border: #3a3028;
  --code-bg: #1a1820;
  --shadow: 0 2px 10px rgba(0,0,0,0.3);
}
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg); color: var(--text);
  height: 100dvh; display: flex; flex-direction: column;
  position: relative;
}
body::before {
  content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: var(--chat-bg-image, linear-gradient(var(--bg), var(--bg))) center center / cover no-repeat;
  z-index: 0; pointer-events: none;
}
.header, .chat-area, .input-area { position: relative; z-index: 1; }
.header {
  position: fixed; top: 0; left: 0; right: 0; height: 49px;
  padding: 0 14px; background: transparent;
  display: flex; align-items: center; gap: 12px; z-index: 10;
}
.hdr-icon {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; color: var(--muted); font-size: 1.1rem;
  -webkit-tap-highlight-color: transparent; border: none; background: none; padding: 0;
}
.hdr-icon:active { opacity: 0.6; }
.hdr-icon svg { width: 18px; height: 18px; }
.hdr-icon-circle {
  width: 34px; height: 34px; border-radius: 50%;
  background: rgba(255,248,236,0.7); box-shadow: 0 1px 4px rgba(60,40,20,0.08);
}
[data-theme="dark"] .hdr-icon-circle { background: rgba(40,34,50,0.7); }
.status { font-size:0.65rem; color:var(--muted); }
.status.alive::before { content:""; display:inline-block; width:5px; height:5px; border-radius:50%; background:#6B8F5B; margin-right:3px; }
.status.dead::before { content:""; display:inline-block; width:5px; height:5px; border-radius:50%; background:#C44; margin-right:3px; }

.sidebar-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 90;
  opacity: 0; pointer-events: none; transition: opacity 0.25s;
}
.sidebar-overlay.open { opacity: 1; pointer-events: auto; }
.sidebar {
  position: fixed; left: 0; top: 0; bottom: 0; width: 260px; z-index: 91;
  background: rgba(255,248,236,0.96); backdrop-filter: blur(16px);
  transform: translateX(-100%); transition: transform 0.28s ease;
  display: flex; flex-direction: column;
  box-shadow: 4px 0 20px rgba(60,40,20,0.1);
}
[data-theme="dark"] .sidebar { background: rgba(22,19,30,0.96); box-shadow: 4px 0 20px rgba(0,0,0,0.3); }
.sidebar.open { transform: translateX(0); }
.sidebar-header { height: 49px; display: flex; align-items: center; padding: 0 16px; border-bottom: 1px solid var(--border); gap: 10px; }
.sidebar-header h2 { font-size: 0.95rem; font-weight: 400; color: var(--text); margin: 0; }
.sidebar-header h2 span { color: var(--accent); }
.sidebar-nav { flex: 1; overflow-y: auto; padding: 8px 0; }
.sidebar-item {
  display: flex; align-items: center; gap: 10px; padding: 11px 18px;
  font-size: 0.85rem; color: var(--text); cursor: pointer;
  -webkit-tap-highlight-color: transparent; border: none; background: none;
  width: 100%; text-align: left; font-family: inherit;
}
.sidebar-item:active { background: rgba(200,180,150,0.15); }
.sidebar-item .si-icon { width: 20px; text-align: center; color: var(--muted); font-size: 0.9rem; }
.sidebar-sep { height: 1px; background: var(--border); margin: 6px 16px; }
.sidebar-section-title { padding: 8px 18px 4px; font-size: 0.65rem; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; }
.look-note { display: block; padding: 0 18px 8px; min-height: 18px; font-size: 0.68rem; color: var(--muted); }
.sidebar-footer { padding: 12px 18px; font-size: 0.7rem; color: var(--muted); border-top: 1px solid var(--border); }

.chat-area {
  flex: 1; overflow-y: auto;
  padding: calc(49px + 0.5rem) 0.85rem calc(74px + env(safe-area-inset-bottom, 0px));
  display: flex; flex-direction: column; gap: 0.65rem; scroll-behavior: smooth;
}
.msg-group { display: contents; }
.msg-wrap { display: flex; gap: 0.45rem; align-items: flex-start; max-width: min(90%, 800px); }
.msg-wrap-user { align-self: flex-end; flex-direction: row-reverse; }
.msg-wrap-assistant { align-self: flex-start; }
.avatar {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; margin-top: 2px; overflow: hidden;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.avatar-user { background: var(--user-border); color: var(--text); }
.avatar-assistant { background: var(--border); color: var(--text); }
.msg {
  max-width: 100%; padding: 0.62rem 0.88rem; border-radius: 18px;
  font-size: 0.88rem; line-height: 1.72; word-break: break-word;
  box-shadow: 0 2px 8px rgba(60,40,20,0.08); cursor: pointer;
}
.msg-ts { font-size: 0.65rem; color: var(--muted); margin-top: 0.25rem; display: none; opacity: 0.6; }
.msg-ts.show { display: flex; align-items: center; gap: 0.5rem; }
.copy-btn { cursor: pointer; opacity: 0.55; user-select: none; font-size: 0.62rem; padding: 0.1rem 0.3rem; border-radius: 3px; background: rgba(0,0,0,0.05); }
.copy-btn:active { opacity: 1; }
.msg-user { background: var(--user-bg); border: none; border-top-right-radius: 6px; }
.msg-assistant { background: var(--assistant-bg); border: none; border-top-left-radius: 6px; }
.msg table { border-collapse: collapse; margin: 0.45em 0; font-size: 0.84em; min-width: 100%; }
.msg th, .msg td { border: 1px solid var(--border); padding: 0.32em 0.58em; text-align: left; vertical-align: top; }
.msg th { background: var(--code-bg); font-weight: 600; }
.msg em { font-style: italic; }
.msg del { text-decoration: line-through; opacity: 0.7; }
.msg a:not(.copy-btn) { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
.msg .md-bq { border-left: 2px solid var(--accent); padding-left: 0.6em; margin: 0.2em 0; color: var(--muted); display: block; }
.msg .md-h { font-weight: 600; display: block; margin: 0.35em 0 0.15em; }
.msg .md-li { display: block; padding-left: 1.2em; text-indent: -0.8em; }
.msg .md-hr { border: none; border-top: 1px solid var(--border); margin: 0.5em 0; display: block; }
.md-table-scroll { overflow-x: auto; max-width: 100%; margin: 0.35em 0; }
.box-table {
  margin: 0.45em 0; padding: 0.55em 0.65em; background: var(--code-bg);
  border-radius: 6px; font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.78em; line-height: 1.45; overflow-x: auto; white-space: pre;
}
.msg-tool { align-self: flex-start; max-width: 95%; font-size: 0.75rem; color: var(--muted); }
.msg-tool summary {
  cursor: pointer; padding: 0.28rem 0.55rem; background: var(--code-bg);
  border-radius: 6px; border: 1px solid var(--border);
  max-width: 88vw; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.msg-tool pre {
  margin-top: 0.3rem; padding: 0.5rem; background: var(--code-bg);
  border-radius: 6px; font-family: "JetBrains Mono", "Fira Code", monospace;
  font-size: 0.72rem; line-height: 1.5; overflow-x: auto; white-space: pre-wrap;
  max-height: 200px; overflow-y: auto;
}
.msg-system { align-self: center; font-size: 0.7rem; color: var(--muted); font-style: italic; }
.msg-channel {
  align-self: flex-start; max-width: min(88%, 760px);
  font-size: 0.78rem; line-height: 1.55; color: var(--muted);
  background: var(--code-bg); border: 1px solid var(--border);
  border-radius: 7px; padding: 0.42rem 0.62rem;
}
.msg-channel strong { color: var(--accent); font-weight: 500; }
.typing-bubble { display: inline-flex; align-items: center; gap: 0.28rem; padding: 0.6rem 0.75rem; }
.typing-dot {
  width: 0.36rem; height: 0.36rem; border-radius: 50%; background: var(--muted);
  opacity: 0.42; animation: typingDot 1.25s infinite ease-in-out;
}
.typing-dot:nth-child(2) { animation-delay: 0.16s; }
.typing-dot:nth-child(3) { animation-delay: 0.32s; }
@keyframes typingDot {
  0%, 70%, 100% { transform: translateY(0); opacity: 0.35; }
  30% { transform: translateY(-0.26rem); opacity: 0.9; }
}
.voice-note {
  display: flex; align-items: center; gap: 0.55rem; min-width: 180px; max-width: 260px;
  padding: 0.12rem 0; color: var(--text);
}
.voice-play {
  width: 28px; height: 28px; border-radius: 50%; border: none; flex-shrink: 0;
  background: var(--accent-strong); color: #fff; cursor: pointer; font-size: 0.72rem;
}
.voice-track {
  position: relative; flex: 1; height: 4px; overflow: hidden; border-radius: 999px;
  background: var(--border);
}
.voice-fill {
  position: absolute; inset: 0 auto 0 0; width: 0%;
  background: var(--accent); border-radius: inherit;
}
.voice-time { min-width: 2.1rem; font-size: 0.68rem; color: var(--muted); text-align: right; }

.input-area {
  position: fixed; bottom: 0; left: 0; right: 0; padding: 10px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  background: transparent; display: flex; flex-direction: column; z-index: 20;
}
.input-area-inner {
  display: flex; align-items: flex-end; width: 100%; min-height: 44px;
  background: #fff8ec; border: 1px solid #e6d8c4; border-radius: 8px;
  padding: 9px 11px 9px 16px;
}
[data-theme="dark"] .input-area-inner { background: rgba(26,23,34,0.85); border-color: #3a3028; }
.input-area textarea {
  flex: 1; font-family: inherit; font-size: 12px; padding: 0;
  border: none; border-radius: 0; background: transparent; color: var(--text);
  resize: none; outline: none; min-height: 24px; max-height: 120px; line-height: 20px; overflow-y: auto;
}
.input-area textarea::placeholder { color: var(--muted); }
#send {
  font-family: inherit; font-size: 0.82rem; padding: 0; border: none;
  border-radius: 8px; background: var(--accent-strong); color: #fff;
  cursor: pointer; width: 39px; height: 25px; min-height: 25px;
  display: flex; align-items: center; justify-content: center; user-select: none;
}
#send:active { opacity: 0.8; }
.btn-attach {
  font-size: 1.3rem; background: transparent !important; border: none !important;
  color: var(--muted) !important; cursor: pointer; margin-right: 8px; line-height: 1;
}
#file-input { display: none; }
.img-preview {
  font-size: 0.72rem; color: var(--muted); padding: 0.45rem; margin-bottom: 0.45rem;
  background: rgba(255,248,236,0.95); border: 1px solid #e6d8c4; border-radius: 8px;
  display: flex; align-items: center; gap: 0.5rem; box-shadow: 0 6px 18px rgba(60,40,20,0.08);
}
[data-theme="dark"] .img-preview { background: rgba(22,19,30,0.95); }
.attach-preview-list { flex:1; display:flex; gap:0.45rem; overflow-x:auto; min-width:0; }
.attach-card { flex:0 0 auto; width:64px; color:var(--text); text-decoration:none; cursor:pointer; }
.attach-thumb {
  width:64px; height:48px; border:1px solid var(--border); border-radius:7px;
  background:var(--card); display:flex; align-items:center; justify-content:center; overflow:hidden;
}
.attach-thumb img { width:100%; height:100%; object-fit:cover; display:block; }
.attach-file-icon { font-size:1.15rem; color:var(--muted); }
.img-preview button { font-size:0.7rem; padding:0.1rem 0.4rem; background:transparent; border:none; color:var(--muted); cursor:pointer; }
</style>
</head>
<body>
<header class="header">
  <button class="hdr-icon hdr-icon-circle" onclick="toggleSidebar()" aria-label="menu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/></svg></button>
</header>
<div class="sidebar-overlay" id="sidebar-overlay" onclick="toggleSidebar()"></div>
<div class="sidebar" id="sidebar">
  <div class="sidebar-header"><h2><span>&mdash;</span> cocoon</h2></div>
  <nav class="sidebar-nav">
    <button class="sidebar-item" onclick="newSession();toggleSidebar()"><span class="si-icon">+</span>new session</button>
    <button class="sidebar-item" onclick="window.location.href='/terminal'"><span class="si-icon">&gt;_</span>terminal</button>
    <div class="sidebar-sep"></div>
    <button class="sidebar-item" id="theme-btn" onclick="toggleTheme()"><span class="si-icon">&#9789;</span>toggle theme</button>
    <div class="sidebar-sep"></div>
    <div class="sidebar-section-title">customize</div>
    <button class="sidebar-item" onclick="pickChatBg()"><span class="si-icon">&#9728;</span>change background</button>
    <button class="sidebar-item" onclick="pickAvatar('assistant')"><span class="si-icon">A</span>assistant avatar</button>
    <button class="sidebar-item" onclick="pickAvatar('user')"><span class="si-icon">U</span>my avatar</button>
    <button class="sidebar-item" onclick="resetChatLook()"><span class="si-icon">&#8634;</span>reset look</button>
    <span class="look-note" id="look-note"></span>
  </nav>
  <div class="sidebar-footer"><span class="status" id="status">...</span></div>
</div>
<input type="file" id="chat-bg-input" accept="image/*" hidden onchange="handleChatBgFile(this.files && this.files[0])">
<input type="file" id="avatar-input" accept="image/*" hidden onchange="handleAvatarFile(this.files && this.files[0])">
<div class="chat-area" id="chat">loading...</div>
<div id="lightbox" style="display:none;position:fixed;inset:0;z-index:999;background:rgba(0,0,0,0.88);align-items:center;justify-content:center;cursor:pointer;" onclick="this.style.display='none'"><img id="lb-img" style="max-width:95vw;max-height:95vh;border-radius:4px;object-fit:contain;"></div>
<div class="input-area">
  <div id="img-preview" class="img-preview" style="display:none">
    <div id="attach-preview-list" class="attach-preview-list"></div>
    <button onclick="clearAttach()">x</button>
  </div>
  <input type="file" id="file-input" multiple style="display:none">
  <div class="input-area-inner">
    <span class="btn-attach" onclick="document.getElementById('file-input').click()">+</span>
    <textarea id="input" rows="1" placeholder="send a message..."></textarea>
    <div id="send" role="button" tabindex="-1"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg></div>
  </div>
</div>
<script>
const TOKEN = localStorage.getItem('cocoon_token') || prompt('Enter your token:');
if (TOKEN) { localStorage.setItem('cocoon_token', TOKEN); document.cookie = 'token=' + TOKEN + '; path=/; SameSite=Strict'; }
const headers = { 'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json' };
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const statusEl = document.getElementById('status');

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
  document.getElementById('sidebar-overlay').classList.toggle('open');
}

function toggleTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  if (isDark) {
    document.documentElement.removeAttribute('data-theme');
    localStorage.setItem('theme', 'light');
    document.querySelector('#meta-theme').setAttribute('content', '#FBF5EC');
  } else {
    document.documentElement.setAttribute('data-theme', 'dark');
    localStorage.setItem('theme', 'dark');
    document.querySelector('#meta-theme').setAttribute('content', '#14111B');
  }
}

const LOOK_KEYS = { bg: 'cocoon_chat_bg', userAvatar: 'cocoon_avatar_user', assistantAvatar: 'cocoon_avatar_assistant' };
let pendingAvatarTarget = 'assistant';

function setLookNote(text) { var el = document.getElementById('look-note'); if (el) el.textContent = text || ''; }

function avatarSrc(role) {
  if (role === 'user') return localStorage.getItem(LOOK_KEYS.userAvatar) || '';
  return localStorage.getItem(LOOK_KEYS.assistantAvatar) || '';
}

function avatarContent(role) {
  const src = avatarSrc(role);
  if (src) return '<img src="' + src + '">';
  return role === 'user' ? 'U' : 'A';
}

function applyChatLook() {
  const bg = localStorage.getItem(LOOK_KEYS.bg);
  if (bg) document.documentElement.style.setProperty('--chat-bg-image', 'url("' + bg + '")');
  else document.documentElement.style.removeProperty('--chat-bg-image');
}

function fitImageFile(file, maxSide, quality, done) {
  if (!file || !file.type || !file.type.startsWith('image/')) { setLookNote('choose an image'); return; }
  const reader = new FileReader();
  reader.onload = function() {
    const img = new Image();
    img.onload = function() {
      let w = img.naturalWidth, h = img.naturalHeight;
      const scale = Math.min(1, maxSide / Math.max(w, h));
      w = Math.round(w * scale); h = Math.round(h * scale);
      const canvas = document.createElement('canvas');
      canvas.width = w; canvas.height = h;
      canvas.getContext('2d').drawImage(img, 0, 0, w, h);
      done(canvas.toDataURL('image/jpeg', quality));
    };
    img.src = reader.result;
  };
  reader.readAsDataURL(file);
}

function saveLookValue(key, value, okText) {
  try { localStorage.setItem(key, value); applyChatLook(); setLookNote(okText); }
  catch (e) { setLookNote('image too large'); }
}

function pickChatBg() { document.getElementById('chat-bg-input').click(); }
function handleChatBgFile(file) { fitImageFile(file, 1600, 0.82, function(d) { saveLookValue(LOOK_KEYS.bg, d, 'background changed'); }); }
function pickAvatar(role) { pendingAvatarTarget = role; document.getElementById('avatar-input').click(); }
function handleAvatarFile(file) {
  const key = pendingAvatarTarget === 'user' ? LOOK_KEYS.userAvatar : LOOK_KEYS.assistantAvatar;
  fitImageFile(file, 512, 0.86, function(d) { saveLookValue(key, d, 'avatar changed'); });
}
function resetChatLook() {
  Object.values(LOOK_KEYS).forEach(function(k) { localStorage.removeItem(k); });
  applyChatLook(); setLookNote('look reset');
}
applyChatLook();

let _blocks = [], _isBusy = false, _lastRawHash = 0, _unchangedPolls = 0;
let _optimisticText = null, _typingEl = null, _deferredBlocks = null;
let _statusIv = null;

function simpleHash(s) {
  var h = 0;
  for (var i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  return h;
}

function escHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function openLightbox(src) {
  document.getElementById('lb-img').src = src;
  document.getElementById('lightbox').style.display = 'flex';
}

function basenameFromPath(path) {
  return (path || '').trim().split(/[\\/]/).pop();
}

function nlToBr(text) {
  return text.replace(/\n/g, '<br>').replace(/(<br>\s*){2,}/g, '<br><span style="display:block;margin-top:0.5em"></span>');
}

function collapseLines(lines) {
  var out = [];
  var buf = '';
  var BREAK_PAT = /^(?:[-*>\u2022|]|[\u2500-\u257F])|^#{1,3} |^\d+[.)] |^```/;
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (line.trim() === '') {
      if (buf) { out.push(buf); buf = ''; }
      out.push('');
    } else if (BREAK_PAT.test(line.trimStart())) {
      if (buf) { out.push(buf); buf = ''; }
      buf = line;
    } else {
      buf += line;
    }
  }
  if (buf) out.push(buf);
  return out;
}

function renderFileRefs(html) {
  html = html.replace(/\[image\]\s*([^\r\n]+\.(jpg|jpeg|png|gif|webp))/gi, function(m, path) {
    var name = basenameFromPath(path);
    if (!name) return m;
    var url = '/files/' + encodeURIComponent(name) + '?token=' + encodeURIComponent(TOKEN);
    return '<img src="' + url + '" style="width:120px;height:120px;object-fit:cover;border-radius:8px;margin:0.3em 0;display:block;cursor:pointer;border:1px solid var(--border);" loading="lazy" onclick="openLightbox(this.src)">';
  });
  html = html.replace(/\[file\]\s*([^\r\n]+)/gi, function(m, path) {
    var name = basenameFromPath(path);
    if (!name) return m;
    var url = '/files/' + encodeURIComponent(name) + '?token=' + encodeURIComponent(TOKEN);
    return '<a href="' + url + '" target="_blank" rel="noopener" style="display:inline-flex;align-items:center;gap:0.3em;background:var(--code-bg);padding:0.25em 0.6em;border-radius:5px;font-size:0.82em;color:inherit;text-decoration:none;">file</a>';
  });
  return html;
}

function renderVoiceNote(id) {
  id = (id || '').toLowerCase();
  if (!/^[a-f0-9]{16,64}$/.test(id)) return '';
  var src = '/tts/audio/' + encodeURIComponent(id + '.mp3') + '?token=' + encodeURIComponent(TOKEN);
  return '<div class="voice-note" data-voice-id="' + id + '"><button class="voice-play" type="button" aria-label="play voice">play</button><div class="voice-track"><span class="voice-fill"></span></div><span class="voice-time">0:00</span><audio preload="metadata" src="' + src + '"></audio></div>';
}

function renderVoiceRefs(html) {
  html = html.replace(/\[\[(?:cocoon_voice|voice):([a-f0-9]{16,64})\]\]/gi, function(_, id) {
    return renderVoiceNote(id);
  });
  html = html.replace(/(^|[\s(>])(?:\/bridge)?\/tts\/audio\/([a-f0-9]{16,64})\.mp3(?=$|[\s<)])/gi, function(_, prefix, id) {
    return prefix + renderVoiceNote(id);
  });
  return html;
}

function renderMarkdownTables(text) {
  text = text.replace(/((?:^|\n)\|[^\n]+\|(?:\n\|[\s:|-]+\|)(?:\n\|[^\n]+\|)+)/g, function(block) {
    var rows = block.replace(/^\n/, '').split('\n').filter(function(r) { return r.trim(); });
    if (rows.length < 2) return block;
    var isSep = function(r) { return /^\|[\s:|-]+\|$/.test(r.trim()); };
    var parseRow = function(r) { return r.replace(/^\|/, '').replace(/\|$/, '').split('|').map(function(c) { return c.trim(); }); };
    var html = '<div class="md-table-scroll"><table>';
    var headerDone = false;
    for (var ri = 0; ri < rows.length; ri++) {
      if (isSep(rows[ri])) { headerDone = true; continue; }
      var cells = parseRow(rows[ri]);
      var tag = (!headerDone && ri === 0) ? 'th' : 'td';
      html += '<tr>' + cells.map(function(c) { return '<' + tag + '>' + c + '</' + tag + '>'; }).join('') + '</tr>';
      if (tag === 'th') headerDone = true;
    }
    return html + '</table></div>';
  });
  text = text.replace(/((?:^|\n)[\u2500-\u257F][^\n]*(?:\n[\u2500-\u257F][^\n]*)+)/g, function(block) {
    var body = block.replace(/^\n/, '').replace(/\n/g, '&#10;');
    return '<pre class="box-table">' + body + '</pre>';
  });
  return text;
}

function renderMessageContent(text, role) {
  text = role === 'assistant' ? collapseLines((text || '').split('\n')).join('\n').trim() : (text || '').trim();
  text = escHtml(text);
  if (role === 'assistant') {
    text = text.replace(/```([\s\S]*?)```/g, function(m,c) {
      return '<details class="msg-tool"><summary>code</summary><pre>'+c.trim()+'</pre></details>';
    });
    text = text.replace(/`([^`]+)`/g, '<code style="background:var(--code-bg);padding:0.1em 0.3em;border-radius:3px;font-size:0.8em;">$1</code>');
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/~~(.+?)~~/g, '<del>$1</del>');
    text = text.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, '<em>$1</em>');
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    text = text.replace(/^(#{1,3})\s+(.+)$/gm, function(m, h, c) {
      var s = h.length === 1 ? '1.05em' : h.length === 2 ? '0.95em' : '0.88em';
      return '<span class="md-h" style="font-size:'+s+'">'+c+'</span>';
    });
    text = text.replace(/^&gt;\s?(.*)$/gm, '<span class="md-bq">$1</span>');
    text = text.replace(/^(?:---+|\*\*\*+|___+)\s*$/gm, '<span class="md-hr"></span>');
    text = text.replace(/^[-•]\s+(.+)$/gm, '<span class="md-li">• $1</span>');
    text = text.replace(/^(\d+)[.)]\s+(.+)$/gm, '<span class="md-li">$1. $2</span>');
    text = renderMarkdownTables(text);
  }
  text = renderFileRefs(text);
  text = renderVoiceRefs(text);
  return text;
}

function renderMessageParts(html, role, rawText) {
  var isUser = role === 'user';
  var wrapCls = isUser ? 'msg-wrap-user' : 'msg-wrap-assistant';
  var avatarCls = isUser ? 'avatar-user' : 'avatar-assistant';
  var avatarHtml = avatarContent(isUser ? 'user' : 'assistant');
  var msgCls = isUser ? 'msg-user' : 'msg-assistant';
  var parts = html.split(/(<img[^>]+>)/g);
  var out = '';
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i];
    if (!part) continue;
    if (/^<img/.test(part)) {
      out += '<div class="msg-wrap ' + wrapCls + '"><div class="avatar ' + avatarCls + '">' + avatarHtml + '</div><div>' + part + '</div></div>';
    } else {
      part = nlToBr(part).replace(/^(<br>\s*)+|(<br>\s*)+$/g, '').trim();
      if (part) out += '<div class="msg-wrap ' + wrapCls + '"><div class="avatar ' + avatarCls + '">' + avatarHtml + '</div><div><div class="msg ' + msgCls + '">' + part + '</div></div></div>';
    }
  }
  return out ? { type: role, text: rawText, html: '<div class="msg-group">' + out + '</div>' } : null;
}

function renderBlockHtml(b) {
  if (b.type === 'user') {
    var rawUserText = b.lines.join('\n').trim();
    var userText = renderFileRefs(escHtml(rawUserText));
    return renderMessageParts(userText, 'user', rawUserText);
  } else if (b.type === 'assistant') {
    var rawAssistantText = b.lines.join('\n').trim();
    var assistantText = renderMessageContent(rawAssistantText, 'assistant');
    return renderMessageParts(assistantText, 'assistant', rawAssistantText);
  } else if (b.type === 'tool') {
    var summary = b.lines[0] || 'tool';
    var body = b.lines.slice(1).join('\n').trim();
    var h = '<details class="msg-tool"><summary>' + escHtml(summary) + '</summary>';
    if (body) h += '<pre>' + escHtml(body) + '</pre>';
    h += '</details>';
    return { type: 'tool', html: h };
  } else if (b.type === 'channel') {
    var label = escHtml((b.platform || '') + ' · ' + (b.sender || ''));
    var body = escHtml(b.lines.join('\n').trim()).replace(/\n/g, '<br>');
    if (!body) return null;
    return { type: 'channel', html: '<div class="msg-channel"><strong>' + label + '</strong><br>' + body + '</div>' };
  } else if (b.type === 'system') {
    return { type: 'system', html: '<div class="msg-system">' + escHtml(b.text) + '</div>' };
  }
  return null;
}

function parseBlocks(raw) {
  var lines = raw.split('\n');
  var blocks = [];
  var current = null;

  var SEP = /^[─━╌]{10,}/;
  var PROMPT = /^❯/;
  var CHANNEL = /^← (\S+) · ([^:]+):\s*(.*)/;
  var TOOL_CALL = /^●\s+(?:Read|Write|Edit|Bash|Grep|Glob|Search|WebFetch|WebSearch|Agent|Task|Monitor|Skill|mcp__\w+)[\(\[{:/ ]/;
  var TOOL_STATUS = /^●\s+(?:Called|Calling|Ran|Running|Read|Wrote|Edited|Updated|Searched|Listed)\b/;
  var TOOL_RESULT = /^\s+(?:⎿|↳)/;
  var ASSISTANT_START = /^● /;
  var TIMER = /^✻/;
  var NOISE = /Claude Code v|^\s*▐▛|^\s*▝▜|^Resume this|^\s*\? for shortcuts|^\s*Opus \d|^\s*Create file|^╭|^╰/;

  function flush() { if (current) { blocks.push(current); current = null; } }
  var TOOL_CALL_EXTRA = /^●\s+(?:MultiEdit|Update|Notebook|PowerShell|TodoWrite|ExitPlanMode|EnterPlanMode|EnterWorktree|ExitWorktree|ToolSearch|AskUserQuestion|ScheduleWakeup|TaskCreate|TaskGet|TaskList|TaskOutput|TaskStop|TaskUpdate|CronCreate|CronDelete|CronList|NotebookEdit|PushNotification|RemoteTrigger|SendMessage|ListMcpResourcesTool|ReadMcpResourceTool|functions\.[A-Za-z_]\w*|mcp__[A-Za-z0-9_]+|multi_tool_use\.[A-Za-z_]\w*|web\.[A-Za-z_]\w*|image_gen\.[A-Za-z_]\w*|tool_search\.[A-Za-z_]\w*|browser_[A-Za-z_]\w*)(?:[\(\[{:：/ ]|$)/;
  var TOOL_STATUS_EXTRA = /^●\s+(?:Uploaded|Downloaded)\b/;
  var COLLAPSED_READ = /^\s+(?:Read \d+ file|listed \d+ dir|\d+ (?:lines?|items?|files?) |Exit code:|Wall time:|Output:)/;
  var TOOL_JSON = /^\s*(?:[{[]\s*"?(?:tool_uses|recipient_name|parameters|command|code|path|files|prompt|provider|sandbox_permissions|justification|timeout_ms|workdir)"?|"?(?:tool_uses|recipient_name|parameters|command|code|path|files|prompt|provider|sandbox_permissions|justification|timeout_ms|workdir)"?\s*:)/;
  var DIFF_LINE = /^\s{4,}\d+[\s\u2502|]/;
  var TABLE_LINE = /^\s*(?:\|.+\||[\u2500-\u257F].*)\s*$/;
  function isDisplayNoise(line) {
    return /<local-command-caveat>|<command-name>|<command-message>|<command-args>|<local-command-stdout>|<local-command-stderr>|This session is being continued from a previous conversation|Continue the conversation from where it left off|Compacted PreCompact|PostCompact /.test(line || '');
  }
  function isPreLaunchNoise(line) {
    return /\[pre-launch\]|memory pipeline started|injection hint written|"source_events"|"sanitized_events"|"kept_events"|"estimated_tokens_(?:scanned|kept)"|"raw_cut_index"|"keep_start_index"|"thinking_blocks_kept"|\/backups\/forge_reload\//.test(line || '');
  }
  function isStandaloneUploadNoise(line) {
    var t = (line || '').trim();
    if (!t) return false;
    if (/^\[(?:image|file)\]\s+/.test(t)) return false;
    if (/^\/(?:tmp\/)?(?:cocoon-uploads|uploads)\/[^\s]+$/i.test(t)) return true;
    if (/^(?:file(?:name)?|uploaded file)[:：]\s*[\w.-]+\.[a-z0-9]{2,8}$/i.test(t)) return true;
    if (/^[a-f0-9]{16,}\.(?:jpg|jpeg|png|gif|webp|heic|bmp|pdf|docx?|xlsx?|txt|zip)$/i.test(t)) return true;
    return false;
  }

  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    if (SEP.test(line) || NOISE.test(line) || DIFF_LINE.test(line)) { continue; }
    if (isDisplayNoise(line)) { flush(); continue; }
    if (isPreLaunchNoise(line)) { flush(); continue; }
    if (isStandaloneUploadNoise(line)) { continue; }
    if (/How is Claude doing/.test(line) || /^\s+\d: (Bad|Fine|Good|Dismiss)/.test(line)) { continue; }

    if (TIMER.test(line)) { flush(); blocks.push({ type: 'system', text: line.replace(/^✻\s*/, '') }); continue; }

    var chm = line.match(CHANNEL);
    if (chm) { flush(); current = { type: 'channel', platform: chm[1], sender: chm[2].trim(), lines: chm[3] ? [chm[3]] : [] }; continue; }
    if (current && current.type === 'channel' && /^  /.test(line) && line.trim()) { current.lines.push(line.trimStart()); continue; }

    if (PROMPT.test(line)) {
      flush();
      var msg = line.replace(/^❯[\s\xa0]*/, '');
      if (msg && !/^Try "/.test(msg)) current = { type: 'user', lines: [msg] };
      continue;
    }
    if (current && current.type === 'user' && /^  /.test(line) && line.trim()) { current.lines.push(line.trimStart()); continue; }
    if (current && current.type === 'user' && line.trim() === '') { current.lines.push(''); continue; }

    if (TOOL_CALL.test(line) || TOOL_STATUS.test(line) || TOOL_CALL_EXTRA.test(line) || TOOL_STATUS_EXTRA.test(line)) { flush(); current = { type: 'tool', lines: [line.replace(/^● /, '')] }; continue; }
    if (current && current.type === 'tool') {
      if (PROMPT.test(line) || ASSISTANT_START.test(line) || TIMER.test(line) || TOOL_CALL.test(line) || TOOL_STATUS.test(line) || TOOL_CALL_EXTRA.test(line) || TOOL_STATUS_EXTRA.test(line) || TABLE_LINE.test(line)) { flush(); }
      else { current.lines.push(line); continue; }
    }
    if (COLLAPSED_READ.test(line) || TOOL_JSON.test(line) || TOOL_RESULT.test(line)) { flush(); current = { type: 'tool', lines: [line.trim()] }; continue; }

    if (ASSISTANT_START.test(line)) { flush(); current = { type: 'assistant', lines: [line.replace(/^● /, '')] }; continue; }
    if (current && current.type === 'assistant' && /^  /.test(line)) { current.lines.push(line.replace(/^  /, '')); continue; }
    if (current && current.type === 'assistant' && line.trim() === '') { current.lines.push(''); continue; }

    if (line.trim() === '') continue;
    if (!current || current.type !== 'assistant') { flush(); current = { type: 'assistant', lines: [line] }; }
    else { current.lines.push(line); }
  }
  flush();

  var merged = [];
  for (var j = 0; j < blocks.length; j++) {
    var b = blocks[j];
    var prev = merged.length > 0 ? merged[merged.length-1] : null;
    if (b.type === 'assistant' && prev && prev.type === 'assistant') { prev.lines.push('', ...b.lines); }
    else { merged.push(b); }
  }

  var result = [];
  for (var k = 0; k < merged.length; k++) {
    var rendered = renderBlockHtml(merged[k]);
    if (rendered) result.push(rendered);
  }
  return result;
}

var _typingBubbleHtml = '<div class="msg-wrap msg-wrap-assistant"><div class="avatar avatar-assistant">' + avatarContent('assistant') + '</div><div><div class="msg msg-assistant typing-bubble"><span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span></div></div></div>';

function formatVoiceTime(sec) {
  if (!isFinite(sec) || sec < 0) sec = 0;
  var m = Math.floor(sec / 60);
  var s = Math.floor(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}

function isVoicePlaying() {
  return Array.prototype.some.call(chat.querySelectorAll('.voice-note audio'), function(audio) {
    return !audio.paused && !audio.ended;
  });
}

function flushDeferredPaint() {
  if (!_deferredBlocks || isVoicePlaying()) return;
  var b = _deferredBlocks;
  _deferredBlocks = null;
  paintChat(b);
}

function bindVoicePlayers() {
  chat.querySelectorAll('.voice-note').forEach(function(note) {
    if (note.dataset.bound === '1') return;
    note.dataset.bound = '1';
    var audio = note.querySelector('audio');
    var btn = note.querySelector('.voice-play');
    var fill = note.querySelector('.voice-fill');
    var time = note.querySelector('.voice-time');
    if (!audio || !btn || !fill || !time) return;

    function update() {
      var duration = audio.duration || 0;
      var pct = duration ? Math.min(100, (audio.currentTime / duration) * 100) : 0;
      fill.style.width = pct + '%';
      time.textContent = formatVoiceTime(audio.currentTime || duration || 0);
    }

    btn.addEventListener('click', function() {
      if (audio.paused) {
        chat.querySelectorAll('.voice-note audio').forEach(function(other) {
          if (other !== audio) other.pause();
        });
        audio.play().catch(function() {});
      } else {
        audio.pause();
      }
    });
    audio.addEventListener('play', function() { btn.textContent = 'pause'; });
    audio.addEventListener('pause', function() { btn.textContent = 'play'; flushDeferredPaint(); });
    audio.addEventListener('ended', function() { btn.textContent = 'play'; update(); flushDeferredPaint(); });
    audio.addEventListener('loadedmetadata', update);
    audio.addEventListener('timeupdate', update);
    audio.addEventListener('error', function() { btn.textContent = 'error'; flushDeferredPaint(); });
  });
}

function appendBlockEl(block, beforeEl) {
  var tmp = document.createElement('div');
  tmp.innerHTML = block.html;
  var el = tmp.firstElementChild || tmp.firstChild;
  if (!el) return null;
  el._bh = block.html;
  if (beforeEl) chat.insertBefore(el, beforeEl);
  else chat.appendChild(el);
  return el;
}

function paintChat(newBlocks) {
  if (isVoicePlaying()) { _deferredBlocks = newBlocks; return; }
  var wasAtBottom = chat.scrollTop + chat.clientHeight >= chat.scrollHeight - 30;

  if (_typingEl && _typingEl.parentNode) _typingEl.remove();

  var optEl = document.getElementById('optimistic-msg');
  if (optEl && _optimisticText) {
    for (var oi = 0; oi < newBlocks.length; oi++) {
      if (newBlocks[oi].type === 'user' && newBlocks[oi].text && newBlocks[oi].text.trim() === _optimisticText.trim()) {
        optEl.remove(); optEl = null; _optimisticText = null; break;
      }
    }
  }

  var msgEls = [];
  for (var ci = 0; ci < chat.children.length; ci++) {
    var c = chat.children[ci];
    if (c.id !== 'optimistic-msg' && c.id !== 'typing-indicator') msgEls.push(c);
  }

  var same = 0;
  while (same < msgEls.length && same < newBlocks.length) {
    if (msgEls[same]._bh !== newBlocks[same].html) break;
    same++;
  }

  for (var ri = msgEls.length - 1; ri >= same; ri--) msgEls[ri].remove();

  var anchor = document.getElementById('optimistic-msg');
  for (var ai = same; ai < newBlocks.length; ai++) appendBlockEl(newBlocks[ai], anchor);

  _blocks = newBlocks;

  if (_isBusy) {
    if (!_typingEl) { _typingEl = document.createElement('div'); _typingEl.id = 'typing-indicator'; }
    _typingEl.innerHTML = _typingBubbleHtml;
    chat.appendChild(_typingEl);
  }

  bindVoicePlayers();
  if (wasAtBottom) { bindBottomOnMediaLoad(); scrollChatToBottom(); }
}

function scrollChatToBottom() {
  const settle = function() { chat.scrollTop = chat.scrollHeight; };
  requestAnimationFrame(function() {
    settle();
    setTimeout(settle, 80);
    setTimeout(settle, 240);
    setTimeout(settle, 650);
  });
}

function bindBottomOnMediaLoad() {
  chat.querySelectorAll('img').forEach(function(img) {
    if (img.dataset.bottomScrollBound === '1') return;
    img.dataset.bottomScrollBound = '1';
    if (!img.complete) {
      img.addEventListener('load', scrollChatToBottom, { once: true });
      img.addEventListener('error', scrollChatToBottom, { once: true });
    }
  });
}

function startStatusPoll(ms) {
  if (_statusIv) clearInterval(_statusIv);
  _statusIv = setInterval(checkStatus, ms);
}

function setBusy(busy) {
  var next = !!busy;
  if (_isBusy === next) return;
  _isBusy = next;
  startStatusPoll(next ? 3000 : 8000);
  if (!next && _typingEl && _typingEl.parentNode) _typingEl.remove();
  else if (next && _blocks.length) paintChat(_blocks);
}

async function checkStatus() {
  try {
    const r = await fetch('/status', { headers });
    const d = await r.json();
    const state = d.running ? 'alive' : (d.alive ? (d.command || 'shell') : 'stopped');
    statusEl.textContent = state;
    statusEl.className = 'status ' + (d.running ? 'alive' : 'dead');
    setBusy(d.running && d.busy);
  } catch(e) {
    statusEl.textContent = 'offline';
    statusEl.className = 'status dead';
    setBusy(false);
  }
}

let _autoStartTried = false;
async function getOutput() {
  try {
    var r = await fetch('/output?lines=1500', { headers });
    if (!r.ok) {
      if (!_autoStartTried && (r.status === 404 || r.status === 409)) {
        _autoStartTried = true;
        chat.innerHTML = '<div class="msg-system">starting session...</div>';
        try { await fetch('/start', { method: 'POST', headers }); } catch(e) {}
        setTimeout(getOutput, 5000);
      } else if (!_blocks.length) {
        chat.innerHTML = '<div class="msg-system">session stopped</div>';
      }
      return;
    }
    var text = await r.text();
    var hash = simpleHash(text);

    if (hash === _lastRawHash) {
      _unchangedPolls++;
      if (_unchangedPolls >= 2 && _isBusy) checkStatus();
      return;
    }

    _lastRawHash = hash;
    _unchangedPolls = 0;

    var blocks = parseBlocks(text);
    paintChat(blocks);
  } catch(e) {
    if (!_blocks.length) chat.innerHTML = '<div class="msg-system">bridge offline</div>';
  }
}

let pendingFiles = [];

function renderAttachPreview() {
  const box = document.getElementById('img-preview');
  const list = document.getElementById('attach-preview-list');
  list.innerHTML = '';
  pendingFiles.forEach(function(fi) {
    const url = '/files/' + encodeURIComponent(fi.filename) + '?token=' + encodeURIComponent(TOKEN);
    const isImg = /\.(jpg|jpeg|png|gif|webp)$/i.test(fi.filename);
    const card = document.createElement(isImg ? 'div' : 'a');
    card.className = 'attach-card'; card.title = fi.filename;
    if (isImg) card.onclick = function() { openLightbox(url); };
    else { card.href = url; card.target = '_blank'; }
    const thumb = document.createElement('span');
    thumb.className = 'attach-thumb';
    if (isImg) {
      const img = document.createElement('img');
      img.src = url;
      img.onload = scrollChatToBottom;
      thumb.appendChild(img);
    }
    else { const icon = document.createElement('span'); icon.className = 'attach-file-icon'; icon.textContent = 'file'; thumb.appendChild(icon); }
    card.appendChild(thumb); list.appendChild(card);
  });
  box.style.display = pendingFiles.length ? 'flex' : 'none';
}

async function handleFileUpload(inputEl) {
  for (const file of inputEl.files) {
    const fd = new FormData(); fd.append('file', file);
    try {
      const r = await fetch('/upload', { method: 'POST', headers: { 'Authorization': 'Bearer ' + TOKEN }, body: fd });
      pendingFiles.push(await r.json());
    } catch(e) { alert('upload failed: ' + file.name); }
  }
  if (pendingFiles.length > 0) {
    renderAttachPreview();
    scrollChatToBottom();
  }
  inputEl.value = '';
}
document.getElementById('file-input').addEventListener('change', function() { handleFileUpload(this); });

function clearAttach() {
  pendingFiles = [];
  document.getElementById('img-preview').style.display = 'none';
  document.getElementById('attach-preview-list').innerHTML = '';
}

let _lastSend = 0;
async function sendMsg() {
  var now = Date.now();
  if (now - _lastSend < 600) return;
  _lastSend = now;
  var text = input.value;
  if (pendingFiles.length > 0) {
    var refs = pendingFiles.map(function(d) {
      var isImg = /\.(jpg|jpeg|png|gif|webp)$/i.test(d.filename);
      return (isImg ? '[image]' : '[file]') + ' ' + d.path;
    }).join('\n');
    text = text.trim() ? refs + '\n' + text.trim() : refs;
    clearAttach();
  } else {
    text = text.trim();
  }
  if (!text) return;
  input.value = ''; input.style.height = 'auto';

  _optimisticText = text;
  var displayText = renderFileRefs(escHtml(text)).replace(/\n/g, '<br>');
  var optHtml = '<div class="msg-wrap msg-wrap-user" id="optimistic-msg"><div class="avatar avatar-user">' + avatarContent('user') + '</div><div><div class="msg msg-user">' + displayText + '</div></div></div>';
  if (_typingEl && _typingEl.parentNode) _typingEl.insertAdjacentHTML('beforebegin', optHtml);
  else chat.insertAdjacentHTML('beforeend', optHtml);
  scrollChatToBottom();

  setBusy(true);
  try { await fetch('/send', { method: 'POST', headers, body: JSON.stringify({ text }) }); } catch(e) {}
  setTimeout(getOutput, 800);
  setTimeout(checkStatus, 1500);
}

async function newSession() {
  _blocks = []; _deferredBlocks = null; _lastRawHash = 0; _unchangedPolls = 0;
  _optimisticText = null; _typingEl = null;
  chat.innerHTML = '<div class="msg-system">starting new session...</div>';
  try { await fetch('/new-session', { method: 'POST', headers, signal: AbortSignal.timeout(90000) }); } catch(e) {}
  setTimeout(getOutput, 500);
}

document.getElementById('send').addEventListener('click', sendMsg);
input.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing && input.value.trim()) { e.preventDefault(); sendMsg(); }
});
input.addEventListener('input', function() {
  input.style.height = 'auto';
  input.style.height = Math.min(input.scrollHeight, 120) + 'px';
});

getOutput();
checkStatus();
setInterval(getOutput, 2000);
startStatusPoll(8000);
</script>
</body>
</html>
"""


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
  <a href="/chat">&larr; chat</a>
  <span class="title">raw terminal</span>
</div>
<pre id="terminal">loading...</pre>
<div class="input-row">
  <input id="raw-input" placeholder="send raw keys..." onkeydown="if(event.key==='Enter')sendRaw()">
  <button onclick="sendRaw()">send</button>
</div>
<script>
const TOKEN = localStorage.getItem('cocoon_token') || new URLSearchParams(location.search).get('token') || '';
const H = {'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'};
async function refresh() {
  try {
    const r = await fetch('/output', { headers: H });
    const el = document.getElementById('terminal');
    el.textContent = r.ok ? (await r.text()) || '(empty)' : '(no output)';
    el.scrollTop = el.scrollHeight;
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
