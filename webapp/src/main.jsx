import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import Chat from './chat/Chat.jsx'
import History from './chat/History.jsx'
import { requireToken, CFG } from './lib/api.js'

if (CFG.siteName) document.title = CFG.siteName

// 极简 hash 路由：history 是覆盖页，Chat 常驻不卸载——
// 返回时零重启动，跳转事件也不用跨挂载周期传递
function App() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const h = () => setHash(window.location.hash)
    window.addEventListener('hashchange', h)
    return () => window.removeEventListener('hashchange', h)
  }, [])
  return (
    <>
      <Chat />
      {hash === '#/history' && <History />}
    </>
  )
}

if (requireToken()) {
  createRoot(document.getElementById('root')).render(<App />)
}
