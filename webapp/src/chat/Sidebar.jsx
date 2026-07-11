// 侧栏（主视图 + 设置视图），从 chat.html renderOverlays sidebar 移植。
// 源码里只硬编码本仓库真实具备的功能；部署私有的入口（额外页面、开关）
// 由 config.js 的 sidebarExtras 声明，或由桥的 /extensions 注册表提供。
import { useEffect, useRef, useState } from 'react'
import { API, CFG, HEADERS, ID } from '../lib/api.js'
import { LOOK, uploadToServer, saveLook, shrinkImage } from '../lib/look.js'

function Item({ icon, label, onClick, color }) {
  return (
    <button className="sb-item" style={color ? { color } : undefined} onClick={onClick}>
      <span className="sb-icon">{icon}</span>{label}
    </button>
  )
}

export default function Sidebar({ mode, theme, offline, onClose, onToggleMode, onCycleTheme, onLookChange, onOpenMusic }) {
  const [view, setView] = useState('main')
  const [note, setNote] = useState('')
  const [forgePaused, setForgePaused] = useState(null)
  // 部署声明的私有入口 + 桥注册表的链接（没有注册表的桥 404 → 空着）
  const extras = Array.isArray(CFG.sidebarExtras) ? CFG.sidebarExtras : []
  const [exts, setExts] = useState([])
  // toggle 类入口的开关态，按 endpoint 存
  const [toggles, setToggles] = useState({})
  const bgRef = useRef(null)
  const avRef = useRef(null)
  const bgTarget = useRef('light')
  const avTarget = useRef('ai')

  useEffect(() => {
    fetch(API + '/extensions', { headers: HEADERS })
      .then(r => (r.ok ? r.json() : null))
      .then(x => { if (x) setExts((x.extensions || []).filter(e => e.enabled && e.href)) })
      .catch(() => {})
    fetch(API + '/forge-auto-reload', { headers: HEADERS })
      .then(r => r.json()).then(d => setForgePaused(!!d.paused)).catch(() => {})
    extras.filter(x => x.kind === 'toggle' && x.endpoint).forEach(x => {
      fetch(API + x.endpoint, { headers: HEADERS })
        .then(r => r.json()).then(d => setToggles(t => ({ ...t, [x.endpoint]: !!d.on }))).catch(() => {})
    })
  }, [])

  function post(path, body) {
    return fetch(API + path, { method: 'POST', headers: HEADERS, body: JSON.stringify(body || {}) })
  }

  function extraItem(x, i) {
    if (x.kind === 'music') {
      return <Item key={'x' + i} icon={x.icon || '♫'} label={x.label} onClick={onOpenMusic} />
    }
    if (x.kind === 'toggle' && x.endpoint) {
      const on = toggles[x.endpoint]
      return <Item key={'x' + i} icon={x.icon || '◇'}
        label={x.label + ': ' + (on == null ? '…' : on ? 'on' : 'off')}
        onClick={() => {
          post(x.endpoint, { on: !on })
            .then(r => r.json()).then(d => setToggles(t => ({ ...t, [x.endpoint]: !!d.on }))).catch(() => {})
        }} />
    }
    if (!x.href) return null
    return <Item key={'x' + i} icon={x.icon || '◇'} label={x.label}
      onClick={() => { window.location.href = x.href }} />
  }

  // 每个外观槽位一个单调序号：连续换图时，慢的旧上传迟到后作废，
  // 不许它把后换的新图盖回去（竞态实锤过：大图上传慢→回调迟到→旧盖新）
  const lookSeq = useRef({})

  function onBgFile(e) {
    const f = e.target.files && e.target.files[0]
    e.target.value = ''
    if (!f) return
    const key = bgTarget.current === 'dark' ? LOOK.bgDark : LOOK.bg
    const serverKey = bgTarget.current === 'dark' ? 'bgDark' : 'bg'
    const label = bgTarget.current === 'dark' ? '夜间' : '日间'
    const seq = (lookSeq.current[key] = (lookSeq.current[key] || 0) + 1)
    setNote(label + '背景上传中…')
    shrinkImage(f, 2560)
      .then(uploadToServer)
      .then(d => {
        if (seq !== lookSeq.current[key]) return
        // ?v= 版本号：桥落盘同名覆盖,URL 不变浏览器连请求都不发；字符串变了缓存才失效
        const url = API + '/files/' + d.filename + '?v=' + Date.now()
        localStorage.setItem(key, url)
        saveLook(serverKey, url)
        setNote(label + '背景已更换')
        onLookChange()
      })
      .catch(() => { if (seq === lookSeq.current[key]) setNote('上传失败') })
  }

  function onAvFile(e) {
    const f = e.target.files && e.target.files[0]
    e.target.value = ''
    if (!f) return
    const key = avTarget.current === 'user' ? LOOK.userAvatar : LOOK.aiAvatar
    const serverKey = avTarget.current === 'user' ? 'userAvatar' : 'aiAvatar'
    const label = avTarget.current === 'user' ? '我的' : ID.aiName + ' '
    const seq = (lookSeq.current[key] = (lookSeq.current[key] || 0) + 1)
    setNote(label + '头像上传中…')
    shrinkImage(f, 512)
      .then(uploadToServer)
      .then(d => {
        if (seq !== lookSeq.current[key]) return
        const url = API + '/files/' + d.filename + '?v=' + Date.now()
        localStorage.setItem(key, url)
        saveLook(serverKey, url)
        setNote(label + '头像已更换')
        onLookChange()
      })
      .catch(() => { if (seq === lookSeq.current[key]) setNote('上传失败') })
  }

  return (
    <div className="sb-ov" onClick={onClose}>
      <div className="sb-panel" onClick={e => e.stopPropagation()}>
        <div className="sb-header" onClick={() => (view === 'settings' ? setView('main') : (window.location.href = '/'))}>
          <span style={{ color: 'var(--c-accent)' }}>←</span>{view === 'settings' ? '设置' : '返回'}
        </div>
        <div className="sb-nav">
          {view === 'settings' ? (
            <>
              <div className="sb-title">外观</div>
              <Item icon="☀" label="日间背景" onClick={() => { bgTarget.current = 'light'; bgRef.current.click() }} />
              <Item icon="🌙" label="夜间背景" onClick={() => { bgTarget.current = 'dark'; bgRef.current.click() }} />
              <Item icon={ID.aiName.slice(0, 1)} label={ID.aiName + '头像'} onClick={() => { avTarget.current = 'ai'; avRef.current.click() }} />
              <Item icon={ID.userName.slice(0, 1)} label="我的头像" onClick={() => { avTarget.current = 'user'; avRef.current.click() }} />
              <div className="sb-title" style={{ opacity: 0.5 }}>build {__BUILD__}</div>
              <Item icon="⟲" label="恢复默认外观" onClick={() => {
                localStorage.removeItem(LOOK.bg)
                localStorage.removeItem(LOOK.bgDark)
                localStorage.removeItem(LOOK.userAvatar)
                localStorage.removeItem(LOOK.aiAvatar)
                ;['bg', 'bgDark', 'userAvatar', 'aiAvatar'].forEach(k => saveLook(k, ''))
                setNote('已恢复默认')
                onLookChange()
              }} />
            </>
          ) : (
            <>
              <Item icon="+" label="新会话" onClick={onClose} />
              {extras.filter(x => x.section === 'top').map(extraItem)}
              <Item icon="✎" label="编辑器" onClick={() => { window.location.href = '/editor.html' }} />
              <div className="sb-sep" />
              <div className="sb-title">工具</div>
              <Item icon="☰" label="history" onClick={() => { onClose(); window.location.hash = '#/history' }} />
              <Item icon=">_" label="terminal" onClick={() => { window.location.href = API + '/terminal' }} />
              <div className="sb-title">外观</div>
              <Item icon="❐" label={'mode: ' + (mode === 'doc' ? 'claude' : 'bubble')} onClick={onToggleMode} />
              <Item icon="☯" label={'theme: ' + theme} onClick={onCycleTheme} />
              <div className="sb-title">会话</div>
              <Item icon="+" label="new session" onClick={() => post('/new-session').then(() => location.reload())} />
              <Item icon="○" label="clean window" onClick={() => post('/clean-session').then(() => location.reload())} />
              <Item icon="↻" label="forge restart" onClick={() => post('/forge-reload-session').then(() => location.reload())} />
              <Item icon="||" label={'auto forge: ' + (forgePaused == null ? '…' : forgePaused ? 'paused' : 'on')}
                onClick={() => {
                  post('/forge-auto-reload', { paused: !forgePaused, force: true })
                    .then(r => r.json()).then(d => setForgePaused(!!d.paused)).catch(() => {})
                }} />
              {(extras.some(x => x.section !== 'top') || exts.length > 0) && (
                <>
                  <div className="sb-title">扩展</div>
                  {extras.filter(x => x.section !== 'top').map(extraItem)}
                  {exts.map(ext => (
                    <Item key={ext.id} icon="◇" label={ext.title} onClick={() => { window.location.href = ext.href }} />
                  ))}
                </>
              )}
              <div className="sb-sep" />
              <Item icon="⚙" label="设置" onClick={() => setView('settings')} />
            </>
          )}
          <div className="sb-note">{note}</div>
        </div>
        <div className="sb-status">{offline ? '● offline' : '● alive'}</div>
        <input type="file" accept="image/*" ref={bgRef} style={{ display: 'none' }} onChange={onBgFile} />
        <input type="file" accept="image/*" ref={avRef} style={{ display: 'none' }} onChange={onAvFile} />
      </div>
    </div>
  )
}
