// 外观层：壁纸/头像 localStorage 键、上传、壁纸取色染 UI。
// extractWallpaperColors 从 chat.html 原样移植（64px 采样均色→HSL→整套变量）。
import { API, NS, AI_KEY, TOKEN, DEFAULT_BG, ID } from './api.js'

export const LOOK = {
  bg: NS + '_chat_bg_image',
  bgDark: NS + '_chat_bg_image_dark',
  userAvatar: NS + '_chat_avatar_user',
  aiAvatar: NS + '_chat_avatar_' + AI_KEY,
}

// 媒体鉴权走 HttpOnly cookie（开机 POST /session 种下，<img>/CSS 请求浏览器自动带）。
// 禁止把 token 拼进 URL：会漏进浏览器历史、Referer 和代理日志。

// isDark/_v 走参数不读全局：渲染期读 localStorage 在编译器眼里是"无依赖计算"，
// 会被缓存成永不更新。_v(lookVer) 必须真的传进来——React Compiler 会重推 useMemo
// 依赖，回调体里没用到的变量会被它从依赖里剔除，光写在依赖数组里不算数
export function wallpaperUrl(isDark, _v) {
  const raw = (isDark ? localStorage.getItem(LOOK.bgDark) : null) || localStorage.getItem(LOOK.bg) || DEFAULT_BG
  return raw
}

export function avatarUrl(role, _v) {
  return role === 'user'
    ? (localStorage.getItem(LOOK.userAvatar) || ID.userAvatar)
    : (localStorage.getItem(LOOK.aiAvatar) || ID.aiAvatar)
}

// 外观选择云端化：图片本就在服务器，"选了哪张"也存服务器，清缓存/换手机照样在
export function saveLook(serverKey, url) {
  const o = {}
  o[serverKey] = url || ''
  fetch(API + '/look', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + TOKEN },
    body: JSON.stringify(o),
  }).catch(() => {})
}

// 启动时从服务器读回选择（服务器优先）；服务器空、本地有则一次性备份上云
export function loadLook() {
  return fetch(API + '/look', { headers: { Authorization: 'Bearer ' + TOKEN } })
    .then(r => (r.ok ? r.json() : null))
    .then(d => {
      const L = (d && d.look) || {}
      const map = { bg: LOOK.bg, bgDark: LOOK.bgDark, userAvatar: LOOK.userAvatar, aiAvatar: LOOK.aiAvatar }
      Object.keys(map).forEach(sk => {
        if (L[sk]) {
          try { localStorage.setItem(map[sk], L[sk]) } catch (e) {}
        } else {
          let local = null
          try { local = localStorage.getItem(map[sk]) } catch (e) {}
          if (local) saveLook(sk, local)
        }
      })
    })
    .catch(() => {})
}

// 上传前压缩：手机原图动辄 8MB，裸传又慢又占盘。长边封顶缩放 + JPEG 0.85；
// 已经够小的原样走，解不出来的（罕见格式）也原样走，压缩永远不拦路
export function shrinkImage(file, maxDim) {
  return new Promise(resolve => {
    const url = URL.createObjectURL(file)
    const img = new Image()
    img.onload = () => {
      URL.revokeObjectURL(url)
      const s = Math.min(1, maxDim / Math.max(img.width, img.height))
      if (s === 1 && file.size < 600 * 1024) return resolve(file)
      const cv = document.createElement('canvas')
      cv.width = Math.round(img.width * s)
      cv.height = Math.round(img.height * s)
      cv.getContext('2d').drawImage(img, 0, 0, cv.width, cv.height)
      cv.toBlob(b => {
        if (!b) return resolve(file)
        resolve(new File([b], file.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' }))
      }, 'image/jpeg', 0.85)
    }
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file) }
    img.src = url
  })
}

// XHR instead of fetch: fetch can't report upload progress, and a big file
// over mobile data looks frozen for minutes before dying with no reason.
export function uploadToServer(file, onProgress) {
  return new Promise((resolve, reject) => {
    const fd = new FormData()
    fd.append('file', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', API + '/upload')
    xhr.setRequestHeader('Authorization', 'Bearer ' + TOKEN)
    if (onProgress) {
      xhr.upload.onprogress = e => {
        if (e.lengthComputable) onProgress(Math.min(99, Math.round((e.loaded / e.total) * 100)))
      }
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)) } catch (e) { reject(new Error('bad response')) }
      } else {
        const err = new Error('upload failed: ' + xhr.status)
        err.status = xhr.status
        reject(err)
      }
    }
    xhr.onerror = () => reject(new Error('network error'))
    xhr.send(fd)
  })
}

function rgb2hsl(r, g, b) {
  r /= 255; g /= 255; b /= 255
  const mx = Math.max(r, g, b)
  const mn = Math.min(r, g, b)
  let h, s
  const l = (mx + mn) / 2
  if (mx === mn) { h = s = 0 }
  else {
    const d = mx - mn
    s = l > 0.5 ? d / (2 - mx - mn) : d / (mx + mn)
    if (mx === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
    else if (mx === g) h = ((b - r) / d + 2) / 6
    else h = ((r - g) / d + 4) / 6
  }
  return [Math.round(h * 360), Math.round(s * 100), Math.round(l * 100)]
}

const hsl = (h, s, l, a) => (a !== undefined ? `hsla(${h},${s}%,${l}%,${a})` : `hsl(${h},${s}%,${l}%)`)

export function extractWallpaperColors(url, frostEl) {
  const img = new Image()
  // 不设 crossOrigin：媒体鉴权在 HttpOnly cookie 里，anonymous 模式的请求不带
  // cookie → 壁纸 401 → onload 永不触发，取色整个静默死。壁纸全部同源，
  // 同源图不污染 canvas，本来就不需要 CORS 模式
  img.onload = () => {
    const c = document.createElement('canvas')
    const sz = 64
    c.width = sz; c.height = sz
    const ctx = c.getContext('2d')
    ctx.drawImage(img, 0, 0, sz, sz)
    const data = ctx.getImageData(0, 0, sz, sz).data
    let rT = 0, gT = 0, bT = 0
    const n = data.length / 4
    for (let i = 0; i < data.length; i += 4) { rT += data[i]; gT += data[i + 1]; bT += data[i + 2] }
    const [H, sRaw] = rgb2hsl(Math.round(rT / n), Math.round(gT / n), Math.round(bT / n))
    const S = Math.min(sRaw, 30)
    const night = document.documentElement.getAttribute('data-theme') === 'dark'
    const root = document.documentElement

    let vars
    if (night) {
      if (frostEl) {
        frostEl.style.cssText = 'position:fixed;inset:0;pointer-events:none;background:rgba(0,0,0,0.45);z-index:1'
        frostEl.style.display = 'block'
      }
      vars = {
        '--c-bubble': hsl(H, S, 95, 0.10),
        '--c-me': hsl(H, S, 95, 0.16),
        '--c-me-text': hsl(H, Math.min(S, 15), 92),
        '--c-text': hsl(H, Math.min(S, 15), 92),
        '--c-muted': hsl(H, Math.min(S, 10), 80, 0.5),
        '--c-input': hsl(H, S, 24, 0.62),
        '--c-border': hsl(H, S, 90, 0.12),
        '--c-code': hsl(H, S, 95, 0.08),
        '--c-send': hsl(H, Math.min(S + 20, 50), 65),
        '--c-send-glow': hsl(H, Math.min(S + 20, 50), 65, 0.35),
        '--c-accent': hsl(H, Math.min(S + 20, 50), 65),
        '--c-card': hsl(H, S, 30, 0.45),
        '--c-panel': hsl(H, S, 16, 0.5),
        '--c-hdr': hsl(H, S, 14, 0.6),
        '--c-side': hsl(H, S, 12, 0.65),
        '--c-divider': hsl(H, S, 90, 0.1),
        '--c-ov': 'rgba(0,0,0,0.4)',
      }
    } else {
      if (frostEl) frostEl.style.display = 'none'
      vars = {
        '--c-bubble': hsl(H, Math.min(S + 10, 35), 96, 0.88),
        '--c-me': hsl(H, Math.min(S + 15, 40), 88, 0.9),
        '--c-me-text': hsl(H, Math.min(S, 20), 18),
        '--c-text': hsl(H, Math.min(S, 20), 18),
        '--c-muted': hsl(H, Math.min(S, 15), 40, 0.6),
        '--c-input': hsl(H, Math.min(S + 5, 25), 98, 0.95),
        '--c-border': hsl(H, S, 20, 0.08),
        '--c-code': hsl(H, Math.min(S + 5, 25), 92, 0.65),
        '--c-send': hsl(H, Math.min(S + 25, 55), 55),
        '--c-send-glow': hsl(H, Math.min(S + 25, 55), 55, 0.3),
        '--c-accent': hsl(H, Math.min(S + 25, 55), 42),
        '--c-card': hsl(H, Math.min(S + 5, 25), 97, 0.72),
        '--c-panel': hsl(H, Math.min(S + 10, 30), 96, 0.78),
        '--c-hdr': hsl(H, Math.min(S + 5, 25), 96, 0.75),
        '--c-side': hsl(H, Math.min(S + 10, 30), 96, 0.9),
        '--c-divider': hsl(H, S, 20, 0.06),
        '--c-ov': hsl(H, S, 50, 0.1),
      }
    }
    for (const key in vars) {
      root.style.setProperty(key, vars[key])
      document.body.style.setProperty(key, vars[key])
    }
  }
  img.src = url
}
