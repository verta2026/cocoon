import { useState } from 'react'
import './login.css'

const CFG = window.CFG || {}
const NS = CFG.storageNs || 'cocoon'
// 与 api.js 同一旋钮：挂子路径反代（apiBase:'/test' 之类）时登录也走前缀
const API = CFG.apiBase !== undefined ? CFG.apiBase : ''

async function check(pw) {
  const res = await fetch(API + '/login', {
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

// 首访须知：读完才解锁输入框；确认后记在本地，之后不再弹
function noticeSeen() {
  try { return localStorage.getItem(NS + '_notice_ack') === '1' } catch (e) { return true }
}

export default function Login() {
  const [value, setValue] = useState('')
  const [error, setError] = useState(false)
  const [guide, setGuide] = useState(false)
  const [notice, setNotice] = useState(() => CFG.loginGuide !== false && !noticeSeen())

  function ackNotice() {
    try { localStorage.setItem(NS + '_notice_ack', '1') } catch (e) {}
    setNotice(false)
    setTimeout(() => document.querySelector('input')?.focus(), 50)
  }

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
      {notice && (
        <div className="notice-ov">
          <div className="notice-card">
            <div className="notice-title">开始之前</div>
            <ul>
              <li><strong>token 不要给任何人。</strong>拿到 token 的人可以在你的服务器上执行任意命令，等于交出整台机器。</li>
              <li>这个前端是 <strong>Claude Code 的渲染界面</strong>，自带 forge 无缝换窗（上下文写满自动开新窗，对话不中断）。</li>
              <li>机在这里的能力和 Claude Code 完全相同。界面不顺手、想加功能、出了 bug——直接让机自己改。</li>
              <li>欢迎反馈 bug，欢迎二改。</li>
            </ul>
            <p className="notice-thanks">致谢 forge 作者：离落。</p>
            <button className="notice-btn" onClick={ackNotice}>读完了，输入 token</button>
          </div>
        </div>
      )}
      <div className="brand">cocoon</div>
      <div className="dash">—</div>
      <div className="label">请输入 token</div>
      <input
        type="password"
        placeholder="..."
        autoFocus={!notice}
        disabled={notice}
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className={error ? 'hint error' : 'hint'}>{error ? '...' : ''}</div>
      {CFG.loginGuide !== false && (
        <div className="guide">
          <button className="guide-toggle" onClick={() => setGuide(g => !g)}>
            {guide ? '收起' : '第一次用？'}
          </button>
          {guide && (
            <div className="guide-card">
              <p>这里要的是访问口令（token）。它在首次运行 <code>./start.sh</code> 时自动生成，只完整显示一次，之后存在服务器的 <code>cocoon/.env</code> 里：</p>
              <pre>grep COCOON_TOKEN .env</pre>
              <p>把它粘贴到上面的输入框，回车。登录状态会留在这个浏览器里。</p>
              <p>进来之后：聊天页侧栏 → 会话 → <code>new session</code> 启动 Claude；<code>/terminal</code> 能看原始终端。</p>
              <p>忘了口令：改 <code>.env</code> 里的 <code>COCOON_TOKEN</code> 再重启即可。</p>
              <div className="guide-sec">安全须知</div>
              <p>这个口令不是普通密码：拿到它的人可以指挥一个<strong>能在你服务器上执行命令</strong>的 Claude，等于交出整台机器。所以——</p>
              <p>· 只通过 HTTPS 或内网（Tailscale/SSH 隧道）访问，别把裸 HTTP 端口挂到公网；</p>
              <p>· 口令别发给任何人、别截进图里；</p>
              <p>· 怀疑泄露就立刻换：改 <code>.env</code> 重启，旧口令当场作废。</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
