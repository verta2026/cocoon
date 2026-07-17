// IndexedDB 离线缓存，从 chat.html openDb/idbAll/idbPut 移植。
// 断网时聊天记录仍可读；db 打不开时所有操作静默降级。
import { NS } from './api.js'

let db = null

function createStores(d) {
  if (!d.objectStoreNames.contains('messages')) d.createObjectStore('messages', { keyPath: 'id' })
  if (!d.objectStoreNames.contains('files')) d.createObjectStore('files', { keyPath: 'id' })
}

export function openDb() {
  return new Promise(res => {
    try {
      // 不带版本号打开：同名库可能被别的页面(chat_v2 用 v3)升过版本，
      // 定版打开会 VersionError→缓存整个静默死掉(不读不写,每次从0)。
      // 无版本号=跟随现有版本；缺 store 时才用 version+1 升级补建
      const q = indexedDB.open(NS + '_chat')
      q.onupgradeneeded = () => createStores(q.result)
      q.onsuccess = () => {
        const d = q.result
        if (d.objectStoreNames.contains('messages')) { db = d; return res(db) }
        const ver = d.version + 1
        d.close()
        const u = indexedDB.open(NS + '_chat', ver)
        u.onupgradeneeded = () => createStores(u.result)
        u.onsuccess = () => { db = u.result; res(db) }
        u.onerror = () => res(null)
      }
      q.onerror = () => res(null)
    } catch (e) { res(null) }
  })
}

export function idbAll() {
  return new Promise(res => {
    const out = []
    if (!db) return res(out)
    try {
      const tx = db.transaction('messages').objectStore('messages').openCursor()
      tx.onsuccess = () => { const c = tx.result; if (c) { out.push(c.value); c.continue() } else res(out) }
      tx.onerror = () => res(out)
    } catch (e) { res(out) }
  })
}

export function idbPut(rows) {
  if (!rows.length || !db) return
  try {
    const st = db.transaction('messages', 'readwrite').objectStore('messages')
    rows.forEach(r => st.put(r))
  } catch (e) {}
}

// 一次性缓存清创：服务端已修好的行（幽灵语音标记/改嫁 voice 字段/双 thinking），
// 缓存里落在尾部回声窗之外就永远得不到热更新——按标记整库清一次，
// 历史从云端翻页重新长回来（服务器是真源，清了不丢东西）
export function idbPurgeOnce(tag) {
  return new Promise(res => {
    if (!db) return res()
    try {
      if (localStorage.getItem(NS + '_msg_purge') === tag) return res()
      const st = db.transaction('messages', 'readwrite').objectStore('messages')
      const q = st.clear()
      q.onsuccess = () => { try { localStorage.setItem(NS + '_msg_purge', tag) } catch (e) {} res() }
      q.onerror = () => res()
    } catch (e) { res() }
  })
}
