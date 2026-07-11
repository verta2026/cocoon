// 消息体解析，从 chat.html renderMessages 前半段原样移植成纯函数。
// 判定正则一字未动；输入一条原始消息，输出渲染所需的全部要素。
import { API, CFG, ID } from '../lib/api.js'

// 代码区蒙版：把围栏和行内代码里的内容换成等长占位符。功能标记
// （贴纸/语音/音乐）只在蒙版后的文本上匹配——反引号里的 [sticker:xxx]
// 是在"谈论"标记而不是在"使用"标记，不能被抠走当真贴纸加载
const maskCode = t => t.replace(/```[\s\S]*?```|`[^`\n]*`/g, m => '\x00'.repeat(m.length))
// 在代码区外找标记；蒙版等长，命中位置在原文上重取分组
function matchOutsideCode(text, re) {
  const masked = maskCode(text).match(re)
  if (!masked) return null
  const m = text.slice(masked.index).match(re)
  m.index = masked.index
  return m
}
// 按命中下标精确切除（字符串 replace 删的是第一处，代码区里的同款会被误删）
const cutMatch = (text, m) => (text.slice(0, m.index) + text.slice(m.index + m[0].length)).trim()

// 语音气泡标记：[[voice:<音频id>]]。marker 词可由部署配置改（CFG.voiceMarker），
// 这样私有部署的历史消息里的旧标记不用迁移也能渲染
const VOICE_RE = new RegExp('\\[\\[' + (CFG.voiceMarker || 'voice') + ':([A-Za-z0-9_.\\-]{8,64})\\]\\]')

// 渠道消息发送者显示名：任何来源字段（用户名/数字 id）先过 channelNames 映射再兜底原文
export function channelWho(m) {
  const raw = m.from_name || m.fromName || m.tg_name || m.sender || ''
  return ID.channelNames[raw] || ID.channelNames[m.sender] || raw
}

export function parseMessage(m) {
  const kind = m.role === 'user' ? 'user'
    : m.role === 'channel' ? 'channel'
    : m.role === 'system' ? 'system' : 'assistant'

  let body = (m.content || '').replace(/^\s*\[\[solo\]\]\s*/, '')
  // 部署可声明要从历史正文里剥掉的遗留控制标签（CFG.legacyStripTags，默认无）
  for (const tag of CFG.legacyStripTags || []) {
    body = body
      .replace(new RegExp('<' + tag + '>\\s*\\w*\\s*</' + tag + '>', 'gi'), '')
      .replace(new RegExp('<' + tag + '>\\s*\\w*\\s*$', 'i'), '')
      .trim()
  }
  let q = ''
  if (body.slice(0, 2) === '> ') {
    const nl = body.indexOf('\n')
    if (nl > -1) { q = body.slice(2, nl); body = body.slice(nl + 1) }
    else { q = body.slice(2); body = '' }
  }

  const uploadAtts = []
  const uploadImgRe = /(?:^|\n)\[图片\]\s*\S*\/([\w.\-]+\.(?:jpg|jpeg|png|gif|webp|heic|bmp))/gi
  let um
  while ((um = uploadImgRe.exec(body))) {
    // 媒体鉴权靠 HttpOnly cookie（开机 /session 种下），URL 里永远不带 token
    uploadAtts.push({ is_image: true, src: API + '/files/' + encodeURIComponent(um[1]), name: um[1] })
  }
  if (uploadAtts.length) body = body.replace(uploadImgRe, '').trim()

  let img = ''
  const mdImg = body.match(/!\[[^\]]*\]\(([^)]+)\)/)
  if (mdImg) { img = mdImg[1]; body = body.replace(mdImg[0], '').trim() }
  else {
    const bare = body.trim().match(/^(https?:\/\/\S+\.(?:png|jpe?g|gif|webp)(?:\?\S*)?|data:image\/[^\s"']+)$/i)
    if (bare) { img = bare[1]; body = '' }
  }

  const fileAtts = []
  const uploadFileMatch = body.match(/(?:^|\n)\[文件\]\s*\S*\/([\w.\-]+)/)
  if (uploadFileMatch) {
    const name = uploadFileMatch[1]
    fileAtts.push({ is_image: false, name, src: API + '/files/' + encodeURIComponent(name) })
    body = body.replace(uploadFileMatch[0], '').trim()
  }

  let stickerFile = ''
  // 三种形态：[sticker:file]（裸）、[sticker:file|名字|描述]（自描述 wire 格式）、
  // 桥翻译形态 [sticker file "name": desc] / [贴纸 file「名字」：描述]（历史兼容）
  const sMatch = matchOutsideCode(body, /\[sticker:([^\]\n]+)\]/)
    || matchOutsideCode(body, /\[(?:sticker|贴纸)\s+([^\s\]"「]+)[^\]\n]*\]/)
  if (sMatch) { stickerFile = sMatch[1].split('|')[0].trim(); body = cutMatch(body, sMatch) }

  let voiceId = m.voice || ''
  const vMatch = matchOutsideCode(body, VOICE_RE)
  if (vMatch) { if (!voiceId) voiceId = vMatch[1]; body = cutMatch(body, vMatch) }

  let music = null
  const mMus = matchOutsideCode(body, /\[music:(\d+)[:：]([^:：]+)[:：]([^:：\]]+)(?:[:：]([^\]]*))?\]/)
  if (mMus) {
    music = { id: mMus[1], title: mMus[2], artist: mMus[3], cover: mMus[4] || '' }
    body = cutMatch(body, mMus)
  }

  const bodyFiles = []
  const fRe = /\[file:([^\]]+)\]\((data:[^)\s]+|https?:[^)\s]+)\)/g
  let fm
  while ((fm = fRe.exec(body))) bodyFiles.push({ is_image: false, name: fm[1], src: fm[2] })
  if (bodyFiles.length) body = body.replace(fRe, '').trim()

  const rawAtts = (m.attachments || []).concat(bodyFiles).concat(uploadAtts).concat(fileAtts)
  const attSeen = {}
  const allAtts = rawAtts.filter(a => {
    const key = a.name || a.src || ''
    if (attSeen[key]) return false
    attSeen[key] = true
    return true
  })

  const tgOn = /^(telegram|tg)$/i.test(m.via || m.source || m.platform || m.origin || '')
    || !!m.telegram || !!m.tg || kind === 'channel'
  const tgGroup = /group/i.test(m.chat_type || m.chatType || (kind === 'channel' ? 'group' : m.telegram) || '') || !!m.is_group
  const tgWho = channelWho(m)
  const tgChat = m.chat_title || m.chatTitle || m.chat_name || ''
  const tgText = tgOn
    ? ('✈ ' + (tgGroup
        ? ('群' + (tgChat ? '「' + tgChat + '」' : '') + (tgWho ? ' · ' + tgWho : ''))
        : ('Telegram · 私信' + (tgWho ? ' · ' + tgWho : ''))))
    : ''
  const groupOther = tgGroup && !!tgWho

  let me = kind === 'user'
  if (groupOther) me = false

  let senderColor = 'var(--c-accent)'
  if (groupOther) {
    let h = 0
    for (let i = 0; i < tgWho.length; i++) h = (h * 31 + tgWho.charCodeAt(i)) >>> 0
    senderColor = ['#B0562F', '#4C86A8', '#5F8A55', '#8E77B0', '#B58A3A', '#A34B7C', '#5B8C7B'][h % 7]
  }

  return {
    kind, me, body, quote: q, img, stickerFile, music, voiceId,
    attImgs: allAtts.filter(a => a.is_image),
    attFiles: allAtts.filter(a => !a.is_image),
    tgOn, tgGroup, tgWho, tgChat, tgText, groupOther, senderColor,
    pureSticker: !!stickerFile && !body && !q && !img,
    pureVoice: !!voiceId && !body && !q && !img && !stickerFile,
  }
}
