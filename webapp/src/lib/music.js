// 音乐播放 store：模块级单例 <audio> + 订阅通知。
// 逻辑从 chat.html playMusicById/togglePlay/恢复段移植；渲染交给 React 组件。
import { CFG, API, HEADERS, NS } from './api.js'

export const audio = new Audio()
audio.crossOrigin = 'anonymous'

let track = { title: '未在播放', artist: '', dur: 0, cover: '' }
let st = { open: false, min: false, playing: false, elapsed: 0 }
let snap = { ...st, track }
const subs = new Set()
let iv = null

function notify() {
  snap = { ...st, track: { ...track } }
  subs.forEach(f => f())
}

export function subscribe(f) {
  subs.add(f)
  return () => subs.delete(f)
}

export function getMusic() {
  return snap
}

export function liveTime() {
  return audio.currentTime || st.elapsed || 0
}

function startTick() {
  clearInterval(iv)
  iv = setInterval(() => { track.dur = audio.duration || track.dur; notify() }, 500)
}

export function openFull() {
  st = { ...st, open: true, min: false }
  notify()
}

export function minimize() {
  st = { ...st, min: true }
  notify()
}

export function expand() {
  st = { ...st, min: false }
  notify()
}

export function closeMusic() {
  clearInterval(iv)
  audio.pause()
  audio.src = ''
  st = { open: false, min: false, playing: false, elapsed: 0 }
  notify()
}

export function togglePlay() {
  if (st.playing) {
    audio.pause()
    clearInterval(iv)
    st = { ...st, playing: false, elapsed: audio.currentTime || 0 }
  } else if (audio.src) {
    audio.play().catch(() => {})
    startTick()
    st = { ...st, playing: true }
  }
  notify()
}

export function playMusicById(id, title, artist, cover) {
  // 参考桥没有 /music/url、/music-stream——只有部署声明了音乐后端才发请求
  if (!CFG.musicEnabled) return
  track = { title: title || '加载中…', artist: artist || '', dur: 0, cover: cover || '' }
  st = { open: true, min: true, playing: false, elapsed: 0 }
  notify()
  fetch(API + '/music/url?id=' + id, { headers: HEADERS })
    .then(r => r.json())
    .then(d => {
      const rawUrl = d.url || d.play_url || ''
      if (!rawUrl) {
        track.title = '无法播放'
        localStorage.removeItem(NS + '_music')
        notify()
        return
      }
      audio.src = API + '/music-stream?url=' + encodeURIComponent(rawUrl)
      audio.load()
      localStorage.setItem(NS + '_music', JSON.stringify({ id, title, artist, cover }))
      audio.addEventListener('loadedmetadata', function onMeta() {
        track.dur = audio.duration || 240
        audio.removeEventListener('loadedmetadata', onMeta)
        audio.play().catch(() => {})
        startTick()
        st = { ...st, playing: true }
        notify()
      })
      audio.addEventListener('ended', function onEnd() {
        clearInterval(iv)
        audio.removeEventListener('ended', onEnd)
        localStorage.removeItem(NS + '_music')
        st = { ...st, playing: false, elapsed: 0 }
        notify()
      })
    })
    .catch(() => {
      track.title = '加载失败'
      localStorage.removeItem(NS + '_music')
      notify()
    })
}

// 页面加载恢复——流 URL 会过期，按歌曲 ID 重取
export function restoreMusic() {
  if (!CFG.musicEnabled) return
  const saved = localStorage.getItem(NS + '_music')
  if (!saved) return
  try {
    const m = JSON.parse(saved)
    if (!m.id) { localStorage.removeItem(NS + '_music'); return }
    playMusicById(m.id, m.title, m.artist, m.cover)
  } catch (e) { localStorage.removeItem(NS + '_music') }
}
