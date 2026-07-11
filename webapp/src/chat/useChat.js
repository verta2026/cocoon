// 轮询与发送的状态钩子：local echo 去重、since 水位、busy/offline、IDB 水合，
// 逻辑从 chat.html poll()/doSend()/init 链原样移植。
import { useEffect, useRef, useState, useCallback } from 'react'
import { API, HEADERS, ID, fetchChat, sendText, ensureCookie, ensureSession, loadPrivateConfig } from '../lib/api.js'
import { openDb, idbAll, idbPut } from '../lib/idb.js'

const byTime = (a, b) => {
  const ta = new Date(a.ts).getTime() || 0
  const tb = new Date(b.ts).getTime() || 0
  return ta - tb || (a.id < b.id ? -1 : 1)
}

export function useChat() {
  const [rows, setRows] = useState([])
  const [typing, setTyping] = useState(false)
  const [offline, setOffline] = useState(false)
  const [ask, setAsk] = useState(null)
  const [reacts, setReacts] = useState({})
  const seen = useRef(new Set())
  const maxId = useRef('')
  const polling = useRef(false)
  const lastSend = useRef(0)
  const pollCount = useRef(0)
  // 档案模式：从 history 页跳进某条旧消息，视图变成"以那条为中心的窗口"，
  // 上下都能翻页；轮询只进 IDB 不进视图，"回到现在"一键回到活水
  const archive = useRef(false)
  const [inArchive, setInArchive] = useState(false)
  const newestCur = useRef('')
  const histMoreAfter = useRef(false)
  const [jumpHl, setJumpHl] = useState('')

  const poll = useCallback(async () => {
    if (polling.current) return
    polling.current = true
    try {
      const d = await fetchChat(maxId.current)
      let fresh = (d.messages || []).filter(m => !seen.current.has(m.id))
      // 档案模式：新消息照常入库存水位（回来时不缺账），但不进当前视图——
      // 她正读三月，七月的消息突然接在窗口底下会把"往下翻页"的语义打穿
      if (fresh.length && archive.current) {
        idbPut(fresh)
        fresh.forEach(m => { if (m.id > maxId.current) maxId.current = m.id })
        fresh = []
      }
      if (fresh.length) {
        idbPut(fresh)
        fresh.forEach(m => {
          seen.current.add(m.id)
          if (m.id > maxId.current) maxId.current = m.id
          if (hydrated.current) m._fresh = true
        })
        setRows(prev => {
          const next = prev.slice()
          const skip = {}
          // 服务器回流的自己消息认领 local echo，不闪双条
          fresh.forEach(m => {
            if (m.role !== 'user') return
            const mc = (m.content || '').trim()
            for (let i = next.length - 1; i >= 0; i--) {
              if (String(next[i].id).startsWith('local-') && (next[i].content || '').trim() === mc) {
                // _key 钉住渲染身份：认领换 id 不重建 DOM 行（重建会重放渐入动画=闪一下）
                next[i] = { ...next[i], id: m.id, ts: m.ts, _key: next[i]._key || next[i].id }
                skip[m.id] = true
                break
              }
            }
          })
          const add = fresh.filter(m => !skip[m.id])
          return add.length ? next.concat(add).sort(byTime) : next
        })
      }
      setOffline(false)
      setTyping(!!d.busy)
      // 只在 id 变化时换引用，避免每轮轮询都重渲染弹窗
      setAsk(prev => {
        const next = d.ask || null
        return (prev && next && prev.id === next.id) ? prev : next
      })
      pollCount.current++
      if (pollCount.current % 5 === 0) {
        fetch(API + '/reactions', { headers: HEADERS })
          .then(r => (r.ok ? r.json() : null))
          .then(rd => { if (rd) setReacts(rd) })
          .catch(() => {})
      }
    } catch (e) {
      setOffline(true)
      setTyping(false)
    }
    polling.current = false
  }, [])

  const [cfgReady, setCfgReady] = useState(false)
  const hydrated = useRef(false)

  // 初始化链从 chat.html 移植：cookie 自愈 → 私配叠加 → IDB 离线水合 →
  // 幂等启动 → 首轮轮询。断网打开页面也能看到本地记录。
  useEffect(() => {
    let iv
    // 本地水合先行：IDB 是零延迟本地库，不许排在 cookie/私配两趟网络往返
    // 后面——高延迟链路+硬刷新(无HTTP缓存)时那就是十秒白屏。缓存先上屏，
    // 网络链(cookie→私配→会话→轮询)随后接力
    openDb()
      .then(() => idbAll())
      .then(cached => {
        cached.forEach(r => {
          if (r.id > maxId.current) maxId.current = r.id
        })
        // 开屏只渲染最近 80 条（chat_v2 同款）：IDB 里翻页攒下的几千条历史
        // 全量怼进 DOM 是首屏"清屏"级卡顿的主根；更早的靠上滑翻页取回。
        // seen 只标"真正上屏的"——把整个缓存标已见会让翻页去重闸把
        // 拿回来的旧页全扔掉，上滑永久卡死（实锤过一次）
        const recent = cached.sort(byTime).slice(-80)
        recent.forEach(r => seen.current.add(r.id))
        if (recent.length) setRows(recent)
        hydrated.current = true
        return ensureCookie()
      })
      .then(() => loadPrivateConfig())
      .then(() => {
        setCfgReady(true)
        fetch(API + '/reactions', { headers: HEADERS })
          .then(r => (r.ok ? r.json() : {}))
          .then(d => setReacts(d || {}))
          .catch(() => {})
        return ensureSession()
      })
      .then(() => poll())
    iv = setInterval(poll, 3000)
    return () => clearInterval(iv)
  }, [poll])

  const send = useCallback((text, quote, atts) => {
    const now = Date.now()
    if (now - lastSend.current < 600) return false
    lastSend.current = now
    const pending = atts || []
    let out = text.trim()
    if (!out && !pending.length) return false
    if (quote) out = '> ' + quote.split('\n')[0].slice(0, 80) + '\n' + out
    const uploaded = pending.filter(a => a.serverPath)
    if (uploaded.length) {
      const refs = uploaded.map(a => (a.isImage ? '[图片]' : '[文件]') + ' ' + a.serverPath).join('\n')
      out = out ? refs + '\n' + out : refs
    }
    if (!out) return true
    const fire = () => {
      const sendAtts = pending.map(a => ({ is_image: !!a.thumb, src: a.thumb || '', name: a.name }))
      const local = { id: 'local-' + now, role: 'user', content: out, ts: new Date().toISOString(), attachments: sendAtts, _fresh: true }
      setRows(prev => prev.concat(local))
      sendText(out)
        .then(async r => {
          // /send 用 200 + {sent:false} 表示"没送进终端"（TUI 还没画好等）——
          // 只看 r.ok 会把丢掉的消息当成功，气泡永远不长失败标
          const j = await r.json().catch(() => ({}))
          if (r.ok && j.sent !== false) poll()
          else throw 0
        })
        .catch(() => {
          setRows(prev => prev.map(m => (m.id === local.id ? { ...m, failed: true } : m)))
        })
    }
    // 在档案窗口里发消息：先回到活水再发——本地回显落在旧窗口里会永远等不到认领
    if (archive.current) exitArchiveRef.current().then(fire)
    else fire()
    return true
  }, [poll])

  const rowsRef = useRef(rows)
  rowsRef.current = rows

  // 云端历史分页：上滑到顶时向 /chat_history_page 要更早的 50 条（chat_v2 loadOlder 同款）
  const histLoading = useRef(false)
  const histMore = useRef(true)
  const oldest = useRef('')
  const [loadingOlder, setLoadingOlder] = useState(false)
  // 翻页锚点：prepend 前量好高度，交给 Chat 的 useLayoutEffect 在绘制前补偿。
  // rAF 补偿在编译器/并发提交下可能赶在 React 落地前量高度——量了个寂寞，视线直接跳走
  const histAnchor = useRef(null)
  const loadOlder = useCallback(async logEl => {
    if (histLoading.current || !histMore.current) return
    if (!oldest.current) {
      const f0 = rowsRef.current[0]
      if (f0 && f0.id) oldest.current = f0.id
    }
    if (!oldest.current) return
    histLoading.current = true
    setLoadingOlder(true)
    try {
      const r = await fetch(API + '/chat_history_page?before=' + encodeURIComponent(oldest.current) + '&limit=50', { headers: HEADERS })
      if (!r.ok) throw new Error(r.status)
      const d = await r.json()
      const older = (d.messages || []).filter(m => !seen.current.has(m.id))
      histMore.current = !!d.has_more
      if (!older.length) return
      idbPut(older)
      older.forEach(m => seen.current.add(m.id))
      if (logEl) histAnchor.current = { el: logEl, prevH: logEl.scrollHeight, prevTop: logEl.scrollTop }
      setRows(prev => older.concat(prev).sort(byTime))
      oldest.current = ''
    } catch (e) {
      /* 失败不锁死，下次上滑再试 */
    } finally {
      histLoading.current = false
      setLoadingOlder(false)
    }
  }, [])

  // 跳转定位：以目标消息为中心开一扇 80 条的窗（history 页点记录进来）
  const jumpTo = useCallback(async id => {
    if (histLoading.current) return
    histLoading.current = true
    setLoadingOlder(true)
    try {
      const r = await fetch(API + '/chat_history_page?around=' + encodeURIComponent(id) + '&limit=80', { headers: HEADERS })
      if (!r.ok) throw new Error(r.status)
      const d = await r.json()
      const page = d.messages || []
      if (!page.length) return
      archive.current = true
      setInArchive(true)
      seen.current = new Set(page.map(m => m.id))
      oldest.current = page[0].id
      newestCur.current = page[page.length - 1].id
      histMore.current = !!d.has_more
      histMoreAfter.current = !!d.has_more_after
      setRows(page)
      setJumpHl(d.target || id)
    } catch (e) {
      /* 桥没重启时端点不存在：静默失败，history 页会给提示 */
    } finally {
      histLoading.current = false
      setLoadingOlder(false)
    }
  }, [])

  // 档案模式向下翻页：滑到窗口底部时取更新的 50 条
  const [loadingNewer, setLoadingNewer] = useState(false)
  const loadNewer = useCallback(async () => {
    if (!archive.current || histLoading.current || !histMoreAfter.current || !newestCur.current) return
    histLoading.current = true
    setLoadingNewer(true)
    try {
      const r = await fetch(API + '/chat_history_page?after=' + encodeURIComponent(newestCur.current) + '&limit=50', { headers: HEADERS })
      if (!r.ok) throw new Error(r.status)
      const d = await r.json()
      const newer = (d.messages || []).filter(m => !seen.current.has(m.id))
      histMoreAfter.current = !!d.has_more_after
      if (!newer.length) return
      newer.forEach(m => seen.current.add(m.id))
      newestCur.current = newer[newer.length - 1].id
      // 往下 append 不动视线，不需要滚动补偿
      setRows(prev => prev.concat(newer).sort(byTime))
    } catch (e) {
      /* 失败不锁死 */
    } finally {
      histLoading.current = false
      setLoadingNewer(false)
    }
  }, [])

  // 回到现在：退出档案模式，从 IDB 水合最近 80 条回到活水
  const exitArchiveRef = useRef(async () => {})
  const exitArchive = useCallback(async () => {
    archive.current = false
    setInArchive(false)
    histMoreAfter.current = false
    newestCur.current = ''
    setJumpHl('')
    const cached = await idbAll()
    const recent = cached.sort(byTime).slice(-80)
    seen.current = new Set(recent.map(r => r.id))
    oldest.current = ''
    histMore.current = true
    setRows(recent)
    poll()
  }, [poll])
  exitArchiveRef.current = exitArchive

  const retry = useCallback(msg => {
    setRows(prev => prev.map(m => (m.id === msg.id ? { ...m, failed: false } : m)))
    sendText(msg.content)
      .then(async r => {
        const j = await r.json().catch(() => ({}))
        if (r.ok && j.sent !== false) poll()
        else throw 0
      })
      .catch(() => {
        setRows(prev => prev.map(m => (m.id === msg.id ? { ...m, failed: true } : m)))
      })
  }, [poll])

  const react = useCallback((id, emoji, content) => {
    const src = content || (rowsRef.current.find(m => m.id === id) || {}).content || ''
    const preview = src.replace(/\n/g, ' ').slice(0, 40)
    fetch(API + '/reactions', {
      method: 'POST',
      headers: HEADERS,
      body: JSON.stringify({ msg_id: id, emoji, from: ID.userId, preview }),
    })
      .then(r => r.json())
      .then(d => { if (d.ok) setReacts(d.reactions || {}) })
      .catch(() => {})
  }, [])

  return {
    rows, typing, offline, reacts, cfgReady, send, retry, react, loadOlder, loadingOlder, histAnchor,
    jumpTo, loadNewer, loadingNewer, exitArchive, inArchive, jumpHl, setJumpHl, ask, setAsk,
  }
}
