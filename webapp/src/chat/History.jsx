// history 页：按月折叠的聊天档案 + 全文检索。
// 覆盖在 Chat 上层（Chat 不卸载），点记录 → 关闭自己 → 广播 chat-jump，
// Chat 跳进以那条消息为中心的档案窗口。染色变量由 Chat 的取色管线全局供给。
import { useEffect, useRef, useState } from 'react'
import { API, HEADERS } from '../lib/api.js'
import { channelWho } from './parseMessage.js'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

function dayLabel(date) {
  const d = new Date(date + 'T00:00:00')
  if (isNaN(d)) return date
  return `${d.getMonth() + 1}月${d.getDate()}日 · 周${WEEKDAYS[d.getDay()]}`
}

function monthLabel(month) {
  const [y, m] = month.split('-')
  return `${y}年${Number(m)}月`
}

export default function History() {
  const [months, setMonths] = useState(null)   // null=加载中
  const [unavailable, setUnavailable] = useState(false)
  const [open, setOpen] = useState({})
  const [q, setQ] = useState('')
  const [results, setResults] = useState(null) // null=不在检索态
  const [searching, setSearching] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    fetch(API + '/chat_history_months', { headers: HEADERS })
      .then(r => {
        if (!r.ok) throw new Error(r.status)
        return r.json()
      })
      .then(d => {
        const ms = d.months || []
        setMonths(ms)
        if (ms.length) setOpen({ [ms[0].month]: true })
      })
      .catch(() => setUnavailable(true))
  }, [])

  function back() {
    window.location.hash = ''
  }

  function jump(id) {
    window.location.hash = ''
    window.dispatchEvent(new CustomEvent('chat-jump', { detail: id }))
  }

  function doSearch() {
    const query = q.trim()
    if (!query) { setResults(null); return }
    setSearching(true)
    fetch(API + '/chat_history_search?q=' + encodeURIComponent(query) + '&limit=120', { headers: HEADERS })
      .then(r => (r.ok ? r.json() : { results: [] }))
      .then(d => setResults(d.results || []))
      .catch(() => setResults([]))
      .finally(() => setSearching(false))
  }

  return (
    <div className="hist-page">
      <div className="hist-hdr">
        <button className="hist-back" aria-label="back" onClick={back}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
        </button>
        <input ref={inputRef} className="hist-search" placeholder="搜聊天记录…" value={q}
          onChange={e => { setQ(e.target.value); if (!e.target.value.trim()) setResults(null) }}
          onKeyDown={e => { if (e.key === 'Enter') doSearch() }} />
        <button className="hist-search-btn" aria-label="search" onClick={doSearch}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><line x1="21" y1="21" x2="16.5" y2="16.5" /></svg>
        </button>
      </div>

      <div className="hist-body">
        {unavailable && (
          <div className="hist-note">档案索引还没上线，桥重启后就有了</div>
        )}
        {!unavailable && months === null && (
          <div className="hist-note"><span className="hist-spin-ring" /> 正在翻档案…</div>
        )}

        {searching && <div className="hist-note"><span className="hist-spin-ring" /> 搜索中…</div>}
        {results !== null && !searching && (
          <div className="hist-results">
            <div className="hist-results-head">
              {results.length ? `${results.length} 条结果` : '没搜到，换个词试试'}
              <span className="hist-results-clear" onClick={() => { setResults(null); setQ('') }}>清除</span>
            </div>
            {results.map(r => (
              <div key={r.id} className="hist-hit" onClick={() => jump(r.id)}>
                <div className="hist-hit-meta">{r.date} · {r.role === 'user' ? '你' : (channelWho(r) || '我')}</div>
                <div className="hist-hit-text">{r.snippet}</div>
              </div>
            ))}
          </div>
        )}

        {results === null && months && months.map(mo => (
          <div key={mo.month} className="hist-month">
            <div className="hist-month-head" onClick={() => setOpen(prev => ({ ...prev, [mo.month]: !prev[mo.month] }))}>
              <span className={'hist-fold-arrow' + (open[mo.month] ? ' hist-fold-arrow--open' : '')}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 6 15 12 9 18" /></svg>
              </span>
              <span className="hist-month-name">{monthLabel(mo.month)}</span>
              <span className="hist-month-count">{mo.count} 条</span>
            </div>
            {open[mo.month] && mo.days.map(d => (
              <div key={d.date} className="hist-day" onClick={() => jump(d.first_id)}>
                <div className="hist-day-top">
                  <span className="hist-day-date">{dayLabel(d.date)}</span>
                  <span className="hist-day-count">{d.count}</span>
                </div>
                {d.preview && <div className="hist-day-preview">{d.preview}</div>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
