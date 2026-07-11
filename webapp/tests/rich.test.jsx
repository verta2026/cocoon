import { render } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import Rich from '../src/lib/rich.jsx'

const mount = text => render(<Rich text={text} />).container

describe('管道表', () => {
  it('带表头分隔行渲染成 table + 横滚容器', () => {
    const c = mount('前言\n| 名 | 值 |\n|---|---|\n| a | **b** |\n尾声')
    expect(c.querySelectorAll('table')).toHaveLength(1)
    expect(c.querySelectorAll('th')).toHaveLength(2)
    expect(c.querySelectorAll('td')).toHaveLength(2)
    expect(c.querySelector('.rc-table-scroll')).toBeTruthy()
    expect(c.querySelector('td strong')?.textContent).toBe('b')
    expect(c.textContent).toContain('前言')
    expect(c.textContent).toContain('尾声')
  })
  it('消息开头就是表格也能命中', () => {
    const c = mount('| a | b |\n|---|---|\n| 1 | 2 |')
    expect(c.querySelectorAll('table')).toHaveLength(1)
  })
  it('行内竖线不误判成表格', () => {
    const c = mount('管道 a | b 只是竖线\n第二行 c | d')
    expect(c.querySelectorAll('table')).toHaveLength(0)
  })
  it('无分隔行的假表格不误判', () => {
    const c = mount('| a | b |\n| c | d |')
    expect(c.querySelectorAll('table')).toHaveLength(0)
  })
})

describe('盒线表', () => {
  it('终端画线字符块渲染成等宽 pre', () => {
    const c = mount('┌──┬──┐\n│ a │ b │\n└──┴──┘')
    const pre = c.querySelector('pre.rc-boxtable')
    expect(pre).toBeTruthy()
    expect(pre.textContent).toContain('│ a │ b │')
  })
})

describe('块级 markdown', () => {
  it('标题/引用/列表/分隔线', () => {
    const c = mount('# 大标题\n> 引用行\n- 甲\n2) 乙\n---')
    expect(c.querySelector('.rc-h1')?.textContent).toBe('大标题')
    expect(c.querySelector('.rc-bq')?.textContent).toBe('引用行')
    const lis = c.querySelectorAll('.rc-li')
    expect(lis).toHaveLength(2)
    expect(lis[0].textContent).toBe('• 甲')
    expect(lis[1].textContent).toBe('2. 乙')
    expect(c.querySelector('.rc-hr')).toBeTruthy()
  })
  it('井号无空格不当标题(#3A6B7B 这类)', () => {
    const c = mount('#3A6B7B 是颜色')
    expect(c.querySelector('.rc-h1')).toBeFalsy()
  })
})

describe('行内', () => {
  it('code/粗体/删除线/斜体/高亮', () => {
    const c = mount('`x` **粗** ~~删~~ *斜* ==亮==')
    expect(c.querySelector('code')?.textContent).toBe('x')
    expect(c.querySelector('strong')?.textContent).toBe('粗')
    expect(c.querySelector('del')?.textContent).toBe('删')
    expect(c.querySelector('em')?.textContent).toBe('斜')
    expect(c.querySelector('mark')?.textContent).toBe('亮')
  })
  it('孤星号不误伤', () => {
    const c = mount('5 * 3 = 15')
    expect(c.querySelector('em')).toBeFalsy()
  })
  it('http 链接渲染为安全 a 标签', () => {
    const c = mount('[说明](https://example.com/x) 和 [相对](/files.html)')
    const as = c.querySelectorAll('a')
    expect(as).toHaveLength(2)
    expect(as[0].getAttribute('href')).toBe('https://example.com/x')
    expect(as[0].getAttribute('rel')).toBe('noopener')
  })
  it('代码围栏内原样保留不渲染', () => {
    const c = mount('```\n**不粗** | 不是表 |\n```')
    expect(c.querySelector('pre.rc-fence')?.textContent).toContain('**不粗**')
    expect(c.querySelector('strong')).toBeFalsy()
  })
})

describe('XSS 防线', () => {
  it('javascript: 伪链接不产出 a 标签', () => {
    const c = mount('[点我](javascript:alert(1))')
    expect(c.querySelectorAll('a')).toHaveLength(0)
    expect(c.textContent).toContain('[点我](javascript:alert(1))')
  })
  it('HTML 标签一律当文本', () => {
    const c = mount('<img src=x onerror=alert(1)> 与 <script>alert(1)</script>')
    expect(c.querySelector('img')).toBeFalsy()
    expect(c.querySelector('script')).toBeFalsy()
    expect(c.textContent).toContain('<img src=x onerror=alert(1)>')
  })
  it('表格单元格里的 HTML 也当文本', () => {
    const c = mount('| a |\n|---|\n| <b onclick=x>y</b> |')
    expect(c.querySelector('td b')).toBeFalsy()
    expect(c.querySelector('td').textContent).toContain('<b onclick=x>y</b>')
  })
})

describe('段落', () => {
  it('双换行产出间隔', () => {
    const c = mount('第一段\n\n第二段')
    expect(c.querySelectorAll('.rc-spacer')).toHaveLength(1)
  })
})
