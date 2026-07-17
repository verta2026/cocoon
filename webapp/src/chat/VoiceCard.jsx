// 语音气泡：从 chat_v2 的 voiceCard 移植。全页共享一个常驻 <audio>——
// 同一时刻只放一条，点别的卡自动切走；组件重渲染不打断播放，进度回填。
import { useEffect, useReducer } from 'react'
import { API } from '../lib/api.js'

const audio = typeof Audio !== 'undefined' ? new Audio() : null
let curId = null
const subs = new Set()
const emit = () => subs.forEach(fn => fn())
if (audio) {
  for (const ev of ['timeupdate', 'play', 'pause', 'loadedmetadata']) audio.addEventListener(ev, emit)
  audio.addEventListener('ended', () => { curId = null; emit() })
}

const fmt = s => {
  s = Math.max(0, Math.floor(s || 0))
  return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2)
}

// 自己画的播放/暂停图标（不用 emoji，免得被系统渲染成彩色表情）
const PLAY = (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="#fff" style={{ marginLeft: 2, display: 'block' }}>
    <path d="M7 4.5v15a1 1 0 0 0 1.5.87l12-7.5a1 1 0 0 0 0-1.74l-12-7.5A1 1 0 0 0 7 4.5z" />
  </svg>
)
const PAUSE = (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="#fff" style={{ display: 'block' }}>
    <rect x="6" y="4" width="4.5" height="16" rx="1.3" /><rect x="13.5" y="4" width="4.5" height="16" rx="1.3" />
  </svg>
)

// id 是全页唯一的播放身份；src 缺省时按 TTS 语音取（/tts/audio/<id>.mp3），
// 传入 src 则播任意音频文件（她的语音输入/通话录音走 /files/）
export default function VoiceCard({ id, src }) {
  const [, force] = useReducer(x => x + 1, 0)
  useEffect(() => {
    subs.add(force)
    return () => subs.delete(force)
  }, [])

  if (!audio) return null
  const active = curId === id
  const playing = active && !audio.paused
  const hasDur = active && audio.duration && isFinite(audio.duration)
  const pct = hasDur ? (100 * audio.currentTime) / audio.duration : 0
  const left = hasDur ? fmt(audio.duration - audio.currentTime) : '0:00'

  function toggle(e) {
    e.stopPropagation()
    if (active && !audio.paused) { audio.pause(); return }
    if (!active) { curId = id; audio.src = src || (API + '/tts/audio/' + encodeURIComponent(id) + '.mp3') }
    audio.play().catch(() => {})
  }

  return (
    <div className="voice-card" onClick={toggle}>
      <div className="voice-btn">{playing ? PAUSE : PLAY}</div>
      <div className="voice-track"><div className="voice-fill" style={{ width: pct + '%' }} /></div>
      <span className="voice-time">{left}</span>
    </div>
  )
}
