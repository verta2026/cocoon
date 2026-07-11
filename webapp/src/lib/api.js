// 桥 API 层。CFG 来自 /config.js（未认证可拉的公共配置），
// 身份细节登录后经 API/app-config 增量叠加（config.private.json）。
// 身份字段集中在可变的 ID 对象——叠加后无需刷新页面即可生效。
export const CFG = window.CFG || {}
export const NS = CFG.storageNs || 'cocoon'
export const API = CFG.apiBase !== undefined ? CFG.apiBase : '/bridge'
export const AI_KEY = CFG.aiKey || 'ai'
export const DEFAULT_BG = CFG.defaultWallpaper || '/wallpaper_default.png'
export const DEMO_STICKERS = CFG.demoStickers || []

export const ID = {
  aiName: CFG.aiName || 'AI',
  userName: CFG.userName || 'User',
  aiAvatar: CFG.aiAvatar || '/avatar_ai.png',
  userAvatar: CFG.userAvatar || '/avatar_user.png',
  userId: CFG.userId || 'user',
  channelNames: CFG.channelNames || {},
}

export const TOKEN = localStorage.getItem(NS + '_token')
export const HEADERS = { 'Content-Type': 'application/json', Authorization: 'Bearer ' + TOKEN }

export function requireToken() {
  if (!TOKEN) {
    // 相对跳转：挂在 / 还是 /app/ 下都指到同目录的 login.html
    window.location.href = 'login.html'
    return false
  }
  return true
}

const GRACE_MS = 10 * 60 * 1000

export function sinceParam(maxId) {
  if (!maxId) return ''
  const ms = parseInt(maxId.slice(0, 15), 10) - GRACE_MS
  return String(Math.max(ms, 0)).padStart(15, '0') + '-'
}

export async function fetchChat(maxId) {
  const r = await fetch(API + '/chat_pure?since=' + encodeURIComponent(sinceParam(maxId)), { headers: HEADERS })
  if (!r.ok) throw new Error(r.status)
  return r.json()
}

export function sendText(text) {
  return fetch(API + '/send', { method: 'POST', headers: HEADERS, body: JSON.stringify({ text }) })
}

// AskUserQuestion 弹窗：answers 与题目等长，每项 {index}|{indexes}|{other}
export function answerAsk(id, answers) {
  return fetch(API + '/ask_answer', { method: 'POST', headers: HEADERS, body: JSON.stringify({ id, answers }) })
    .then(r => (r.ok ? r.json() : { ok: false, reason: String(r.status) }))
}

export function escapeAsk() {
  return fetch(API + '/ask_escape', { method: 'POST', headers: HEADERS }).catch(() => {})
}

// 媒体（壁纸/头像/图片/音乐流）走 HttpOnly 会话 cookie 鉴权，而 cookie 会过期、
// localStorage 里的 bearer token 不会。加载时先用 bearer 重置一次 cookie，保证后续
// <img>/<audio> 不会因 cookie 过期而集体 403 裂图；老用户（有 token 无 cookie）也自愈。
export function ensureCookie() {
  return fetch(API + '/session', { method: 'POST', headers: HEADERS }).catch(() => {})
}

// 幂等引导：fresh clone 无底层会话时 /send 永远 404。/start 服务端幂等，失败不阻断轮询。
export function ensureSession() {
  return fetch(API + '/start', { method: 'POST', headers: HEADERS }).catch(() => {})
}

export function loadPrivateConfig() {
  return fetch(API + '/app-config', { headers: HEADERS })
    .then(r => (r.ok ? r.json() : {}))
    .then(cfg => {
      cfg = cfg || {}
      for (const k of Object.keys(cfg)) {
        if (k === '__proto__' || k === 'constructor' || k === 'prototype') continue
        if (k.charAt(0) !== '_') CFG[k] = cfg[k]
      }
      ID.aiName = CFG.aiName || ID.aiName
      ID.userName = CFG.userName || ID.userName
      ID.aiAvatar = CFG.aiAvatar || ID.aiAvatar
      ID.userAvatar = CFG.userAvatar || ID.userAvatar
      ID.userId = CFG.userId || ID.userId
      ID.channelNames = CFG.channelNames || ID.channelNames
    })
    .catch(() => {})
}
