// 消息富文本渲染管线，从 frontend/chat.html 的 vanilla 版同源移植。
// 方言与判定正则一字未动：代码围栏 → 表格/盒线表 → 块级 markdown → 行内。
// 输出 React 元素（无 dangerouslySetInnerHTML）：文本一律走默认转义。
import { useState } from 'react'
import './rich.css'

let keySeq = 0
const k = () => 'r' + keySeq++

export function inlineRich(s) {
  const out = []
  const re = /`([^`]+)`|\*\*([^*]+)\*\*|\{#([0-9a-fA-F]{3,8})\|([^}]*)\}|\{rainbow\|([^}]*)\}|==([^=]+)==|~~([^~\n]+)~~|\[([^\]\n]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]*)\)|\*([^*\n]+)\*/g
  let last = 0
  let mt
  while ((mt = re.exec(s))) {
    if (mt.index > last) out.push(...textWithBreaks(s.slice(last, mt.index)))
    if (mt[1] != null) out.push(<code key={k()} className="rc-code">{mt[1]}</code>)
    else if (mt[2] != null) out.push(<strong key={k()} className="rc-b">{mt[2]}</strong>)
    else if (mt[3] != null) out.push(<span key={k()} style={{ color: '#' + mt[3] }}>{mt[4]}</span>)
    else if (mt[5] != null) out.push(<span key={k()} className="rc-rainbow">{mt[5]}</span>)
    else if (mt[6] != null) out.push(<mark key={k()} className="rc-mark">{mt[6]}</mark>)
    else if (mt[7] != null) out.push(<del key={k()} className="rc-del">{mt[7]}</del>)
    else if (mt[8] != null)
      out.push(<a key={k()} className="rc-a" href={mt[9]} target="_blank" rel="noopener">{mt[8]}</a>)
    else if (mt[10] != null) out.push(<em key={k()} className="rc-em">{mt[10]}</em>)
    last = re.lastIndex
  }
  if (last < s.length) out.push(...textWithBreaks(s.slice(last)))
  return out
}

function textWithBreaks(text) {
  const out = []
  const paras = text.split(/\n\n+/)
  for (let i = 0; i < paras.length; i++) {
    if (i > 0) out.push(<div key={k()} className="rc-spacer" />)
    if (paras[i]) out.push(paras[i])
  }
  return out
}

function TableBlock({ block }) {
  const rows = block.split('\n').filter(r => r.trim())
  const isSep = r => /^\|[\s:|-]+\|$/.test(r.trim())
  const parseRow = r => r.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim())
  let headerDone = false
  const trs = []
  for (let ri = 0; ri < rows.length; ri++) {
    if (isSep(rows[ri])) { headerDone = true; continue }
    const cells = parseRow(rows[ri])
    const isTh = !headerDone && ri === 0
    trs.push(
      <tr key={ri}>
        {cells.map((c, ci) =>
          isTh
            ? <th key={ci} className="rc-cell rc-th">{inlineRich(c)}</th>
            : <td key={ci} className="rc-cell">{inlineRich(c)}</td>)}
      </tr>,
    )
    if (isTh) headerDone = true
  }
  return (
    <div className="rc-table-scroll">
      <table className="rc-table"><tbody>{trs}</tbody></table>
    </div>
  )
}

const COPY_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="9" y="9" width="13" height="13" rx="2" /><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
)
const CHECK_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#5b8a72" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

function CodeFence({ code }) {
  // 复制条：另起一行、右下角，点击变绿勾（chat_v2 同款）。
  // 手势全部截断：横滑代码块不能误触发滑动引用/长按菜单
  const [copied, setCopied] = useState(false)
  const stop = e => e.stopPropagation()
  return (
    <div className="rc-fence-wrap"
      onPointerDown={stop} onPointerMove={stop} onPointerUp={stop}
      onTouchStart={stop} onTouchMove={stop} onClick={stop}>
      <pre className="rc-fence">{code}</pre>
      <div className="rc-fence-bar">
        <span className="rc-fence-copy" onClick={e => {
          e.stopPropagation()
          try {
            navigator.clipboard.writeText(code).then(() => {
              setCopied(true)
              setTimeout(() => setCopied(false), 1400)
            }, () => {})
          } catch (err) {}
        }}>{copied ? CHECK_ICON : COPY_ICON}</span>
      </div>
    </div>
  )
}

function BoxTableBlock({ block }) {
  // 阻断手势冒泡：横滑盒线表不能误触滑动引用（与代码块同款处理）
  const stop = e => e.stopPropagation()
  return (
    <pre
      className="rc-boxtable"
      onPointerDown={stop} onPointerMove={stop} onPointerUp={stop}
      onTouchStart={stop} onTouchMove={stop}
    >{block}</pre>
  )
}

export function blockRich(text) {
  const out = []
  const lines = text.split('\n')
  let plain = []
  const flushPlain = () => {
    if (plain.length) { out.push(...inlineRich(plain.join('\n'))); plain = [] }
  }
  for (const ln of lines) {
    let m
    if ((m = ln.match(/^(#{1,3})\s+(.+)$/))) {
      flushPlain()
      out.push(<span key={k()} className={'rc-h rc-h' + m[1].length}>{inlineRich(m[2])}</span>)
    } else if ((m = ln.match(/^>\s?(.*)$/))) {
      flushPlain()
      out.push(<span key={k()} className="rc-bq">{inlineRich(m[1])}</span>)
    } else if (/^(?:---+|\*\*\*+|___+)\s*$/.test(ln)) {
      flushPlain()
      out.push(<span key={k()} className="rc-hr" />)
    } else if ((m = ln.match(/^[-•]\s+(.+)$/))) {
      flushPlain()
      out.push(<span key={k()} className="rc-li">{'• '}{inlineRich(m[1])}</span>)
    } else if ((m = ln.match(/^(\d+)[.)]\s+(.+)$/))) {
      flushPlain()
      out.push(<span key={k()} className="rc-li">{m[1] + '. '}{inlineRich(m[2])}</span>)
    } else {
      plain.push(ln)
    }
  }
  flushPlain()
  return out
}

function richWithTables(text) {
  const out = []
  const re = /(?:^|\n)(\|[^\n]+\|(?:\n\|[\s:|-]+\|)(?:\n\|[^\n]+\|)+|[┌┬┐├┼┤└┴┘│][^\n]*(?:\n[┌┬┐├┼┤└┴┘│][^\n]*)+)/g
  let last = 0
  let mt
  let found = false
  while ((mt = re.exec(text))) {
    found = true
    if (mt.index > last) out.push(...blockRich(text.slice(last, mt.index)))
    const block = mt[1]
    out.push(block.charAt(0) === '|'
      ? <TableBlock key={k()} block={block} />
      : <BoxTableBlock key={k()} block={block} />)
    last = re.lastIndex
  }
  if (!found) return blockRich(text)
  if (last < text.length) out.push(...blockRich(text.slice(last)))
  return out
}

export default function Rich({ text }) {
  keySeq = 0
  const out = []
  const parts = String(text).split(/```(\w*)\n?([\s\S]*?)```/)
  for (let i = 0; i < parts.length; i += 3) {
    if (parts[i]) out.push(...richWithTables(parts[i]))
    if (i + 2 < parts.length) out.push(<CodeFence key={k()} code={parts[i + 2]} />)
  }
  return <>{out}</>
}
