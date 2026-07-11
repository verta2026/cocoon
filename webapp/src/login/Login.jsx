import { useState } from 'react'
import './login.css'

const CFG = window.CFG || {}
const NS = CFG.storageNs || 'cocoon'

async function check(pw) {
  const res = await fetch('/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: pw }),
  })
  if (!res.ok) return false
  // Cookie-based deployments return {ok}; token-based ones also return
  // {token} for the page to store for the bridge API.
  try {
    const data = await res.json()
    if (data && data.token) localStorage.setItem(NS + '_token', data.token)
  } catch (e) {}
  return true
}

// 只允许站内相对路径：拒绝 scheme（javascript:/https: 等）、//、反斜杠——
// 否则 ?next= 是登录后必然执行的 DOM XSS / 开放重定向
function safeNext(raw, fallback) {
  if (!raw || raw[0] !== '/' || raw[1] === '/' || raw.indexOf('\\') > -1) return fallback
  return raw
}

export default function Login() {
  const [value, setValue] = useState('')
  const [error, setError] = useState(false)

  async function onKeyDown(e) {
    if (e.key !== 'Enter') return
    if (await check(value)) {
      location.href = safeNext(new URLSearchParams(location.search).get('next'), './')
    } else {
      setError(true)
      setValue('')
    }
  }

  return (
    <div className="container">
      <div className="dash">—</div>
      <input
        type="password"
        placeholder="..."
        autoFocus
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className={error ? 'hint error' : 'hint'}>{error ? '...' : ''}</div>
    </div>
  )
}
