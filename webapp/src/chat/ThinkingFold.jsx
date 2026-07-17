// 思考折叠条：assistant 消息头顶的「💭 思考」，点开按需拉全文。
// 从 config.js 覆盖层的 renderThinking 收编成 React 原生组件——
// 覆盖层直接改 React 管辖的 DOM 会在重渲染时打架（消息重复/正文被吞的根源）。
// 样式沿用 config.js 注入的 .tk-bar/.tk-body。
import { useState } from 'react'
import { API, HEADERS } from '../lib/api.js'

export default function ThinkingFold({ id }) {
  const [open, setOpen] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [text, setText] = useState('')

  function toggle(e) {
    e.stopPropagation()
    const next = !open
    setOpen(next)
    if (next && !loaded) {
      setLoaded(true)
      setText('……')
      fetch(API + '/thinking/' + encodeURIComponent(id), { headers: HEADERS })
        .then(r => { if (!r.ok) throw 0; return r.json() })
        .then(j => setText(j.thinking || '（空）'))
        .catch(() => { setText('（取不到了——大概换窗了）'); setLoaded(false) })
    }
  }

  return (
    <>
      <div className={'tk-bar' + (open ? ' open' : '')} onClick={toggle}>
        <span className="tk-arrow">▸</span><span>💭 思考</span>
      </div>
      {open && <div className="tk-body show">{text}</div>}
    </>
  )
}
