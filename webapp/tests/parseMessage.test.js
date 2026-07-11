import { describe, it, expect } from 'vitest'
import { parseMessage } from '../src/chat/parseMessage.js'
import { CFG } from '../src/lib/api.js'

describe('parseMessage', () => {
  it('引用行拆出', () => {
    const p = parseMessage({ role: 'user', content: '> 原话在此\n正文' })
    expect(p.quote).toBe('原话在此')
    expect(p.body).toBe('正文')
  })
  it('上传图片引用转附件并从正文剥离', () => {
    const p = parseMessage({ role: 'user', content: '[图片] /up/x/a.png\n看这张' })
    expect(p.attImgs).toHaveLength(1)
    expect(p.attImgs[0].src).toContain('/files/a.png')
    expect(p.body).toBe('看这张')
  })
  it('贴纸消息', () => {
    const p = parseMessage({ role: 'assistant', content: '[sticker:cat.png]' })
    expect(p.stickerFile).toBe('cat.png')
    expect(p.pureSticker).toBe(true)
  })
  it('music 标记(全角冒号也认)', () => {
    const p = parseMessage({ role: 'assistant', content: '[music:123：歌名：歌手]' })
    expect(p.music).toEqual({ id: '123', title: '歌名', artist: '歌手', cover: '' })
    expect(p.body).toBe('')
  })
  it('channel 消息判成TG群且左对齐', () => {
    const p = parseMessage({ role: 'channel', sender: '1000000001', content: 'hi', from_name: '朋友' })
    expect(p.tgOn).toBe(true)
    expect(p.groupOther).toBe(true)
    expect(p.me).toBe(false)
    expect(p.tgText).toContain('朋友')
  })
  it('自己的TG消息(无别人名字)不判外人', () => {
    const p = parseMessage({ role: 'user', telegram: 'private', content: 'hi' })
    expect(p.tgOn).toBe(true)
    expect(p.groupOther).toBe(false)
    expect(p.me).toBe(true)
  })
  it('markdown 图片提为内联图', () => {
    const p = parseMessage({ role: 'assistant', content: '![alt](https://x.com/a.png)' })
    expect(p.img).toBe('https://x.com/a.png')
    expect(p.body).toBe('')
  })
  it('普通消息什么都不误判', () => {
    const p = parseMessage({ role: 'assistant', content: '就是普通话 [不是sticker] a|b' })
    expect(p.stickerFile).toBe('')
    expect(p.music).toBeNull()
    expect(p.attImgs).toHaveLength(0)
    expect(p.body).toContain('普通话')
  })
  it('贴纸三种形态都渲染成图', () => {
    const piped = parseMessage({ role: 'user', content: '[sticker:kiss.jpg|贴贴|两只猫猫亲亲]' })
    expect(piped.stickerFile).toBe('kiss.jpg')
    expect(piped.pureSticker).toBe(true)
    const zh = parseMessage({ role: 'user', content: '[贴纸 kiss.jpg「贴贴」：两只猫猫亲亲]' })
    expect(zh.stickerFile).toBe('kiss.jpg')
    expect(zh.pureSticker).toBe(true)
    const en = parseMessage({ role: 'user', content: '[sticker cat.png "happy": paw on hand]' })
    expect(en.stickerFile).toBe('cat.png')
  })

  it('代码区里的功能标记不被当真', () => {
    const r = parseMessage({ role: 'assistant', content: '把 `[sticker:xxx]` 翻译掉' })
    expect(r.stickerFile).toBe('')
    expect(r.body).toContain('[sticker:xxx]')
    const f = parseMessage({ role: 'assistant', content: '```\n[[voice:abcdef1234]]\n[sticker:cat.png]\n```' })
    expect(f.voiceId).toBe('')
    expect(f.stickerFile).toBe('')
    // 代码区外的照常提取
    const ok = parseMessage({ role: 'assistant', content: '`说明` [sticker:cat.png]' })
    expect(ok.stickerFile).toBe('cat.png')
    // 代码区内外同款标记：只切除外面那个，代码示例原样保留
    const both = parseMessage({ role: 'assistant', content: '例子 `[sticker:cat.png]` 真发 [sticker:cat.png]' })
    expect(both.stickerFile).toBe('cat.png')
    expect(both.body).toContain('`[sticker:cat.png]`')
  })

  it('语音标记提取voiceId且不进正文', () => {
    const r = parseMessage({ role: 'assistant', content: '晚安 [[voice:abcdef1234567890]]' })
    expect(r.voiceId).toBe('abcdef1234567890')
    expect(r.body).toBe('晚安')
    const pure = parseMessage({ role: 'assistant', content: '[[voice:abcdef1234567890]]' })
    expect(pure.pureVoice).toBe(true)
  })

  it('legacyStripTags声明的遗留控制标签剥离不进正文(闭合/未闭合尾部;默认不剥)', () => {
    expect(parseMessage({ role: 'assistant', content: '<tone>alpha</tone>生气了' }).body).toContain('<tone>')
    CFG.legacyStripTags = ['tone']
    try {
      expect(parseMessage({ role: 'assistant', content: '<tone>alpha</tone>生气了' }).body).toBe('生气了')
      expect(parseMessage({ role: 'assistant', content: '晚安<tone>beta' }).body).toBe('晚安')
      expect(parseMessage({ role: 'assistant', content: '正文里写 <tone> 这个词' }).body).toContain('<tone>')
    } finally {
      delete CFG.legacyStripTags
    }
  })
  it('代码区里的markdown图片是示例不是图;多张全提取', () => {
    const r = parseMessage({ role: 'assistant', content: '气泡认 `![](url)` 格式:\n\n![引导](https://x.y/a.png)\n\n![须知](https://x.y/b.png) 完' })
    expect(r.img).toBe('https://x.y/a.png')
    expect(r.attImgs.map(a => a.src)).toContain('https://x.y/b.png')
    expect(r.body).toContain('`![](url)`')
    expect(r.body).not.toContain('a.png')
    expect(r.body).toContain('完')
  })
})
