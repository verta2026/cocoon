// 语音气泡：波形条样式，从旧覆盖层原样收编进 React。
// 全页共享一个常驻 <audio>——同一时刻只放一条，点别的卡自动切走；
// 组件重渲染不打断播放，进度画在波形条上。长按=转文字（STT），短按=播放。
import { useEffect, useReducer, useRef, useState } from 'react'
import { API, TOKEN } from '../lib/api.js'

const audio = typeof Audio !== 'undefined' ? new Audio() : null
let curId = null
const subs = new Set()
const emit = () => subs.forEach(fn => fn())
if (audio) {
  for (const ev of ['timeupdate', 'play', 'pause', 'loadedmetadata']) audio.addEventListener(ev, emit)
  audio.addEventListener('ended', () => { curId = null; emit() })
}

const fmt = s => {
  s = Math.max(0, Math.round(s || 0))
  return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2)
}

// 波形条高度：从 id 出确定性伪随机——React 每次音频事件都重渲染，
// 真随机会让波形每秒抖动
function barsFor(id, dur) {
  const n = Math.max(8, Math.min(24, Math.round((dur || 4) * 3)))
  let h = 2166136261
  const s = String(id)
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) }
  const out = []
  for (let i = 0; i < n; i++) {
    h = Math.imul(h ^ (h >>> 15), 2246822507); h ^= h >>> 13
    out.push(6 + ((h >>> 0) % 1000) / 1000 * 14)
  }
  return out
}

// 自己画的播放/暂停图标（不用 emoji，免得被系统渲染成彩色表情）
const PLAY = (
  <svg viewBox="0 0 24 24" fill="#fff" style={{ width: 14, height: 14, marginLeft: 2, display: 'block' }}>
    <path d="M7 4.5v15a1 1 0 0 0 1.5.87l12-7.5a1 1 0 0 0 0-1.74l-12-7.5A1 1 0 0 0 7 4.5z" />
  </svg>
)
const PAUSE = (
  <svg viewBox="0 0 24 24" fill="#fff" style={{ width: 13, height: 13, display: 'block' }}>
    <rect x="6" y="4" width="4.5" height="16" rx="1.3" /><rect x="13.5" y="4" width="4.5" height="16" rx="1.3" />
  </svg>
)

// id 是全页唯一的播放身份；src 缺省时按 TTS 语音取（/tts/audio/<id>.mp3），
// 传入 src 则播任意音频文件（她的语音输入/通话录音走 /files/）。
// hasCaption=true 时长按不再 STT（正文就是转文字，折叠在 Bubble 层管）
export default function VoiceCard({ id, src, dur, hasCaption }) {
  const [, force] = useReducer(x => x + 1, 0)
  const [stt, setStt] = useState('')
  const [sttBusy, setSttBusy] = useState(false)
  const press = useRef(null)
  const bars = useRef(null)
  if (!bars.current) bars.current = barsFor(id, dur)
  useEffect(() => {
    subs.add(force)
    return () => subs.delete(force)
  }, [])

  if (!audio) return null
  const active = curId === id
  const playing = active && !audio.paused
  const metaDur = active && audio.duration && isFinite(audio.duration) ? audio.duration : 0
  const total = metaDur || dur || 0
  const pct = active && total ? audio.currentTime / total : 0
  const url = src || (API + '/tts/audio/' + encodeURIComponent(id) + '.mp3')

  function toggle() {
    if (active && !audio.paused) { audio.pause(); return }
    if (!active) { curId = id; audio.src = url }
    audio.play().catch(() => {})
    emit()
  }

  function transcribe() {
    if (stt || sttBusy) return
    setSttBusy(true)
    fetch(url)
      .then(r => { if (!r.ok) throw 0; return r.blob() })
      .then(blob => {
        const fd = new FormData()
        fd.append('audio', blob, 'voice.webm')
        return fetch(API + '/api/call/transcribe', {
          method: 'POST', headers: { Authorization: 'Bearer ' + TOKEN }, body: fd,
        })
      })
      .then(r => r.json())
      .then(j => setStt((j.text || '').trim() || '（没听出字来）'))
      .catch(() => setStt('（音频取不到，转不了）'))
      .finally(() => setSttBusy(false))
  }

  // 长按500ms转文字，短按播放。pointer 事件不往上冒——
  // 免得 Bubble 的长按菜单跟着一起弹
  function down(e) {
    e.stopPropagation()
    clearTimeout(press.current)
    press.current = setTimeout(() => {
      press.current = 'long'
      if (!hasCaption) transcribe()
    }, 500)
  }
  function up(e) {
    e.stopPropagation()
    if (press.current !== 'long') { clearTimeout(press.current); toggle() }
    press.current = null
  }

  const n = bars.current.length
  return (
    <div className="vm-wrap">
      <div className="vm-bubble"
        onPointerDown={down} onPointerUp={up}
        onPointerLeave={() => { if (press.current !== 'long') clearTimeout(press.current); press.current = null }}
        onClick={e => e.stopPropagation()}
        onContextMenu={e => e.preventDefault()}>
        <div className="vm-play">{playing ? PAUSE : PLAY}</div>
        <div className="vm-bars">
          {bars.current.map((h, i) => (
            <span key={i} className={pct > 0 && i < n * pct ? 'on' : ''} style={{ height: h + 'px' }} />
          ))}
        </div>
        <span className="vm-dur">{fmt(active && audio.currentTime ? total - audio.currentTime : total)}</span>
      </div>
      {sttBusy && <div className="vm-loading">转文字中...</div>}
      {stt && <div className="vm-text">{stt}</div>}
    </div>
  )
}
