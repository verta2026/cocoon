// 单条消息行，视觉与 chat.html renderMessages 逐项对齐。
// 手势(长按菜单/左滑引用)、反应、失败重试、时间戳+复制已接。
// 本批未接：doc 模式排版、贴纸选择器、音乐播放(卡片仅展示)。
import { memo, useEffect, useRef, useState } from 'react'
import Rich from '../lib/rich.jsx'
import { parseMessage } from './parseMessage.js'
import { API, ID, NS, AI_KEY, TOKEN } from '../lib/api.js'
import { playMusicById } from '../lib/music.js'
import VoiceCard from './VoiceCard.jsx'
import ThinkingFold from './ThinkingFold.jsx'

export function cssUrl(u) {
  return 'url("' + String(u == null ? '' : u).replace(/["'()\\]/g, '') + '")'
}

// 语音原文（说这条语音时的文字）：桥 /tts/text/<id> 按需拉，模块级缓存。
// 有原文时它才是转文字；语音标记后面跟着的正文是正文，不再被当成转文字顶掉
const vtCache = new Map()
function useVoiceText(id) {
  const [text, setText] = useState(() => (id && vtCache.get(id)) || '')
  useEffect(() => {
    if (!id) return
    if (vtCache.has(id)) { setText(vtCache.get(id)); return }
    let on = true
    fetch(API + '/tts/text/' + encodeURIComponent(id), { headers: { Authorization: 'Bearer ' + TOKEN } })
      .then(r => (r.ok ? r.json() : { text: '' }))
      .then(j => {
        const t = (j.text || '').trim()
        vtCache.set(id, t)
        if (on) setText(t)
      })
      .catch(() => { if (on) setText('') })
    return () => { on = false }
  }, [id])
  return text
}

const normText = s => String(s || '').replace(/\s+/g, ' ').trim()

// 语音消息的随行文字＝转文字：默认展开，点一下折叠成"▸ 转文字"小条（旧覆盖层同款）
function VoiceCaption({ body }) {
  const [folded, setFolded] = useState(false)
  if (folded) {
    return <div className="vm-cap-chip" onClick={e => { e.stopPropagation(); setFolded(false) }}>▸ 转文字</div>
  }
  return (
    <div className="vm-text vm-text--cap" onClick={e => { e.stopPropagation(); setFolded(true) }}>
      <Rich text={body} />
    </div>
  )
}

function Bubble({ m, grouped, mode, avatars, expanded, copied, reacts, selMode, selOn, onSelToggle, onToggle, onOpenMenu, onQuote, onLightbox, onRetry, onReact, onCopy, onTextView }) {
  const p = parseMessage(m)
  const rowRef = useRef(null)
  const g = useRef({ lpT: 0, lpFired: false, x: 0, y: 0, swiping: false, swipeTriggered: false, icon: null })

  if (p.kind === 'system') {
    return <div className="cb-sys">{m.content}</div>
  }

  const vText = useVoiceText(p.voiceId)

  // 新到的音乐卡自动开播（原版 isNew && !me 行为）
  useEffect(() => {
    if (p.music && m._fresh && !p.me) {
      const t = setTimeout(() => playMusicById(p.music.id, p.music.title, p.music.artist, p.music.cover), 300)
      return () => clearTimeout(t)
    }
  }, [])

  const cm = mode === 'doc'
  const doc = cm && !p.me && p.kind === 'assistant'
  const rad = p.tgOn ? '16px' : doc ? '0' : p.me ? (cm ? '22px' : '18px 18px 5px 18px') : '18px 18px 18px 5px'
  const rowMax = p.tgOn ? 'min(90%,760px)' : doc ? '100%' : cm ? '85%' : 'min(90%,800px)'
  const nImg = p.attImgs.length
  const rl = reacts || []

  // 手势逻辑从 chat.html 原样移植：480ms 长按开菜单，左滑 48px 触发引用
  function onPointerDown(e) {
    if (selMode) return
    const s = g.current
    s.x = e.clientX; s.y = e.clientY; s.lpFired = false
    s.swiping = false; s.swipeTriggered = false
    clearTimeout(s.lpT)
    s.lpT = setTimeout(() => { s.lpFired = true; onOpenMenu(m, s.x, s.y) }, 480)
  }
  function settleBack(fast) {
    const s = g.current
    const row = rowRef.current
    if (!row) return
    row.style.transition = fast ? 'transform 0.2s ease' : 'transform 0.25s cubic-bezier(0.2,0.9,0.3,1)'
    row.style.transform = ''
    const icon = s.icon
    if (icon) {
      icon.style.transition = 'opacity 0.2s'
      icon.style.opacity = '0'
      setTimeout(() => { if (icon.parentNode) icon.parentNode.removeChild(icon) }, 200)
      s.icon = null
    }
    setTimeout(() => { if (row) row.style.transition = '' }, 260)
    s.swiping = false
  }
  function onPointerUp() {
    const s = g.current
    clearTimeout(s.lpT)
    if (s.swiping) settleBack(false)
  }
  function onPointerCancel() {
    const s = g.current
    clearTimeout(s.lpT)
    if (s.swiping) settleBack(true)
  }
  function onPointerMove(e) {
    const s = g.current
    const row = rowRef.current
    const dx = e.clientX - s.x
    const dy = e.clientY - s.y
    if (Math.abs(dx) + Math.abs(dy) > 8) clearTimeout(s.lpT)
    if (s.lpFired || s.swipeTriggered) return
    if (!s.swiping && dx < -6 && Math.abs(dx) > Math.abs(dy) + 4) {
      s.swiping = true
      e.currentTarget.setPointerCapture(e.pointerId)
    }
    if (s.swiping && row) {
      let move = Math.max(dx, -72)
      if (move > 0) move = 0
      row.style.transform = 'translateX(' + move + 'px)'
      if (!s.icon) {
        const icon = document.createElement('div')
        icon.className = 'cb-reply-icon'
        icon.textContent = '↩'
        row.style.position = 'relative'
        row.appendChild(icon)
        s.icon = icon
      }
      const progress = Math.min(Math.abs(move) / 48, 1)
      s.icon.style.opacity = String(progress)
      s.icon.style.transform = 'translateY(-50%) scale(' + (0.6 + progress * 0.4) + ')'
      if (move <= -48 && !s.swipeTriggered) {
        s.swipeTriggered = true
        s.lpFired = true
        if (navigator.vibrate) navigator.vibrate(15)
        onQuote(m)
      }
    }
  }
  function onBubClick() {
    if (selMode) return // 选择模式：cb-col 已 pointer-events:none，点击由行级 onClick 统一接
    if (g.current.lpFired) { g.current.lpFired = false; return }
    // 双击 → 全屏选字页；第二下也过 onToggle，展开态转一圈回原位不留痕
    const now = Date.now()
    if (now - (g.current.dtT || 0) < 320) {
      g.current.dtT = 0
      onToggle()
      if (p.body && onTextView) onTextView(p.body)
      return
    }
    g.current.dtT = now
    onToggle()
  }
  function onCtx(e) {
    e.preventDefault()
    if (selMode) return
    clearTimeout(g.current.lpT)
    onOpenMenu(m, e.clientX, e.clientY)
  }

  return (
    <div ref={rowRef} data-mid={m.id}
      onClick={selMode ? () => onSelToggle(m.id) : undefined}
      className={'cb-row ' + (p.me ? 'cb-row--me msg--user' : 'msg--assistant') + (selMode ? ' cb-row--sel' : '') + (selOn ? ' cb-row--sel-on' : '')}
      style={{
        maxWidth: rowMax, width: doc ? '100%' : 'auto',
        // 新到的消息才渐入；历史水合不动（chat_v2 isNew 同款语义）。
        // 不用 both：fill-forwards 的最终帧 transform 会永久压住左滑的行内 translateX
        animation: m._fresh ? 'msg-in .3s ease' : undefined,
      }}>
      {!(cm || (p.tgOn && p.groupOther)) && (
        <div className="cb-avatar"
          style={{
            background: p.groupOther ? p.senderColor : 'var(--c-border)',
            color: p.groupOther ? '#fff' : 'var(--c-muted)',
            visibility: grouped ? 'hidden' : 'visible',
          }}>
          {p.groupOther ? (p.tgWho ? p.tgWho.slice(0, 1) : '·') : (p.me ? ID.userName : ID.aiName).slice(0, 1)}
          {!p.groupOther && (
            <div className="cb-avatar-img" style={{ backgroundImage: cssUrl(p.me ? avatars.user : avatars.ai) }} />
          )}
        </div>
      )}
      <div className="cb-col" style={{ alignItems: p.me ? 'flex-end' : 'flex-start' }}>
        {p.tgOn && <div className="cb-tg-badge">{p.tgText}</div>}

        {nImg > 0 && (
          <div className="cb-att-imgs">
            {p.attImgs.map((a, i) => (
              <div key={i} className="cb-att-img"
                onClick={e => { e.stopPropagation(); onLightbox(a.src) }}
                style={{
                  flex: '1 1 ' + (nImg === 1 ? '100%' : 'calc(50% - 1px)'),
                  height: nImg === 1 ? '160px' : nImg <= 4 ? '110px' : '86px',
                  backgroundImage: cssUrl(a.src || ''),
                }} />
            ))}
          </div>
        )}

        {p.attFiles.map((a, i) => (
          <div key={i} className="cb-att-file"
            onClick={e => {
              e.stopPropagation()
              if (!a.src) return
              const dl = document.createElement('a')
              dl.href = a.src
              dl.download = a.name || 'file'
              document.body.appendChild(dl)
              dl.click()
              dl.remove()
            }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--c-muted)" strokeWidth="1.6" style={{ flexShrink: 0 }}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            <span className="cb-att-file-name">{a.name || '文件'}</span>
          </div>
        ))}

        {p.call && (
          <div className={'cb-call' + (p.call.type === 'missed' ? ' cb-call--missed' : '')}>
            <svg className="cb-call-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              {p.call.type === 'missed' ? (
                <><path d="M10.68 13.31a16 16 0 0 0 3.41 2.6l1.27-1.27a2 2 0 0 1 2.11-.45c.9.33 1.85.53 2.81.7A2 2 0 0 1 22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6A19.79 19.79 0 0 1 2.12 4.11 2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.17.96.37 1.91.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91" /><line x1="23" y1="1" x2="17" y2="7" /><line x1="17" y1="1" x2="23" y2="7" /></>
              ) : (
                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
              )}
            </svg>
            <div className="cb-call-info">
              <div className="cb-call-label">{p.call.type === 'dial' ? '语音通话' : p.call.type === 'missed' ? '未接来电' : '通话结束'}</div>
              <div className="cb-call-reason">{p.call.type === 'ended' ? '通话时长 ' + p.call.reason : p.call.reason}</div>
            </div>
          </div>
        )}

        {p.music && (
          <div className="cb-music" onClick={e => { e.stopPropagation(); playMusicById(p.music.id, p.music.title, p.music.artist, p.music.cover) }}>
            <div className="cb-music-cover"
              style={p.music.cover ? { backgroundImage: cssUrl(p.music.cover), backgroundSize: 'cover' } : undefined}>
              {p.music.cover ? '' : '♪'}
            </div>
            <div className="cb-music-info">
              <div className="cb-music-title">{p.music.title || ''}</div>
              <div className="cb-music-artist">{p.music.artist || ''}</div>
            </div>
            <div className="cb-music-play"><span>▶</span></div>
          </div>
        )}

        {(p.body || p.quote || p.img || p.stickerFile || p.voiceId || p.fileVoice || p.thinkingId) && (
          <div
            className={'cb-bub' + (p.me ? ' cb-bub--me' : ' assistant-msg') + (p.tgOn ? ' cb-bub--tg' : '') + (p.pureSticker || p.pureVoice ? ' cb-bub--sticker' : '') + (doc ? ' cb-bub--doc' : '') + (cm ? ' cb-bub--cm' : '')}
            style={{ borderRadius: rad }}
            onClick={onBubClick}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerCancel}
            onContextMenu={onCtx}>
            {p.thinkingId && <ThinkingFold id={p.thinkingId} />}
            {p.quote && <div className="cb-quote">{p.quote}</div>}
            {p.img && (
              <div className="cb-inline-img" style={{ backgroundImage: cssUrl(p.img) }}
                onClick={e => { e.stopPropagation(); onLightbox(p.img) }} />
            )}
            {p.stickerFile && (
              <img className="cb-sticker" alt="sticker" draggable={false}
                src={API + '/stickers/' + p.stickerFile} />
            )}
            {p.voiceId && <VoiceCard id={p.voiceId} hasCaption={!!(vText || p.body)} />}
            {p.fileVoice && <VoiceCard id={'file:' + p.fileVoice.file} src={API + '/files/' + encodeURIComponent(p.fileVoice.file)} dur={p.fileVoice.dur} hasCaption={!!p.body} />}
            {p.voiceId && vText ? (
              <>
                <VoiceCaption body={vText} />
                {p.body && normText(p.body) !== normText(vText) && (
                  <span className="cb-text"><Rich text={p.body} /></span>
                )}
              </>
            ) : p.body && (p.voiceId || p.fileVoice
              ? <VoiceCaption body={p.body} />
              : <span className="cb-text"><Rich text={p.body} /></span>)}
          </div>
        )}

        {rl.length > 0 && (
          <div className="cb-reacts">
            {rl.map((r, i) => {
              const emoji = typeof r === 'string' ? r : r.emoji
              const from = typeof r === 'string' ? ID.userId : (r.from || ID.userId)
              return (
                <span key={i} className={'cb-react-pill' + (from === AI_KEY ? ' cb-react-pill--ai' : '')}
                  onClick={e => { e.stopPropagation(); onReact(m.id, emoji, m.content) }}>
                  {emoji}
                </span>
              )
            })}
          </div>
        )}

        {m.failed && (
          <div className="cb-failed" onClick={() => onRetry(m)}>
            <span className="cb-failed-icon">!</span> 发送失败，点击重试
          </div>
        )}

        {(expanded || doc) && (
          <div className="cb-ts" style={{ justifyContent: p.me ? 'flex-end' : 'flex-start' }}>
            {(m.ts || '').slice(11, 16)}
            <span className="cb-copy" onClick={e => { e.stopPropagation(); onCopy(m) }}>
              {copied ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#5b8a72" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
              ) : (
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" /></svg>
              )}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

// 记忆化：列表级 re-render（打字、轮询、开菜单）时没变的气泡整个跳过。
// 回调 props 故意不比——它们语义稳定（setState/refs），身份每轮都新。
export default memo(Bubble, (a, b) =>
  a.m === b.m && a.grouped === b.grouped && a.mode === b.mode
  && a.avatars === b.avatars // useMemo 身份：换头像 bump lookVer 时全体重画
  && a.expanded === b.expanded && a.copied === b.copied
  && a.selMode === b.selMode && a.selOn === b.selOn
  && JSON.stringify(a.reacts || null) === JSON.stringify(b.reacts || null))
