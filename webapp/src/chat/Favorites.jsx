// 收藏页：她点名的功能——任何消息都能收进来，文本/语音/音乐卡/一段对话。
// 与 History 同款覆盖页：Chat 常驻不卸载，点条目 → 广播 chat-jump 跳回原文。
// 云端(桥 /favorites)为真源，页面不留本地副本。
import { useEffect, useState } from 'react'
import { API, HEADERS, ID } from '../lib/api.js'

// 快照预览：把 wire 标记折叠成人话
export function previewOf(content) {
  let t = String(content || '')
  t = t.replace(/\[\[bond_voice:[^\]]+\]\]/g, '🎙 语音')
  t = t.replace(/\[music:\d+[:：]([^:：\]]+)[^\]]*\]/g, '♪ $1')
  t = t.replace(/\[sticker:([^\]|]+)[^\]]*\]/g, '[贴纸]')
  t = t.replace(/(?:^|\n)\[图片\]\s*\S+/g, ' [图片]')
  t = t.replace(/\s+/g, ' ').trim()
  return t.slice(0, 120)
}

export default function Favorites() {
  const [items, setItems] = useState(null)
  const [confirmDel, setConfirmDel] = useState('')

  useEffect(() => {
    fetch(API + '/favorites', { headers: HEADERS })
      .then(r => (r.ok ? r.json() : { items: [] }))
      .then(d => setItems((d.items || []).slice().reverse())) // 最新收藏在前
      .catch(() => setItems([]))
  }, [])

  function back() { window.location.hash = '' }

  function jump(id) {
    if (!id) return
    window.location.hash = ''
    window.dispatchEvent(new CustomEvent('chat-jump', { detail: id }))
  }

  function del(favId) {
    if (confirmDel !== favId) { setConfirmDel(favId); setTimeout(() => setConfirmDel(''), 2500); return }
    setConfirmDel('')
    fetch(API + '/favorites', { method: 'POST', headers: HEADERS, body: JSON.stringify({ action: 'del', id: favId }) })
      .then(r => (r.ok ? r.json() : null))
      .then(d => { if (d && d.ok) setItems((d.items || []).slice().reverse()) })
      .catch(() => {})
  }

  const who = m => (m.role === 'user' ? ID.userName : ID.aiName)

  return (
    <div className="hist-page">
      <div className="hist-hdr">
        <button className="hist-back" aria-label="back" onClick={back}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
        </button>
        <div className="fav-title">收藏</div>
      </div>

      <div className="hist-body">
        {items === null && <div className="hist-note"><span className="hist-spin-ring" /> 正在开抽屉…</div>}
        {items && items.length === 0 && (
          <div className="hist-note">还什么都没收。长按一条消息 → ✦ 收藏；长按 → ▤ 选一段，成段收。</div>
        )}
        {items && items.map(it => {
          const first = (it.messages || [])[0] || {}
          const seg = (it.messages || []).length > 1
          return (
            <div key={it.id} className="fav-item" onClick={() => jump(first.id)}>
              <div className="fav-meta">
                <span>{(first.ts || '').slice(0, 16).replace('T', ' ')} · {who(first)}{seg ? ` · 一段对话（${it.messages.length} 条）` : ''}</span>
                <span className={'fav-del' + (confirmDel === it.id ? ' fav-del--arm' : '')}
                  onClick={e => { e.stopPropagation(); del(it.id) }}>
                  {confirmDel === it.id ? '再点一下删除' : '✕'}
                </span>
              </div>
              {seg ? (
                <div className="fav-seg">
                  {it.messages.slice(0, 3).map((m, i) => (
                    <div key={i} className="fav-seg-line"><b>{who(m)}</b>：{previewOf(m.content)}</div>
                  ))}
                  {it.messages.length > 3 && <div className="fav-seg-more">…还有 {it.messages.length - 3} 条</div>}
                </div>
              ) : (
                <div className="fav-text">{previewOf(first.content)}</div>
              )}
              <div className="fav-saved">收于 {it.saved_ts || ''}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
