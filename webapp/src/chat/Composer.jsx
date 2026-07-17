// 输入区：+号工具栏(图片/文件/贴纸)、附件条(缩略图/上传转圈/错误/移除)、
// 引用条、textarea 自适应。上传流从 chat.html attachUpload/renderAttach 移植。
import { useEffect, useRef, useState } from 'react'
import { uploadToServer } from '../lib/look.js'
import { API, TOKEN } from '../lib/api.js'

let attSeq = 0

export default function Composer({ api, quote, onClearQuote, onSubmit, onOpenSticker, onOpenPicker, doc, taRef, onFocus }) {
  const [tb, setTb] = useState(false)
  const [attach, setAttach] = useState([])
  // 草稿住在这里：打字只重渲染输入区，消息列表不动（性能关键）
  const [input, setInput] = useState(() => {
    try { return sessionStorage.getItem('chatDraft') || '' } catch (e) { return '' }
  })
  const inputVal = useRef(input)
  const imgRef = useRef(null)
  const fileRef = useRef(null)
  const imgPress = useRef(null)
  // 语音输入（旧覆盖层 injectVoiceBtn/startVoiceRec/sendVoiceMsg 收编）：
  // 麦克风切换按住说话，录完上传+STT 并行，发 [voice:file:dur] 文字
  const [voiceMode, setVoiceMode] = useState(false)
  const [recState, setRecState] = useState('') // '' | 'rec' | 'sending'
  const rec = useRef({ mr: null, chunks: [], start: 0 })

  function startRec() {
    if (rec.current.mr) return
    rec.current.chunks = []
    rec.current.start = Date.now()
    setRecState('rec')
    navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      rec.current.mr = mr
      mr.ondataavailable = e => { if (e.data.size > 0) rec.current.chunks.push(e.data) }
      mr.onstop = () => {
        stream.getTracks().forEach(t => t.stop())
        rec.current.mr = null
        if (!rec.current.chunks.length) { setRecState(''); return }
        const blob = new Blob(rec.current.chunks, { type: 'audio/webm' })
        rec.current.chunks = []
        sendVoice(blob, Math.round((Date.now() - rec.current.start) / 1000))
      }
      mr.start()
    }).catch(() => { rec.current.mr = null; setRecState('') })
  }

  function stopRec() {
    const mr = rec.current.mr
    if (mr && mr.state !== 'inactive') mr.stop()
    else setRecState('')
  }

  function cancelRec() {
    const mr = rec.current.mr
    if (mr) { mr.ondataavailable = null; mr.onstop = null; try { mr.stream.getTracks().forEach(t => t.stop()) } catch (e) {}; if (mr.state !== 'inactive') mr.stop() }
    rec.current.mr = null
    rec.current.chunks = []
    setRecState('')
  }

  function sendVoice(blob, dur) {
    setRecState('sending')
    const fname = 'voice_' + Date.now() + '.webm'
    const upP = uploadToServer(new File([blob], fname, { type: 'audio/webm' }))
      .then(d => d.filename || fname)
    const fd = new FormData()
    fd.append('audio', blob, fname)
    const sttP = fetch(API + '/api/call/transcribe', {
      method: 'POST', headers: { Authorization: 'Bearer ' + TOKEN }, body: fd,
    }).then(r => r.json()).catch(() => ({ text: '' }))
    Promise.all([upP, sttP]).then(([file, stt]) => {
      const text = (stt.text || '').trim()
      onSubmit('[voice:' + file + ':' + dur + ']' + (text ? ' ' + text : ''), [])
      setRecState('')
    }).catch(() => setRecState(''))
  }

  function onInput(e) {
    inputVal.current = e.target.value
    setInput(e.target.value)
    try { sessionStorage.setItem('chatDraft', e.target.value) } catch (err) {}
    const ta = e.target
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 120) + 'px'
  }

  // Chat 通过这两个把手读草稿（选图器拼文本）/发送成功后清空。
  // 挂在 effect 里而不是渲染期：ref 突变对编译器必须不可见
  useEffect(() => {
    if (!api) return
    api.current.getText = () => inputVal.current
    api.current.clear = () => {
      inputVal.current = ''
      setInput('')
      try { sessionStorage.removeItem('chatDraft') } catch (e) {}
      if (taRef && taRef.current) taRef.current.style.height = 'auto'
    }
  })

  const anyUploading = attach.some(a => a.uploading)

  function patchAtt(key, patch) {
    setAttach(prev => prev.map(a => (a.key === key ? { ...a, ...patch } : a)))
  }

  function startUpload(at) {
    uploadToServer(at.file, pct => patchAtt(at.key, { progress: pct }))
      .then(d => patchAtt(at.key, { serverPath: d.path, serverFilename: d.filename, uploading: false }))
      .catch(err => patchAtt(at.key, {
        uploadError: true,
        uploading: false,
        errorMsg: err && err.status === 413 ? '超过服务器上限' : '上传失败，点!重试',
      }))
  }

  function retryUpload(at) {
    patchAtt(at.key, { uploadError: false, errorMsg: '', uploading: true, progress: 0 })
    startUpload(at)
  }

  function addImages(files) {
    files.forEach(f => {
      const rd = new FileReader()
      rd.onload = () => {
        const at = { key: 'a' + attSeq++, thumb: rd.result, name: f.name, file: f, isImage: true, uploading: true }
        setAttach(prev => prev.concat(at))
        startUpload(at)
      }
      rd.readAsDataURL(f)
    })
  }

  function addFiles(files) {
    files.forEach(f => {
      const at = { key: 'a' + attSeq++, thumb: '', name: f.name, file: f, isImage: false, uploading: true }
      setAttach(prev => prev.concat(at))
      startUpload(at)
    })
  }

  function closeTb() {
    setTb(false)
  }

  function submit() {
    if (anyUploading) return
    if (onSubmit(input, attach)) setAttach([])
  }

  // 图片按钮：短按开文件浏览，长按(500ms)开最近图片选择器
  function imgDown() {
    imgPress.current = setTimeout(() => {
      imgPress.current = 'long'
      closeTb()
      onOpenPicker()
    }, 500)
  }
  function imgUp() {
    if (imgPress.current !== 'long') {
      clearTimeout(imgPress.current)
      imgRef.current.click()
      closeTb()
    }
    imgPress.current = null
  }

  return (
    <div className={'chat-composer' + (doc ? ' chat-composer--doc' : '')}>
      {quote && (
        <div className="chat-quote-bar">
          <div className="chat-quote-text">{quote.text}</div>
          <span className="chat-quote-clear" onClick={onClearQuote}>✕</span>
        </div>
      )}
      {attach.length > 0 && (
        <div className="chat-attach-bar">
          {attach.map(at => at.thumb ? (
            <div key={at.key} className="att-thumb-wrap">
              <div className="att-thumb" style={{ backgroundImage: `url("${at.thumb.replace(/["\\]/g, '')}")` }} />
              {at.uploading && (
                <div className="att-shade">
                  {at.progress > 0 ? <span className="att-pct">{at.progress}%</span> : <div className="att-spin" />}
                </div>
              )}
              {at.uploadError && <div className="att-shade att-err" title={at.errorMsg} onClick={() => retryUpload(at)}>!</div>}
              <div className="att-rm" onClick={() => setAttach(prev => prev.filter(a => a.key !== at.key))}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
              </div>
            </div>
          ) : (
            <div key={at.key} className="att-file-wrap">
              {at.uploading ? (
                at.progress > 0 ? <span className="att-pct att-pct--sm">{at.progress}%</span> : <div className="att-spin att-spin--sm" />
              ) : at.uploadError ? (
                <span className="att-err-badge" title={at.errorMsg} onClick={() => retryUpload(at)}>!</span>
              ) : (
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--c-muted)" strokeWidth="1.6" style={{ flexShrink: 0 }}><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>
              )}
              <span className="att-file-name">{at.name}</span>
              <div className="att-rm" onClick={() => setAttach(prev => prev.filter(a => a.key !== at.key))}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="chat-input-row">
        <span className="chat-plus" style={{ transform: tb ? 'rotate(45deg)' : 'none' }} onClick={() => setTb(!tb)}>+</span>
        <button className={'voice-toggle' + (voiceMode ? ' active' : '')} title="语音输入"
          onClick={() => { if (recState) cancelRec(); setVoiceMode(v => !v) }}>
          {voiceMode ? (
            <svg viewBox="0 0 24 24"><rect x="2" y="4" width="20" height="16" rx="2" /><line x1="6" y1="8" x2="6" y2="8" /><line x1="10" y1="8" x2="10" y2="8" /><line x1="14" y1="8" x2="14" y2="8" /><line x1="18" y1="8" x2="18" y2="8" /><line x1="6" y1="12" x2="6" y2="12" /><line x1="10" y1="12" x2="10" y2="12" /><line x1="14" y1="12" x2="14" y2="12" /><line x1="18" y1="12" x2="18" y2="12" /><line x1="8" y1="16" x2="16" y2="16" /></svg>
          ) : (
            <svg viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>
          )}
        </button>
        {voiceMode ? (
          <div className={'voice-hold-btn' + (recState === 'rec' ? ' rec' : '')}
            onPointerDown={e => { e.preventDefault(); if (recState !== 'sending') startRec() }}
            onPointerUp={() => { if (recState === 'rec') stopRec() }}
            onPointerLeave={() => { if (recState === 'rec') cancelRec() }}
            onPointerCancel={() => { if (recState === 'rec') cancelRec() }}
            onContextMenu={e => e.preventDefault()}>
            {recState === 'rec' ? <><span className="voice-dot" />松开 发送</>
              : recState === 'sending' ? '发送中...' : '按住 说话'}
          </div>
        ) : (
          <>
            <textarea
              ref={taRef}
              rows={1}
              placeholder="输入消息..."
              value={input}
              onChange={onInput}
              onFocus={onFocus}
              onKeyDown={e => {
                const isMobile = 'ontouchstart' in window || navigator.maxTouchPoints > 0
                if (e.key === 'Enter' && !isMobile && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault()
                  submit()
                }
              }}
            />
            <div className="chat-send" role="button" style={{ opacity: anyUploading ? 0.5 : 1 }} onClick={submit}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12" />
                <polyline points="12 5 19 12 12 19" />
              </svg>
            </div>
          </>
        )}
      </div>
      {tb && (
        <div className="chat-toolbar">
          <button onPointerDown={imgDown} onPointerUp={imgUp}
            onPointerLeave={() => { if (imgPress.current !== 'long') clearTimeout(imgPress.current); imgPress.current = null }}>
            <span className="tb-circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="3" y="3" width="18" height="18" rx="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg></span>image
          </button>
          <button onClick={() => { fileRef.current.click(); closeTb() }}>
            <span className="tb-circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg></span>file
          </button>
          <button onClick={() => { onOpenSticker(); closeTb() }}>
            <span className="tb-circle"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="12" cy="12" r="10" /><path d="M8 14s1.5 2 4 2 4-2 4-2" /><line x1="9" y1="9" x2="9.01" y2="9" /><line x1="15" y1="9" x2="15.01" y2="9" /></svg></span>sticker
          </button>
        </div>
      )}
      <input type="file" accept="image/*" multiple ref={imgRef} style={{ display: 'none' }}
        onChange={e => { addImages(Array.from(e.target.files || [])); e.target.value = '' }} />
      <input type="file" multiple ref={fileRef} style={{ display: 'none' }}
        onChange={e => { addFiles(Array.from(e.target.files || [])); e.target.value = '' }} />
    </div>
  )
}
