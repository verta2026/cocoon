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

  // markdown 图片同样只认代码区外的（反引号里的 ![](url) 是示例不是图），
  // 且全部提取——一条消息可以带多张。裸 /files/ 路径补 API 前缀，
  // 子路径部署（apiBase 非空）下才打得到桥
  const withApi = (u) => (u.startsWith('/files/') ? API + u : u)
  let img = ''
  const mdImgRe = /!\[[^\]]*\]\(([^)\s]+)\)/
  let mdImg
  while ((mdImg = matchOutsideCode(body, mdImgRe))) {
    if (!img) img = withApi(mdImg[1])
    else uploadAtts.push({ is_image: true, src: withApi(mdImg[1]), name: '' })
    body = cutMatch(body, mdImg)
  }
  if (!img) {
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
  // 服务端显示层的单括号语音标记 [bondvoice:<hex>]（bridge_display 为旧 DOM
  // 覆盖层生成的形态，存量历史消息里都是它）。语音条由 voiceId 原生渲染，
  // 标记全剥掉；一条消息可能带多个（通话行引用旧语音），只认第一个
  let bv
  while ((bv = matchOutsideCode(body, /\[bondvoice:([a-f0-9]{8,64})\]/))) {
    if (!voiceId) voiceId = bv[1]
    body = cutMatch(body, bv)
  }
  // 她的语音输入 / 通话录音：[voice:<文件名>:<秒数>]，音频在 /files/ 下
  let fileVoice = null
  let fv
  while ((fv = matchOutsideCode(body, /\[voice:([^\]:\s]+):?(\d*)\]/))) {
    if (!fileVoice) fileVoice = { file: fv[1], dur: parseInt(fv[2], 10) || 0 }
    body = cutMatch(body, fv)
  }
  // 思考折叠标记 [[thinking:<id>]]：Bubble 渲染成可展开思考条，全文按需拉
  let thinkingId = ''
  const tkMatch = matchOutsideCode(body, /\[\[thinking:([0-9a-fA-F\-:]+)\]\]\s*/)
  if (tkMatch) { thinkingId = tkMatch[1]; body = cutMatch(body, tkMatch) }

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
    kind, me, body, quote: q, img, stickerFile, music, voiceId, fileVoice, thinkingId,
    attImgs: allAtts.filter(a => a.is_image),
    attFiles: allAtts.filter(a => !a.is_image),
    tgOn, tgGroup, tgWho, tgChat, tgText, groupOther, senderColor,
    pureSticker: !!stickerFile && !body && !q && !img,
    pureVoice: (!!voiceId || !!fileVoice) && !body && !q && !img && !stickerFile,
  }
}
