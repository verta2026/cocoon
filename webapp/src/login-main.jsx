import { createRoot } from 'react-dom/client'
import Login from './login/Login.jsx'

const CFG = window.CFG || {}
if (CFG.siteName) document.title = CFG.siteName

createRoot(document.getElementById('root')).render(<Login />)
