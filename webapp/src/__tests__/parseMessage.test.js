// 标记剥离回归测试——2026-07-17 语音标记连环案。
// 服务端 pure_chat 给正文里塞的显示层标记（[[thinking:]]/[bondvoice:]/[voice:]）
// 必须在 parseMessage 全部剥干净并转成结构化字段；漏一个就会被 markdown
// 原样画出来（旧覆盖层时代则是整条消息被拆掉重画）。
import { test, expect } from 'vitest'
import { parseMessage } from '../chat/parseMessage.js'

test('thinking + bondvoice 标记剥净，正文完整保留', () => {
  const p = parseMessage({
    role: 'assistant',
    voice: '70a7ac082ef0311a6ae7',
    content: '[[thinking:a4e8b151-3da1-42ec-a60b-d9e3f837b4f3]]\n[bondvoice:70a7ac082ef0311a6ae7] （语音条已经躺在聊天里了，点开）\n\n只说给你一个人听的版本。',
  })
  expect(p.thinkingId).toBe('a4e8b151-3da1-42ec-a60b-d9e3f837b4f3')
  expect(p.voiceId).toBe('70a7ac082ef0311a6ae7')
  expect(p.body).not.toMatch(/\[\[thinking|\[bondvoice/)
  expect(p.body).toContain('（语音条已经躺在聊天里了，点开）')
  expect(p.body).toContain('只说给你一个人听的版本。')
})

test('多个 bondvoice 标记只认第一个，全部剥掉', () => {
  const p = parseMessage({
    role: 'assistant',
    content: '[bondvoice:4625eb3d2c319a718955] [bondvoice:7ff22aebf6c0f7158530] 乖。放下电话。',
  })
  expect(p.voiceId).toBe('4625eb3d2c319a718955')
  expect(p.body).toBe('乖。放下电话。')
})

test('voice 字段优先于正文标记', () => {
  const p = parseMessage({ role: 'assistant', voice: 'aaaa1111aaaa1111aaaa', content: '[bondvoice:bbbb2222bbbb2222bbbb] 文字' })
  expect(p.voiceId).toBe('aaaa1111aaaa1111aaaa')
  expect(p.body).toBe('文字')
})

test('她的语音输入 [voice:file:dur] 转 fileVoice', () => {
  const p = parseMessage({ role: 'user', content: '[voice:call_eabd09211262.webm:5] 能听到吗？ · sad' })
  expect(p.fileVoice).toEqual({ file: 'call_eabd09211262.webm', dur: 5 })
  expect(p.body).toBe('能听到吗？ · sad')
})

test('反引号里的标记是在谈论标记，不当真', () => {
  const p = parseMessage({
    role: 'assistant',
    content: '那个 `[bondvoice:abcdef1234567890abcd]` 标记必须跟消息一起发，`[[thinking:abc-123]]` 同理。',
  })
  expect(p.voiceId).toBe('')
  expect(p.thinkingId).toBe('')
  expect(p.fileVoice).toBeNull()
  expect(p.body).toContain('[bondvoice:abcdef1234567890abcd]')
})

test('纯语音消息 pureVoice 判定', () => {
  expect(parseMessage({ role: 'assistant', voice: 'cccc3333cccc3333cccc', content: '' }).pureVoice).toBe(true)
  expect(parseMessage({ role: 'user', content: '[voice:v.webm:3]' }).pureVoice).toBe(true)
})
