import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useChat } from './useChat.js'
import Bubble, { cssUrl } from './Bubble.jsx'
import { ContextMenu, Lightbox, TextView, loadQuicks } from './Overlays.jsx'
import Sidebar from './Sidebar.jsx'
import Composer from './Composer.jsx'
import { ImagePicker, StickerPanel } from './Sheets.jsx'
import AskSheet from './AskSheet.jsx'
import { channelWho } from './parseMessage.js'
import { NS } from '../lib/api.js'
import { wallpaperUrl, avatarUrl, extractWallpaperColors, loadLook } from '../lib/look.js'
import Music from './Music.jsx'
import { restoreMusic, openFull } from '../lib/music.js'
import './chat.css'

function isDark(t) {
  const h = new Date().getHours()
  return t === 'dark' || (t === 'auto' && (h < 7 || h >= 19))
}

function syncClaude(mode) {
  if (mode === 'doc') document.body.setAttribute('data-claude', '')
  else document.body.removeAttribute('data-claude')
}

function TypingRow({ doc, avatar }) {
  if (doc) {
    return (
      <div className="cb-typing-doc" id="typing-row">
        <div className="cb-typing cb-typing--bare">
          {[0, 1, 2].map(i => <span key={i} style={{ animationDelay: i * 0.16 + 's' }} />)}
        </div>
      </div>
    )
  }
  return (
    <div className="cb-row msg--assistant" id="typing-row">
      <div className="cb-avatar">
        <div className="cb-avatar-img" style={{ backgroundImage: cssUrl(avatar) }} />
      </div>
      <div className="cb-typing">
        {[0, 1, 2].map(i => <span key={i} style={{ animationDelay: i * 0.16 + 's' }} />)}
      </div>
    </div>
  )
}

export default function Chat() {
  const {
    rows, typing, offline, reacts, cfgReady, send, retry, react, loadOlder, loadingOlder, histAnchor,
    jumpTo, loadNewer, loadingNewer, exitArchive, inArchive, jumpHl, setJumpHl, ask, setAsk,
  } = useChat()
  // 选择题弹窗：answered 记住已答/已弃的 id（轮询要几秒才把 ask 撤下来）；
  // askMin=true 折成悬浮胶囊，点开还在
  const [askDone, setAskDone] = useState('')
  const [askMin, setAskMin] = useState(false)
  const askLive = ask && ask.id !== askDone ? ask : null
  // 草稿状态住在 Composer 里：敲字不再牵动整棵消息树。这里只留读/清的把手
  const composerApi = useRef({ getText: () => '', clear: () => {} })
  const [expId, setExpId] = useState(null)
  const [copied, setCopied] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem(NS + '_chat_theme') || 'auto')
  const [mode, setMode] = useState(() => localStorage.getItem(NS + '_chat_mode') || 'bubble')
  const [menu, setMenu] = useState(null)
  const [lb, setLb] = useState(null)
  const [tv, setTv] = useState(null) // 双击气泡的全屏选字页
  const [quote, setQuote] = useState(null)
  const [side, setSide] = useState(false)
  const [sticker, setSticker] = useState(false)
  const [picker, setPicker] = useState(false)
  const [showDown, setShowDown] = useState(false)
  const [lookVer, setLookVer] = useState(0)
  const [docPad, setDocPad] = useState(0)
  const [quicks, setQuicks] = useState(loadQuicks)
  const [foldClosed, setFoldClosed] = useState({})
  const logRef = useRef(null)
  const taRef = useRef(null)
  const frostRef = useRef(null)
  const stick = useRef(true)
  const docAlign = useRef(false) // doc 弹起锚定中：最后一条自己的消息钉在头部下
  const docPadRef = useRef(0)    // docPad 的同步镜像（layout effect 里读不到刚 set 的 state）
  // 输入框长高让位：多行输入时 composer 盖住底部气泡且滚不出来——
  // 量出相对一行态多出的高度，聊天区底部等量垫高
  const [compExtra, setCompExtra] = useState(0)
  const compExtraRef = useRef(0)
  const compWrapRef = useRef(null)

  useEffect(() => {
    const el = compWrapRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const base = el.offsetHeight // 挂载时是一行态，CSS 的 74px 底衬就是按它给的
    const ro = new ResizeObserver(() => {
      const extra = Math.max(0, Math.round(el.offsetHeight - base))
      if (extra !== compExtraRef.current) {
        compExtraRef.current = extra
        setCompExtra(extra)
      }
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const dark = isDark(theme)
  const doc = mode === 'doc'
  // 外观走 lookVer 驱动的正经数据流：换壁纸/头像 → bump lookVer → 这里重算 → props 层层可见。
  // 渲染期偷读 localStorage 的旧写法在编译器/memo 下会被缓存成"永不更新"
  const wall = useMemo(() => wallpaperUrl(dark, lookVer), [dark, lookVer])
  const avatars = useMemo(() => ({ user: avatarUrl('user', lookVer), ai: avatarUrl('ai', lookVer) }), [lookVer])
  void cfgReady

  // DOM 属性突变全部住进 effect（渲染期保持纯净，编译器的前提）
  useEffect(() => { document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light') }, [dark])
  useEffect(() => { syncClaude(mode) }, [mode])
  useEffect(() => { restoreMusic() }, [])
  // 外观云端化：启动读回服务器的选择（服务器优先），回来后刷新壁纸/头像
  useEffect(() => { loadLook().then(() => setLookVer(v => v + 1)) }, [])
  useEffect(() => { extractWallpaperColors(wall, frostRef.current) }, [wall, dark, lookVer])

  // frost 层：夜间常开；doc 模式日间开磨砂（取色函数夜间会覆盖 cssText）
  useEffect(() => {
    const f = frostRef.current
    if (!f) return
    if (dark) f.style.display = 'block'
    else if (doc) {
      f.style.cssText = 'position:fixed;inset:0;pointer-events:none;backdrop-filter:blur(2px) saturate(1.05);-webkit-backdrop-filter:blur(2px) saturate(1.05);background:rgba(255,250,245,0.02);z-index:1'
      f.style.display = 'block'
    } else f.style.display = 'none'
  }, [dark, doc, lookVer])

  // doc 弹起：实测"锚点消息以下还有多少内容"，底衬 = 视口 − 实测。
  // 回复流进来内容变高 → 底衬每轮渲染自动缩 → 消息钉在头部下，
  // 回复填满一屏时底衬归零，自然回到正常流。不猜高度，不等聚焦。
  useLayoutEffect(() => {
    if (!docAlign.current) return
    const el = logRef.current
    if (!el) return
    const users = el.querySelectorAll('.msg--user')
    const node = users[users.length - 1]
    if (!node) return
    const nodeTop = node.getBoundingClientRect().top - el.getBoundingClientRect().top + el.scrollTop
    // scrollHeight 里含人工底衬(docPad+compExtra)，量"真实内容"时要全部剥掉
    const below = el.scrollHeight - docPadRef.current - compExtraRef.current - nodeTop
    const room = el.clientHeight - below - 8
    // 缩到 composer 净空以下就收场：底衬撤掉，交还 CSS 基础 padding
    const pad = room > 90 ? Math.round(room) : 0
    if (pad === 0) docAlign.current = false
    docPadRef.current = pad
    setDocPad(pad)
  }, [rows, typing])

  // 翻页补偿：prepend 落地后、绘制前把滚动位置钉回原地——视线不跳。
  // layout effect 先于普通 effect 执行，也压住下面的贴底跟随
  useLayoutEffect(() => {
    const a = histAnchor.current
    if (!a || !a.el) return
    histAnchor.current = null
    a.el.scrollTop = a.prevTop + (a.el.scrollHeight - a.prevH)
  }, [rows, histAnchor])

  // 贴底跟随：本来就在底部才自动滚，翻旧消息时不打扰。
  // docPad 进依赖：底衬变化后重新贴底 = 锚点消息精确顶到头部下
  useEffect(() => {
    const el = logRef.current
    if (el && stick.current && !inArchive) el.scrollTop = el.scrollHeight
  }, [rows, typing, docPad, compExtra, inArchive])

  function onScroll() {
    const el = logRef.current
    if (!el) return
    if (el.scrollTop < 80) loadOlder(el)
    const fromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    if (inArchive && fromBottom < 120) loadNewer()
    // 档案窗口里永不贴底跟随：窗口底部不是"现在"
    stick.current = !inArchive && fromBottom < 60
    setShowDown(fromBottom > 400)
  }

  function submit(text, attach) {
    if (send(text, quote ? quote.text : null, attach)) {
      composerApi.current.clear()
      setQuote(null)
      stick.current = true
      // doc 模式：锚定这条消息，弹起对齐交给 layout effect 实测
      if (doc) docAlign.current = true
      return true
    }
    return false
  }

  // 输入框重新聚焦 = 她要说下一句了，底衬提前收场，平滑滚回真实底部
  function onTaFocus() {
    if (!docPad) return
    docAlign.current = false
    docPadRef.current = 0
    setDocPad(0)
    setTimeout(() => {
      const el = logRef.current
      if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    }, 50)
  }

  // history 页点了某条记录：跳进以它为中心的档案窗口
  useEffect(() => {
    const h = e => { if (e.detail) { stick.current = false; jumpTo(String(e.detail)) } }
    window.addEventListener('chat-jump', h)
    return () => window.removeEventListener('chat-jump', h)
  }, [jumpTo])

  // 跳转落地：目标行滚到视野中央并闪一下。只按 jumpHl 触发一次——
  // 挂上 rows 依赖的话，档案窗口里每次翻页都会把视线拽回目标行
  useLayoutEffect(() => {
    if (!jumpHl || !logRef.current) return
    const node = logRef.current.querySelector('[data-mid="' + CSS.escape(jumpHl) + '"]')
    if (!node) return
    node.scrollIntoView({ block: 'center' })
    node.classList.add('row-flash')
    const t = setTimeout(() => { node.classList.remove('row-flash'); setJumpHl('') }, 2000)
    return () => clearTimeout(t)
  }, [jumpHl, setJumpHl])

  // 切离 doc 模式时底衬清场
  useEffect(() => {
    if (!doc) {
      docAlign.current = false
      docPadRef.current = 0
      setDocPad(0)
    }
  }, [doc])

  function confirmPicker(srcs) {
    let text = composerApi.current.getText()
    srcs.forEach(src => { text = (text ? text + '\n' : '') + '[图片] ' + src })
    if (srcs.length) submit(text, [])
  }

  function sendSticker(s) {
    // wire 格式自带名字+描述：[sticker:file|name|desc]——agent 直接读得懂，
    // 前端照样渲染成图，历史(jsonl)里存的也是同一份，不需要桥翻译
    const clean = v => String(v || '').replace(/[|\]\n]/g, ' ').trim()
    const tail = [clean(s.name), clean(s.desc)].filter(Boolean).join('|')
    send('[sticker:' + (s.file || s.name) + (tail ? '|' + tail : '') + ']', null, [])
    stick.current = true
  }

  function openMenu(m, x, y) {
    // 原始坐标直传：钳制在 ContextMenu 里按实测弹窗尺寸做（chat_v2 同款）
    setMenu({ id: m.id, content: m.content, x, y })
  }

  function startQuote(m) {
    setQuote({ id: m.id, text: m.content })
    if (taRef.current) taRef.current.focus()
  }

  function copyMsg(m) {
    try { navigator.clipboard.writeText(m.content) } catch (e) {}
    setCopied(m.id)
    setTimeout(() => setCopied(null), 1500)
  }

  function addQuick(v) {
    setQuicks(prev => {
      const next = prev.indexOf(v) < 0 ? prev.concat([v]).slice(-8) : prev
      localStorage.setItem(NS + '_chat_quick_emojis_v1', JSON.stringify(next))
      return next
    })
  }

  function cycleTheme() {
    const order = ['auto', 'light', 'dark']
    const next = order[(order.indexOf(theme) + 1) % 3]
    localStorage.setItem(NS + '_chat_theme', next)
    setTheme(next)
  }

  function toggleMode() {
    const next = doc ? 'bubble' : 'doc'
    localStorage.setItem(NS + '_chat_mode', next)
    setMode(next)
    setSide(false)
    setTimeout(() => { const el = logRef.current; if (el) el.scrollTop = el.scrollHeight }, 60)
  }

  // ---- 折叠段（chat_v2 语义原样移植）：连续的群聊消息 / 独处提醒 ----
  const isGroupMsg = m => m.role === 'channel' || /group/i.test(m.chat_type || m.chatType || m.telegram || '') || !!m.is_group
  const isSoloMsg = m => m.solo === true || /^\s*\[\[solo\]\]/.test(m.content || '')
  const foldRuns = useMemo(() => {
    const runs = {}
    const runOf = {}
    let i = 0
    while (i < rows.length) {
      if (!(isGroupMsg(rows[i]) || isSoloMsg(rows[i]))) { i++; continue }
      let j = i
      let hasGroup = false
      const names = []
      const seenN = {}
      while (j < rows.length && (isGroupMsg(rows[j]) || isSoloMsg(rows[j]))) {
        if (isGroupMsg(rows[j])) {
          hasGroup = true
          const s = rows[j].role === 'channel' ? (channelWho(rows[j]) || '群友') : ''
          if (s && !seenN[s]) { seenN[s] = 1; names.push(s) }
        }
        j++
      }
      const sid = rows[i].id
      runs[sid] = { start: i, count: j - i, hasGroup, names }
      for (let k = i; k < j; k++) runOf[k] = sid
      i = j
    }
    return { runs, runOf }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows])

  const bubbleFor = (m, i) => {
    const next = rows[i + 1]
    const d = (m.ts || '').slice(0, 10)
    // 连发只留队尾头像；busy 指示器在场=队伍还没完，最后一条 AI 气泡也让位，
    // 头像由指示器接棒（否则双头像）
    const grouped = !!(next && (next.ts || '').slice(0, 10) === d && next.role === m.role)
      || !!(!next && typing && m.role !== 'user')
    return (
      <Bubble key={m._key || m.id} m={m} grouped={grouped} mode={mode} avatars={avatars}
        expanded={expId === m.id} copied={copied === m.id}
        reacts={reacts[m.id]}
        onToggle={() => setExpId(cur => (cur === m.id ? null : m.id))}
        onOpenMenu={openMenu}
        onQuote={startQuote}
        onLightbox={setLb}
        onTextView={setTv}
        onRetry={retry}
        onReact={(id, emoji, content) => { react(id, emoji, content); setMenu(null) }}
        onCopy={copyMsg} />
    )
  }

  let lastDay = ''
  const items = []
  let tray = null       // 展开中的折叠段托盘（消息挂进去）
  let dedupPrev = null  // 幽灵去重参照：同人同文同一时刻、id 不同=换窗重入库的分身
  rows.forEach((m, i) => {
    // 贴表情通知是发给机的旁白：用户自己刚点的表情，页面上不再复述
    if (m.role === 'user' && typeof m.content === 'string' && m.content.startsWith('[reaction]')) return
    // 幽灵去重：换窗时同一条消息会以新指纹重进档案，IDB 里新旧 id 并存。
    // 同 role+同 sender+同内容且时间差 <8s 的相邻分身只留第一个
    if (dedupPrev && m.id !== dedupPrev.id
      && m.role === dedupPrev.role
      && (m.content || '') === (dedupPrev.content || '')
      && (m.sender || '') === (dedupPrev.sender || '')
      && Math.abs((new Date(m.ts).getTime() || 0) - (new Date(dedupPrev.ts).getTime() || 0)) < 8000) return
    dedupPrev = m

    const runId = foldRuns.runOf[i]
    const run = runId !== undefined ? foldRuns.runs[runId] : null
    const closed = run ? !!foldClosed[runId] : false
    if (!run) tray = null
    if (run && run.start === i) {
      const primary = run.hasGroup ? '群聊' : '独处提醒'
      const detail = run.hasGroup ? run.names.join('、') : run.count + ' 条'
      const txt = primary + (detail ? ' · ' + detail : '')
        + (closed && run.hasGroup ? ' · ' + run.count + ' 条' : '')
      // 段容器：sticky 折叠线以它为界，滚过段尾自动松手
      const seg = []
      items.push(<div key={'seg-' + runId} className="fold-seg">{seg}</div>)
      seg.push(
        <div key="line" className="fold-line"
          onClick={() => setFoldClosed(prev => ({ ...prev, [runId]: !prev[runId] }))}>
          <span className="fold-arrow">{closed ? '▸' : '▾'}</span>
          <span className="fold-txt">{txt}</span>
          <span className="fold-rule" />
          <span className="fold-stars">✦ ✧ ✦</span>
        </div>,
      )
      if (!closed) {
        tray = []
        seg.push(<div key="tray" className="fold-tray"><div className="fold-tex" />{tray}</div>)
      }
    }
    if (run && closed) return // 收起段：只留折叠线

    const sink = tray || items
    const d = (m.ts || '').slice(0, 10)
    if (d && d !== lastDay) {
      lastDay = d
      sink.push(<div key={'day-' + d + i} className="cb-day">{d}</div>)
    }
    sink.push(bubbleFor(m, i))
  })

  return (
    <div className="chat-app" style={{ '--comp-extra': compExtra + 'px' }}>
      <div className="chat-wallpaper" style={{ backgroundImage: cssUrl(wall) }} />
      <div className="chat-frost" ref={frostRef} />
      {offline && <div className="chat-offline">离线 · 显示的是本地记录</div>}
      <Music />
      <button className="chat-menu-btn" aria-label="menu" onClick={() => setSide(true)}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="4" y1="7" x2="20" y2="7" /><line x1="4" y1="12" x2="20" y2="12" /><line x1="4" y1="17" x2="20" y2="17" />
        </svg>
      </button>
      {loadingOlder && <div className="hist-spin"><span className="hist-spin-ring" /> 加载更早的消息</div>}
      {loadingNewer && <div className="hist-spin hist-spin--btm"><span className="hist-spin-ring" /> 加载后面的消息</div>}
      {inArchive && !loadingNewer && (
        <div className="chat-now-pill" onClick={() => { stick.current = true; exitArchive() }}>回到现在
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
        </div>
      )}
      <div className={'chat-log' + (doc ? ' chat-log--doc' : '')} ref={logRef} onScroll={onScroll}
        style={docPad || compExtra
          ? { paddingBottom: docPad ? (docPad + compExtra) + 'px' : `calc(${74 + compExtra}px + env(safe-area-inset-bottom, 0px))` }
          : undefined}>
        {items.length === 0 && !typing && (
          <div className="chat-empty">
            <div className="chat-empty-title">还没有消息</div>
            <div className="chat-empty-hint">桥启动后 Claude 会话会自动就绪，在下面输入框说第一句话，或直接在终端里聊，两边都会出现在这里</div>
          </div>
        )}
        {items}
        {typing && <TypingRow doc={doc} avatar={avatars.ai} />}
      </div>
      <div className="chat-scroll-down" style={{ opacity: showDown ? 0.95 : 0, pointerEvents: showDown ? 'auto' : 'none' }}
        onClick={() => { const el = logRef.current; if (el) el.scrollTop = el.scrollHeight }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9" /></svg>
      </div>
      <div className="chat-composer-wrap" ref={compWrapRef}>
        <Composer api={composerApi} quote={quote} taRef={taRef} doc={doc}
          onFocus={onTaFocus}
          onClearQuote={() => setQuote(null)}
          onSubmit={submit}
          onOpenSticker={() => setSticker(true)}
          onOpenPicker={() => setPicker(true)} />
      </div>
      {menu && (
        <ContextMenu menu={menu} reacts={reacts} quicks={quicks}
          onReact={(id, emoji, content) => { react(id, emoji, content); setMenu(null) }}
          onAddQuick={addQuick}
          onClose={() => setMenu(null)} />
      )}
      {lb && <Lightbox src={lb} onClose={() => setLb(null)} />}
      {tv && <TextView text={tv} onClose={() => setTv(null)} />}
      {askLive && !askMin && (
        <AskSheet ask={askLive}
          onClose={() => { setAskDone(askLive.id); setAsk(null); setAskMin(false) }}
          onMinimize={() => setAskMin(true)} />
      )}
      {askLive && askMin && (
        <div className="ask-pill" onClick={() => setAskMin(false)}>✦ 有一道选择题等你答</div>
      )}
      {sticker && <StickerPanel onSend={sendSticker} onClose={() => setSticker(false)} />}
      {picker && (
        <ImagePicker onConfirm={confirmPicker} onClose={() => setPicker(false)}
          onBrowse={() => { /* 浏览文件走 Composer 的图片input：提示用+号 */ setPicker(false) }} />
      )}
      {side && (
        <Sidebar mode={mode} theme={theme} offline={offline}
          onClose={() => setSide(false)}
          onToggleMode={toggleMode}
          onCycleTheme={cycleTheme}
          // 侧栏不自动关：让"已更换/上传失败"的小字提示能被看到
          onLookChange={() => setLookVer(v => v + 1)}
          onOpenMusic={() => { setSide(false); openFull() }} />
      )}
    </div>
  )
}
