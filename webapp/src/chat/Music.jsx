// 音乐迷你条 + 全屏面板，视觉从 chat.html renderMusicMini/music full 移植。
import { useSyncExternalStore } from 'react'
import { subscribe, getMusic, liveTime, togglePlay, minimize, expand, closeMusic } from '../lib/music.js'
import { cssUrl } from './Bubble.jsx'
import { ID } from '../lib/api.js'

const fmtT = s => { s = Math.floor(s); return Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2) }

export default function Music() {
  const m = useSyncExternalStore(subscribe, getMusic)
  if (!m.open) return null
  const live = liveTime()
  const pct = m.track.dur ? Math.round(live / m.track.dur * 100) : 0

  if (m.min) {
    return (
      <div className="mm-bar" id="music-mini">
        <span className="mm-note">♫</span>
        <div className="mm-info" onClick={expand}>
          <div className="mm-title">{m.track.title}</div>
          <div className="mm-track"><div className="mm-prog" style={{ width: pct + '%' }} /></div>
        </div>
        <span className="mm-play" onClick={togglePlay}>{m.playing ? '❚❚' : '▶'}</span>
        <span className="mm-close" onClick={closeMusic}>✕</span>
      </div>
    )
  }

  return (
    <div className="mp-ov" onClick={minimize}>
      <div className="mp-panel" onClick={e => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="mp-cover" style={m.track.cover ? { backgroundImage: cssUrl(m.track.cover), backgroundSize: 'cover' } : undefined}>
          {m.track.cover ? '' : '♪'}
        </div>
        <div className="mp-info">
          <div className="mp-title">{m.track.title}</div>
          <div className="mp-artist">{m.track.artist}</div>
        </div>
        <div className="mp-progress">
          <div className="mp-track"><div className="mp-prog" style={{ width: pct + '%' }} /></div>
          <div className="mp-times"><span>{fmtT(live)}</span><span>{fmtT(m.track.dur)}</span></div>
        </div>
        <div className="mp-ctrl">
          <span className="mp-skip">⏮</span>
          <span className="mp-playbtn" onClick={togglePlay}>{m.playing ? '❚❚' : '▶'}</span>
          <span className="mp-skip">⏭</span>
        </div>
        <div className="mp-links">
          <span className="mp-shrink" onClick={minimize}>缩小</span>
          <span className="mp-quit" onClick={closeMusic}>关闭</span>
        </div>
        <div className="mp-hint">和{ID.aiName}一起听 · 待接入播放源</div>
      </div>
    </div>
  )
}
