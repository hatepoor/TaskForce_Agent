import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { send, submitAnswer, submitConfirm, summarize } from '@/api/chat'
import { SseError, type SseHandlers } from '@/api/sse'
import { useChatStore } from '@/stores/chat'
import { createFakeStorage } from '@/test-utils/fakeStorage'

import { useChatStream } from './useChatStream'

vi.mock('@/api/chat', () => ({
  send: vi.fn(),
  submitAnswer: vi.fn(),
  submitConfirm: vi.fn(),
  summarize: vi.fn(),
}))

const mockSend = vi.mocked(send)
const mockAnswer = vi.mocked(submitAnswer)
const mockConfirm = vi.mocked(submitConfirm)
const mockSummarize = vi.mocked(summarize)

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('localStorage', createFakeStorage())
  mockSend.mockReset()
  mockAnswer.mockReset()
  mockConfirm.mockReset()
  mockSummarize.mockReset()
})

describe('useChatStream.send', () => {
  it('用户气泡落地 → 开轮 → 调 /chat,事件按序写进 store', async () => {
    mockSend.mockImplementation((_body, h: SseHandlers) => {
      h.onRoute?.({ next: 'dispatch', question: null, tasks: [{ agent: 'retriever', task: 't', reason: 'r' }] })
      h.onToken?.('答案')
      h.onUsage?.({ thread_id: 'sess-x', calls: 1, input_tokens: 10, output_tokens: 5 })
      h.onDone?.()
      return Promise.resolve()
    })

    const chat = useChatStore()
    const stream = useChatStream()
    await stream.send('  帮我查一下  ')

    expect(mockSend).toHaveBeenCalledWith(
      { thread_id: chat.currentThreadId, text: '帮我查一下' },
      expect.any(Object),
      expect.anything(),
    )
    expect(chat.items.map((it) => it.kind)).toEqual(['user', 'route', 'assistant'])
    expect(chat.items[0]).toMatchObject({ text: '帮我查一下' })
    expect(chat.items[2]).toMatchObject({ text: '答案', streaming: false })
    expect(chat.turn?.status).toBe('done')
    expect(chat.isStreaming).toBe(false)
  })

  it('空文本 / 流式进行中:直接早退,不发请求', async () => {
    const chat = useChatStore()
    const stream = useChatStream()

    await stream.send('   ')
    expect(mockSend).not.toHaveBeenCalled()

    mockSend.mockImplementation(() => Promise.resolve())
    chat.beginTurn()
    await stream.send('第二条')
    expect(mockSend).not.toHaveBeenCalled()
  })

  it('异常帧 code=recursion_limit 走 note,不当错误', async () => {
    mockSend.mockImplementation((_body, h: SseHandlers) => {
      h.onErrorEvent?.({ message: '本轮任务循环过深,已中止。', code: 'recursion_limit' })
      h.onDone?.()
      return Promise.resolve()
    })

    const chat = useChatStore()
    await useChatStream().send('深递归')

    expect(chat.turn?.status).toBe('done')
    expect((chat.items[1] as { note?: string }).note).toContain('循环过深')
  })

  it('传输错误:标 error 并可重试(resend 不重复插气泡)', async () => {
    mockSend.mockImplementation((_body, h: SseHandlers) => {
      h.onError?.(new SseError('network', 0, '无法连接后端,请确认 uvicorn 已启动'))
      return Promise.resolve()
    })

    const chat = useChatStore()
    const stream = useChatStream()
    await stream.send('在吗')

    expect(chat.turn?.status).toBe('error')
    expect(chat.items.filter((it) => it.kind === 'user')).toHaveLength(1)

    mockSend.mockImplementation((_body, h: SseHandlers) => {
      h.onToken?.('在的')
      h.onDone?.()
      return Promise.resolve()
    })
    await stream.resend('在吗')

    expect(chat.items.filter((it) => it.kind === 'user')).toHaveLength(1) // 不重复插
    expect(chat.items[chat.items.length - 1]).toMatchObject({ text: '在的' })
    expect(chat.turn?.status).toBe('done')
  })

  it('abort:轮次标 aborted 并留灰字提示', async () => {
    let release: () => void = () => {}
    mockSend.mockImplementation(
      (_body, h: SseHandlers, signal?: AbortSignal) =>
        new Promise<void>((resolve) => {
          h.onToken?.('半截')
          release = resolve
          signal?.addEventListener('abort', () => resolve())
        }),
    )

    const chat = useChatStore()
    const stream = useChatStream()
    const running = stream.send('讲个长故事')
    await Promise.resolve()

    stream.abort()
    release()
    await running

    expect(chat.turn?.status).toBe('aborted')
    expect((chat.items[1] as { note?: string }).note).toContain('已停止接收')
  })
})

describe('挂起恢复入口', () => {
  it('answer → POST /chat/answer,confirm → POST /chat/confirm', async () => {
    mockAnswer.mockImplementation(() => Promise.resolve())
    mockConfirm.mockImplementation(() => Promise.resolve())

    const chat = useChatStore()
    const stream = useChatStream()

    await stream.answer('只看 docs/ 那几份')
    expect(mockAnswer).toHaveBeenCalledWith(
      { thread_id: chat.currentThreadId, text: '只看 docs/ 那几份' },
      expect.any(Object),
      expect.anything(),
    )

    chat.endTurn()
    await stream.confirm(true)
    expect(mockConfirm).toHaveBeenCalledWith(
      { thread_id: chat.currentThreadId, approved: true },
      expect.any(Object),
      expect.anything(),
    )
  })
})

describe('summarizeThread(后台任务自动汇总)', () => {
  it('当前会话有待汇总任务:POST /chat/summary,不插用户气泡,回答流式落地', async () => {
    mockSummarize.mockImplementation((_body, h: SseHandlers) => {
      h.onRoute?.({ next: 'answer', question: null, tasks: null })
      h.onToken?.('三份资料已汇总…')
      h.onDone?.()
      return Promise.resolve()
    })

    const chat = useChatStore()
    const tid = chat.currentThreadId
    await useChatStream().summarizeThread(tid)

    expect(mockSummarize).toHaveBeenCalledWith(
      { thread_id: tid },
      expect.any(Object),
      expect.anything(),
    )
    expect(chat.items.filter((it) => it.kind === 'user')).toHaveLength(0) // 无用户气泡
    expect(chat.items[chat.items.length - 1]).toMatchObject({
      kind: 'assistant',
      text: '三份资料已汇总…',
      streaming: false,
    })
    expect(chat.turn?.status).toBe('done')
  })

  it('已切走会话 / 正在流式:不代汇总', async () => {
    mockSummarize.mockImplementation(() => Promise.resolve())
    const chat = useChatStore()
    const stream = useChatStream()

    await stream.summarizeThread('sess-other')
    expect(mockSummarize).not.toHaveBeenCalled()

    chat.beginTurn()
    await stream.summarizeThread(chat.currentThreadId)
    expect(mockSummarize).not.toHaveBeenCalled()
  })
})
