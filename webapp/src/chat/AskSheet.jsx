// AskUserQuestion 弹窗：主窗里 Claude Code 的选择题渲染成底部抽屉。
// 单选点了就记，多选勾完按确定；每题都有"自定义回答"走 Other 行；
// 全部答完一次性 POST，桥在终端里替她敲键。TUI 驱动失败或不想选时
// "改用打字回答"发 Esc 弃题，永远有退路。
import { useState } from 'react'
import { answerAsk, escapeAsk } from '../lib/api.js'

export default function AskSheet({ ask, onClose, onMinimize }) {
  const questions = ask.questions || []
  const [step, setStep] = useState(0)
  const [answers, setAnswers] = useState(() => questions.map(() => null))
  const [otherOn, setOtherOn] = useState(false)
  const [otherText, setOtherText] = useState('')
  const [multiSel, setMultiSel] = useState({})
  const [sending, setSending] = useState(false)
  const [failed, setFailed] = useState(false)

  const q = questions[step]
  if (!q) return null
  const opts = q.options || []
  const last = step === questions.length - 1

  const advance = list => {
    setOtherOn(false)
    setOtherText('')
    setMultiSel({})
    if (!last) { setAnswers(list); setStep(step + 1); return }
    submit(list)
  }

  const submit = async list => {
    setSending(true)
    setFailed(false)
    const r = await answerAsk(ask.id, list).catch(() => ({ ok: false }))
    setSending(false)
    if (r && r.ok) { onClose(true); return }
    setFailed(true)
  }

  const pick = i => {
    if (sending) return
    const list = answers.slice()
    list[step] = { index: i }
    advance(list)
  }

  const confirmMulti = () => {
    const idxs = Object.keys(multiSel).filter(k => multiSel[k]).map(Number)
    if (!idxs.length || sending) return
    const list = answers.slice()
    list[step] = { indexes: idxs }
    advance(list)
  }

  const confirmOther = () => {
    const t = otherText.trim()
    if (!t || sending) return
    const list = answers.slice()
    list[step] = { other: t }
    advance(list)
  }

  return (
    <div className="sheet-ov" onClick={() => onMinimize()}>
      <div className="sheet sheet--ask" onClick={e => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="sheet-head">
          <span className="sheet-title">
            {q.header ? <span className="ask-chip">{q.header}</span> : null}
            {questions.length > 1 ? `第 ${step + 1}/${questions.length} 题` : '在等你选'}
          </span>
          <span className="sheet-close" onClick={() => onMinimize()}>—</span>
        </div>
        <div className="ask-q">{q.question}</div>
        <div className="ask-opts">
          {opts.map((o, i) => (
            <div key={i}
              className={'ask-opt' + (q.multiSelect && multiSel[i] ? ' ask-opt--on' : '')}
              onClick={() => (q.multiSelect ? setMultiSel(s => ({ ...s, [i]: !s[i] })) : pick(i))}>
              {q.multiSelect && <span className="ask-check">{multiSel[i] ? '✓' : ''}</span>}
              <div className="ask-opt-body">
                <div className="ask-opt-label">{o.label}</div>
                {o.description ? <div className="ask-opt-desc">{o.description}</div> : null}
              </div>
            </div>
          ))}
          {otherOn ? (
            <div className="ask-other">
              <textarea className="ask-other-input" rows={2} autoFocus value={otherText}
                placeholder="想怎么答就怎么写" onChange={e => setOtherText(e.target.value)} />
              <button className="ask-btn" disabled={!otherText.trim() || sending} onClick={confirmOther}>就这么答</button>
            </div>
          ) : (
            <div className="ask-opt ask-opt--other" onClick={() => setOtherOn(true)}>
              <div className="ask-opt-body"><div className="ask-opt-label">自定义回答…</div></div>
            </div>
          )}
        </div>
        {q.multiSelect && !otherOn && (
          <button className="ask-btn" disabled={sending || !Object.values(multiSel).some(Boolean)}
            onClick={confirmMulti}>确定{last ? '' : '，下一题'}</button>
        )}
        <div className="ask-foot">
          {sending ? <span className="ask-status">正在替你选…</span>
            : failed ? <span className="ask-status ask-status--bad">没选上，可能界面对不上——改用打字最稳</span>
            : <span />}
          <span className="ask-esc" onClick={() => { escapeAsk(); onClose(true) }}>改用打字回答</span>
        </div>
      </div>
    </div>
  )
}
