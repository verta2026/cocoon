// 长按菜单 + 灯箱，从 chat.html renderOverlays 移植。侧栏下一批。
import { useLayoutEffect, useRef, useState } from 'react'
import { cssUrl } from './Bubble.jsx'
import { NS } from '../lib/api.js'

export function loadQuicks() {
  try {
    const v = JSON.parse(localStorage.getItem(NS + '_chat_quick_emojis_v1') || 'null')
    if (Array.isArray(v) && v.length) return v
  } catch (e) {}
  return ['❤️', '😂', '😮', '🥺', '👍']
}

export function ContextMenu({ menu, reacts, quicks, onReact, onAddQuick, onClose }) {
  const popRef = useRef(null)
  const [emojiAdd, setEmojiAdd] = useState(false)
  const [emojiVal, setEmojiVal] = useState('')

  // 按实测尺寸钳进可视区。依赖含 emojiAdd：加号展开输入行弹窗会长高，得重钳；
  // 视口用 visualViewport：软键盘弹起时 innerHeight 仍是含键盘的布局高度，会算到键盘底下
  useLayoutEffect(() => {
    function position() {
      const popup = popRef.current
      if (!popup) return
      const ph = popup.offsetHeight
      const pw = popup.offsetWidth
      const vv = window.visualViewport
      const vw = (vv && vv.width) || window.innerWidth
      const vh = (vv && vv.height) || window.innerHeight
      const px = Math.max(8, Math.min(menu.x - pw / 2, vw - pw - 8))
      let py = menu.y - ph - 8
      if (py < 8) py = menu.y + 8
      if (py + ph > vh - 8) py = vh - ph - 8
      popup.style.left = px + 'px'
      popup.style.top = Math.max(8, py) + 'px'
      popup.style.visibility = 'visible'
    }
    position()
    const vv = window.visualViewport
    if (vv) {
      vv.addEventListener('resize', position)
      return () => vv.removeEventListener('resize', position)
    }
  }, [menu, emojiAdd])

  function commitQuick() {
    const v = emojiVal.trim()
    if (!v) { setEmojiAdd(false); return }
    onAddQuick(v)
    setEmojiAdd(false)
    setEmojiVal('')
    onReact(menu.id, v, menu.content)
  }

  return (
    <div className="cm-ov" onClick={onClose}>
      <div className="cm-popup" ref={popRef} onClick={e => e.stopPropagation()}>
        <div className="cm-emoji-row">
          {quicks.map(emoji => (
            <button key={emoji}
              className={'cm-emoji' + ((reacts[menu.id] || []).indexOf(emoji) > -1 ? ' cm-emoji--on' : '')}
              onClick={() => onReact(menu.id, emoji, menu.content)}>
              {emoji}
            </button>
          ))}
          {emojiAdd && (
            <input className="cm-emoji-input" value={emojiVal} placeholder="输入emoji" autoFocus
              onChange={e => setEmojiVal(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); commitQuick() } }} />
          )}
          <button className="cm-emoji-add" onClick={() => (emojiAdd ? commitQuick() : setEmojiAdd(true))}>＋</button>
        </div>
      </div>
    </div>
  )
}

export function Lightbox({ src, onClose }) {
  return (
    <div className="lb-ov" onClick={onClose}>
      <div className="lb-img" style={{ backgroundImage: cssUrl(src) }} />
    </div>
  )
}

// 双击气泡的全屏选字页：气泡里长按撞菜单、滑动撞引用，选区没活路——
// 铺到全屏就都让开了。只有 ✕ 能关，点正文不关（点哪都关会杀选区手势）
export function TextView({ text, onClose }) {
  return (
    <div className="textview">
      <button className="textview-close" onClick={onClose} aria-label="close">✕</button>
      <div className="textview-body">{text}</div>
    </div>
  )
}
