// 底部抽屉：最近图片选择器 + 贴纸面板（含上传新贴纸）。
// 从 chat.html openImagePicker / sticker panel 移植。
import { useEffect, useRef, useState } from 'react'
import { API, HEADERS, DEMO_STICKERS } from '../lib/api.js'

export function ImagePicker({ onConfirm, onBrowse, onClose }) {
  const [imgs, setImgs] = useState(null)
  const [sel, setSel] = useState([])

  useEffect(() => {
    fetch(API + '/recent-images', { headers: HEADERS })
      .then(r => (r.ok ? r.json() : []))
      .then(setImgs)
      .catch(() => setImgs([]))
  }, [])

  function toggle(src) {
    setSel(prev => (prev.includes(src) ? prev.filter(s => s !== src) : prev.concat(src)))
  }

  return (
    <div className="sheet-ov" onClick={onClose}>
      <div className="sheet" onClick={e => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="sheet-head">
          <span className="sheet-title">选择图片</span>
          <span className="sheet-link" onClick={() => { onClose(); onBrowse() }}>浏览文件…</span>
        </div>
        <div className="picker-grid">
          {imgs == null && <div className="picker-empty">加载中…</div>}
          {imgs != null && !imgs.length && <div className="picker-empty">还没有图片～点右上角「浏览文件…」</div>}
          {(imgs || []).map((img, i) => {
            const idx = sel.indexOf(img.src)
            return (
              <div key={i} className="picker-cell"
                style={{
                  backgroundImage: `url("${String(img.src).replace(/["\\]/g, '')}")`,
                  outline: idx > -1 ? '2px solid var(--c-accent)' : 'none',
                  outlineOffset: '-2px',
                }}
                onClick={() => toggle(img.src)}>
                <div className="picker-check" style={idx > -1 ? { background: 'var(--c-accent)' } : undefined}>
                  {idx > -1 ? idx + 1 : ''}
                </div>
              </div>
            )
          })}
        </div>
        {sel.length > 0 && (
          <div className="picker-bar">
            <button onClick={() => { onConfirm(sel.slice()); onClose() }}>添加 {sel.length} 项</button>
          </div>
        )}
      </div>
    </div>
  )
}

// 贴纸卡：长按已有贴纸是编辑（改名、改描述、删除），选了新图是添加——
// 同一张卡两种模式。描述是给 AI 读的：它看到的是 [sticker:文件名] +
// meta.json 里的文字，不是图片本身，所以添加时就该把描述要到手
function StickerEditCard({ sticker, create, onSaved, onDeleted, onClose }) {
  const [name, setName] = useState(sticker.name || '')
  const [desc, setDesc] = useState(sticker.desc || '')
  const [armed, setArmed] = useState(false)

  function save() {
    if (create) {
      fetch(API + '/sticker-upload', {
        method: 'POST', headers: HEADERS,
        body: JSON.stringify({ data: sticker.data, name, desc, filename: sticker.filename }),
      })
        .then(r => r.json())
        .then(d => { if (d.ok) onSaved({ file: d.file, name: name || d.name, desc, src: API + '/stickers/' + d.file }) })
        .catch(() => {})
      return
    }
    fetch(API + '/stickers-edit', {
      method: 'POST', headers: HEADERS,
      body: JSON.stringify({ file: sticker.file, name, desc }),
    })
      .then(r => r.json())
      .then(d => { if (d.ok) onSaved({ ...sticker, name, desc }) })
      .catch(() => {})
  }
  function del() {
    if (!armed) { setArmed(true); return }
    fetch(API + '/stickers-delete', {
      method: 'POST', headers: HEADERS,
      body: JSON.stringify({ file: sticker.file, name: '', desc: '' }),
    })
      .then(r => r.json())
      .then(d => { if (d.ok) onDeleted(sticker) })
      .catch(() => {})
  }

  return (
    <div className="sheet-ov sticker-edit-ov" onClick={onClose}>
      <div className="sticker-edit" onClick={e => e.stopPropagation()}>
        <img className="sticker-edit-preview" src={create ? sticker.data : (sticker.src || (API + '/stickers/' + sticker.file))} alt="" draggable={false} />
        <label className="sticker-edit-label">名字
          <input className="sticker-edit-input" value={name} maxLength={30}
            onChange={e => setName(e.target.value)} placeholder="给表情包起个名字" />
        </label>
        <label className="sticker-edit-label">描述（AI 靠它认识这张表情包）
          <textarea className="sticker-edit-input sticker-edit-desc" value={desc} maxLength={200} rows={2}
            onChange={e => setDesc(e.target.value)} placeholder="什么心情、什么场合用" />
        </label>
        <div className="sticker-edit-btns">
          {create ? <span /> : (
            <span className={'sticker-edit-del' + (armed ? ' sticker-edit-del--armed' : '')}
              onClick={del}>{armed ? '再点一次确认删除' : '删除'}</span>
          )}
          <span className="sticker-edit-save" onClick={save}>{create ? '添加' : '保存'}</span>
        </div>
      </div>
    </div>
  )
}

export function StickerPanel({ onSend, onClose }) {
  const [stickers, setStickers] = useState([])
  const [editing, setEditing] = useState(null)
  const [adding, setAdding] = useState(null)
  const holdTimer = useRef(null)
  const held = useRef(false)

  useEffect(() => {
    fetch(API + '/stickers-meta', { headers: HEADERS })
      .then(r => (r.ok ? r.json() : Promise.reject()))
      .then(meta => {
        const list = []
        for (const k of Object.keys(meta)) {
          list.push({ file: k, name: meta[k].name || k, desc: meta[k].desc || '', src: API + '/stickers/' + k })
        }
        setStickers(list.length ? list : DEMO_STICKERS.map(s => ({ ...s, demo: true })))
      })
      .catch(() => setStickers(DEMO_STICKERS.map(s => ({ ...s, demo: true }))))
  }, [])

  // 长按贴纸 → 编辑卡（和长按气泡出菜单同一手势语言）；
  // demo 贴纸只是配置里的占位，服务器上没有实体，不进编辑
  function holdStart(s) {
    held.current = false
    clearTimeout(holdTimer.current)
    if (s.demo || !s.file) return
    holdTimer.current = setTimeout(() => { held.current = true; setEditing(s) }, 550)
  }
  function holdEnd() { clearTimeout(holdTimer.current) }

  function uploadSticker() {
    const inp = document.createElement('input')
    inp.type = 'file'
    inp.accept = 'image/*'
    inp.addEventListener('change', ev => {
      const f = ev.target.files[0]
      if (!f) return
      const rd = new FileReader()
      rd.onload = () => {
        const img = new Image()
        img.onload = () => {
          const max = 256
          let w = img.width
          let h = img.height
          if (w > max || h > max) {
            const s = max / Math.max(w, h)
            w = Math.round(w * s)
            h = Math.round(h * s)
          }
          const cv = document.createElement('canvas')
          cv.width = w
          cv.height = h
          cv.getContext('2d').drawImage(img, 0, 0, w, h)
          const data = cv.toDataURL('image/png', 0.9)
          // 不用 prompt() 弹丑框：开与编辑卡同款的添加卡，名字+描述一次要齐
          setAdding({ data, filename: f.name, name: f.name.replace(/\.[^.]+$/, ''), desc: '' })
        }
        img.src = rd.result
      }
      rd.readAsDataURL(f)
    })
    inp.click()
  }

  return (
    <div className="sheet-ov" onClick={onClose}>
      <div className="sheet sheet--sticker" onClick={e => e.stopPropagation()}>
        <div className="sheet-handle" />
        <div className="sheet-head">
          <span className="sheet-title">表情包</span>
          <span className="sheet-close" onClick={onClose}>✕</span>
        </div>
        <div className="sticker-grid">
          {stickers.map((s, i) => (
            <div key={i} className="sticker-cell"
              onClick={() => { if (held.current) { held.current = false; return } onSend(s); onClose() }}
              onPointerDown={() => holdStart(s)}
              onPointerUp={holdEnd} onPointerLeave={holdEnd} onPointerCancel={holdEnd}
              onContextMenu={e => e.preventDefault()}>
              <img src={s.src || (API + '/stickers/' + s.file)} alt={s.name || ''} draggable={false} />
            </div>
          ))}
          <div className="sticker-add" onClick={uploadSticker}>＋</div>
          {!stickers.length && <div className="picker-empty" style={{ gridColumn: '1 / -1' }}>还没有表情包～</div>}
        </div>
      </div>
      {editing && (
        <StickerEditCard sticker={editing}
          onSaved={s => { setStickers(prev => prev.map(x => (x.file === s.file ? s : x))); setEditing(null) }}
          onDeleted={s => { setStickers(prev => prev.filter(x => x.file !== s.file)); setEditing(null) }}
          onClose={() => setEditing(null)} />
      )}
      {adding && (
        <StickerEditCard sticker={adding} create
          onSaved={s => { setStickers(prev => prev.filter(x => !x.demo).concat(s)); setAdding(null) }}
          onClose={() => setAdding(null)} />
      )}
    </div>
  )
}
