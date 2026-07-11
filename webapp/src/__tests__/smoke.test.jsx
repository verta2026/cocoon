// 挂载冒烟测试：整页 render 一把，抓"纯色屏"级别的崩溃
import { render } from '@testing-library/react'
import { vi, test, expect } from 'vitest'

vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({}) })))

// 20s 限额：测试内动态 import 付的是整包 transform 的钱（慢机器上实测能到 6s+），
// 默认 5s 会把纯粹的编译耗时误判成挂载悬挂
test('Chat 挂载不炸', async () => {
  const { default: Chat } = await import('../chat/Chat.jsx')
  expect(() => render(<Chat />)).not.toThrow()
}, 20000)

test('History 挂载不炸', async () => {
  const { default: History } = await import('../chat/History.jsx')
  expect(() => render(<History />)).not.toThrow()
})

test('History 渲染月份折叠', async () => {
  fetch.mockImplementationOnce(() => Promise.resolve({
    ok: true,
    json: () => Promise.resolve({
      months: [{
        month: '2026-07', count: 3,
        days: [{ date: '2026-07-10', count: 3, first_id: '001-aa', preview: '今晚修前端' }],
      }],
    }),
  }))
  const { default: History } = await import('../chat/History.jsx')
  const { findByText } = render(<History />)
  expect(await findByText('2026年7月')).toBeTruthy()
  expect(await findByText(/7月10日/)).toBeTruthy()
})
