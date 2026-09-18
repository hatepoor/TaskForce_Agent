import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { listThreadMessages, listThreadsMeta } from '@/api/chat'
import { readCurrentThreadId } from '@/composables/useLocalStore'
import { useUiStore } from '@/stores/ui'
import { createFakeStorage } from '@/test-utils/fakeStorage'
import type { ThreadMessagesResponse, ThreadMetaResponse } from '@/types/chat'

import { titleFromText, useChatStore } from './chat'

vi.mock('@/api/chat', () => ({
  listThreadsMeta: vi.fn(),
  listThreadMessages: vi.fn(),
}))

const mockMeta = vi.mocked(listThreadsMeta)
const mockMessages = vi.mocked(listThreadMessages)

const A = 'sess-aaaa1111'
const B = 'sess-bbbb2222'

function metaResponse(ids: string[]): ThreadMetaResponse {
  return {
    threads: ids.map((thread_id, i) => ({
      thread_id,
      last_checkpoint: `1ef7f0a${i}`,
      checkpoints: 3,
    })),
  }
}

function messagesResponse(
  threadId: string,
  messages: ThreadMessagesResponse['messages'],
  pending: ThreadMessagesResponse['pending_interrupt'] = null,
): ThreadMessagesResponse {
  return { thread_id: threadId, messages, pending_interrupt: pending }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.stubGlobal('localStorage', createFakeStorage())
  vi.restoreAllMocks()
  mockMeta.mockReset()
  mockMessages.mockReset()
})

describe('loadThreads', () => {
  it('按后端返回顺序建列表(后端已按最近活跃排序)', async () => {
    mockMeta.mockResolvedValue(metaResponse([B, A]))
    const chat = useChatStore()

    await chat.loadThreads()

    expect(chat.sessionList.map((row) => row.threadId)).toEqual([B, A])
    expect(chat.sessionList.every((row) => row.persisted)).toBe(true)
    expect(chat.loadingThreads).toBe(false)
    expect(chat.threadsError).toBe('')
  })

  it('id 缺少 sess- 前缀时 console.warn(契约漂移暴露)', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    mockMeta.mockResolvedValue(metaResponse(['裸-id-没有前缀']))
    const chat = useChatStore()

    await chat.loadThreads()

    expect(warn).toHaveBeenCalledWith(expect.stringContaining('sess-'))
  })

  it('请求失败时写入 threadsError,不抛', async () => {
    mockMeta.mockRejectedValue(new Error('boom'))
    const chat = useChatStore()

    await expect(chat.loadThreads()).resolves.toBeUndefined()
    expect(chat.threadsError).toBe('boom')
    expect(chat.loadingThreads).toBe(false)
  })
})

describe('newThread', () => {
  it('只生成 id 置为当前,不请求后端,并排在列表最前', async () => {
    mockMeta.mockResolvedValue(metaResponse([A]))
    const chat = useChatStore()
    await chat.loadThreads()

    const callsBeforeNew = mockMessages.mock.calls.length
    const id = chat.newThread()

    expect(id.startsWith('sess-')).toBe(true)
    expect(chat.currentThreadId).toBe(id)
    // newThread 自己不请求后端(loadThreads 的会话预热会有请求,故比增量)
    expect(mockMessages).toHaveBeenCalledTimes(callsBeforeNew)
    expect(chat.sessionList[0]?.threadId).toBe(id)
    expect(chat.sessionList[0]?.persisted).toBe(false)
    expect(chat.items).toEqual([])
  })
})

describe('hydrateFromServer', () => {
  it('回填时用首条用户消息补标题(本地没标题的会话,如 CLI/API 建的)', async () => {
    mockMessages.mockResolvedValue(
      messagesResponse(A, [
        { role: 'user', content: '帮我对比 pgvector 和 FAISS 的运维成本' },
        { role: 'assistant', content: '…' },
      ]),
    )
    const chat = useChatStore()

    await chat.hydrateFromServer(A)

    expect(chat.threadMeta[A]?.title).toBe('帮我对比 pgvector 和 FAIS…') // titleFromText 截 20 字
  })

  it('已有标题不被回填覆盖(标题只认首条输入)', async () => {
    mockMessages.mockResolvedValue(
      messagesResponse(A, [{ role: 'user', content: '回填时看到的第一条' }]),
    )
    const chat = useChatStore()
    chat.setThreadTitle(A, '本地已经记下的标题')

    await chat.hydrateFromServer(A)

    expect(chat.threadMeta[A]?.title).toBe('本地已经记下的标题')
  })

  it('历史消息映射为 ChatItem,pending_interrupt 恢复挂起占位', async () => {
    mockMessages.mockResolvedValue(
      messagesResponse(
        A,
        [
          { role: 'user', content: '帮我对比 pgvector 和 FAISS' },
          { role: 'assistant', content: '两款都是向量检索方案…' },
        ],
        { kind: 'ask', text: '你的服务端要部署在什么环境?' },
      ),
    )
    const chat = useChatStore()

    await chat.hydrateFromServer(A)

    const items = chat.itemsByThread[A] ?? []
    expect(items.map((it) => it.kind)).toEqual(['user', 'assistant', 'interrupt'])
    expect(items[0]).toMatchObject({ kind: 'user', text: '帮我对比 pgvector 和 FAISS' })
    expect(items[1]).toMatchObject({ kind: 'assistant', streaming: false })
    expect(chat.pendingByThread[A]).toMatchObject({
      sub: 'ask',
      text: '你的服务端要部署在什么环境?',
      status: 'waiting',
    })
  })

  it('无挂起时 pendingByThread 置 null', async () => {
    mockMessages.mockResolvedValue(messagesResponse(A, [{ role: 'user', content: '你好' }]))
    const chat = useChatStore()

    await chat.hydrateFromServer(A)

    expect(chat.pendingByThread[A]).toBeNull()
  })

  it('会话间不串台:computed 只读当前会话的那一组', async () => {
    mockMessages.mockImplementation(async (threadId: string) =>
      messagesResponse(
        threadId,
        threadId === A
          ? [
              { role: 'user', content: 'A 的问题' },
              { role: 'assistant', content: 'A 的回答' },
            ]
          : [{ role: 'user', content: 'B 的问题' }],
      ),
    )
    const chat = useChatStore()

    await chat.hydrateFromServer(A)
    await chat.hydrateFromServer(B)

    chat.switchThread(A, { hydrate: false })
    expect(chat.items.map((it) => (it.kind === 'route' || it.kind === 'interrupt' ? it.kind : it.text))).toEqual(
      ['A 的问题', 'A 的回答'],
    )

    chat.switchThread(B, { hydrate: false })
    expect(chat.items).toHaveLength(1)
    expect(chat.currentThreadId).toBe(B)
  })

  it('已有内容时 ensureHydrated 不重复请求', async () => {
    mockMessages.mockResolvedValue(messagesResponse(A, []))
    const chat = useChatStore()

    await chat.hydrateFromServer(A)
    chat.ensureHydrated(A)

    expect(mockMessages).toHaveBeenCalledTimes(1)
  })

  it('并发回填以最后一次为准(切走再切回不覆盖新结果)', async () => {
    const deferred: { resolve: (v: ThreadMessagesResponse) => void } = { resolve: () => {} }
    mockMessages
      .mockImplementationOnce(
        () =>
          new Promise<ThreadMessagesResponse>((resolve) => {
            deferred.resolve = resolve
          }),
      )
      .mockResolvedValueOnce(messagesResponse(A, [{ role: 'user', content: '第二次' }]))
    const chat = useChatStore()

    const first = chat.hydrateFromServer(A)
    const second = chat.hydrateFromServer(A)
    await second
    deferred.resolve(messagesResponse(A, [{ role: 'user', content: '第一次' }]))
    await first

    const items = chat.itemsByThread[A] ?? []
    expect(items).toHaveLength(1)
    expect(items[0]).toMatchObject({ text: '第二次' })
  })

  it('请求失败时 toast 提示且不落内容,不抛', async () => {
    mockMessages.mockRejectedValue(new Error('网络断了'))
    const chat = useChatStore()

    await expect(chat.hydrateFromServer(A)).resolves.toBeUndefined()
    expect(chat.itemsByThread[A]).toBeUndefined()
    expect(useUiStore().toasts.map((t) => t.type)).toEqual(['error'])
  })
})

describe('本地标题', () => {
  it('titleFromText 折叠空白并截断到 20 字', () => {
    expect(titleFromText('  帮我  对比\npgvector  ')).toBe('帮我 对比 pgvector')
    expect(titleFromText('一'.repeat(30))).toBe(`${'一'.repeat(20)}…`)
  })

  it('只认首条输入(已有标题不覆盖),且按本地活跃时间排序', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-09-17T12:00:00'))
    const chat = useChatStore()

    chat.setThreadTitle(A, '第一条输入')
    chat.setThreadTitle(A, '第二条输入')
    vi.setSystemTime(new Date('2026-09-17T12:05:00'))
    chat.setThreadTitle(B, 'B 的首条')

    expect(chat.threadMeta[A]?.title).toBe('第一条输入')
    expect(chat.threadMeta[B]?.title).toBe('B 的首条')
    expect(chat.sessionList.map((row) => row.title)).toEqual(['B 的首条', '第一条输入'])
    vi.useRealTimers()
  })
})

describe('会话身份持久化', () => {
  it('切换后写入 localStorage,重建 store 仍指向同一会话', async () => {
    mockMeta.mockResolvedValue(metaResponse([A]))
    const chat = useChatStore()
    await chat.loadThreads()

    chat.switchThread(A, { hydrate: false })
    expect(readCurrentThreadId()).toBe(A)

    setActivePinia(createPinia())
    const revived = useChatStore()
    expect(revived.currentThreadId).toBe(A)
  })
})

describe('轮次动作(模块 07)', () => {
  it('pushUser + beginTurn:用户气泡 + 空 AI 占位 + 首条输入设标题', () => {
    const chat = useChatStore()
    chat.pushUser('帮我对比 pgvector 和 FAISS')
    chat.beginTurn()

    expect(chat.items.map((it) => it.kind)).toEqual(['user', 'assistant'])
    expect(chat.items[0]).toMatchObject({ text: '帮我对比 pgvector 和 FAISS' })
    expect(chat.items[1]).toMatchObject({ text: '', streaming: true })
    expect(chat.turn?.status).toBe('streaming')
    expect(chat.isStreaming).toBe(true)
    expect(chat.threadMeta[chat.currentThreadId]?.title).toBe(titleFromText('帮我对比 pgvector 和 FAISS'))
  })

  it('appendToken 累加到同一条 AI 正文,flushTokens 后可见', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.appendToken('你好')
    chat.appendToken(',我是 TaskForce')
    chat.flushTokens()

    expect(chat.items).toHaveLength(1)
    expect(chat.items[0]).toMatchObject({ kind: 'assistant', text: '你好,我是 TaskForce' })
    expect(chat.turnHasOutput).toBe(true)
  })

  it('pushRoute 关掉当前 AI 段,其后的 token 另起一段', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.appendToken('先检索一下')
    chat.pushRoute({ next: 'dispatch', question: null, tasks: [{ agent: 'retriever', task: 't', reason: 'r' }] })
    chat.appendToken('检索完成')
    chat.flushTokens()

    expect(chat.items.map((it) => it.kind)).toEqual(['assistant', 'route', 'assistant'])
    expect(chat.items[0]).toMatchObject({ text: '先检索一下', streaming: false })
    expect(chat.items[2]).toMatchObject({ text: '检索完成', streaming: true })
  })

  it('轨迹/挂起出现时收回空占位,不留空气泡', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.pushRoute({ next: 'answer', question: null, tasks: null })
    expect(chat.items.map((it) => it.kind)).toEqual(['route'])

    chat.beginTurn()
    chat.setPending({ kind: 'ask', text: 'q' })
    expect(chat.items.map((it) => it.kind)).toEqual(['route', 'interrupt'])
  })

  it('setPending 落挂起占位并记 pendingByThread', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.setPending({ kind: 'ask', text: '要检索哪个范围?' })

    const last = chat.items[chat.items.length - 1]
    expect(last).toMatchObject({ kind: 'interrupt', sub: 'ask', status: 'waiting' })
    expect(chat.pending).toMatchObject({ sub: 'ask', status: 'waiting' })
  })

  it('attachUsage 按轮首快照做差(进程累计 → 本轮增量)', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.attachUsage({ thread_id: chat.currentThreadId, calls: 3, input_tokens: 1000, output_tokens: 200 })
    chat.endTurn()

    chat.beginTurn()
    chat.attachUsage({ thread_id: chat.currentThreadId, calls: 5, input_tokens: 4000, output_tokens: 900 })

    const assistant = chat.items.filter((it) => it.kind === 'assistant')
    expect(assistant[1]?.usage).toEqual({ calls: 2, inputTokens: 3000, outputTokens: 700 })
  })

  it('endTurn:收尾轮次、关光标;等待回答的挂起保留、已答的解除', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.appendToken('答完了')
    chat.setPending({ kind: 'ask', text: 'q' })
    chat.endTurn()
    expect(chat.turn?.status).toBe('done')
    expect(chat.pending).toMatchObject({ sub: 'ask' }) // 本轮新出的挂起,还在等回答

    // 用户作答 → 恢复流 → 本轮结束 → 挂起解除
    chat.resolvePending({ status: 'submitting', answer: '只看 docs/' })
    chat.beginTurn()
    chat.appendToken('继续')
    chat.endTurn()
    expect(chat.pending).toBeNull()
    expect(chat.turnHasOutput).toBe(false)
  })

  it('endTurn 空输出补兜底 note', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.endTurn()

    expect(chat.items[0]).toMatchObject({ kind: 'assistant', streaming: false })
    expect((chat.items[0] as { note?: string }).note).toContain('没有产生文本输出')
  })

  it('abortTurn:标 aborted + 留灰字提示,可继续发下一条', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.appendToken('半截回答')
    chat.abortTurn()

    expect(chat.turn?.status).toBe('aborted')
    expect(chat.isStreaming).toBe(false)
    expect((chat.items[0] as { note?: string }).note).toContain('已停止接收')
    expect(chat.items[0]).toMatchObject({ text: '半截回答', streaming: false })
  })

  it('failTurn:错误落到 AI 项,挂起卡标失效并清挂起', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.setPending({ kind: 'memory', text: '用户偏好中文' })
    chat.failTurn('该会话没有待处理的挂起', 400)

    const err = chat.turn?.error
    expect(err).toMatchObject({ status: 400 })
    expect(chat.pending).toBeNull()
    const pendingItem = chat.items.find((it) => it.kind === 'interrupt')
    expect(pendingItem).toMatchObject({ status: 'failed', error: '该会话没有待处理的挂起' })
  })

  it('noteTurn:兜底文案按正常正文走(不标错误态)', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.noteTurn('本轮任务循环过深,已中止。')
    expect((chat.items[0] as { note?: string }).note).toBe('本轮任务循环过深,已中止。')
    expect(chat.turn?.status).toBe('streaming') // 兜底文案不是错误态
    expect((chat.items[0] as { error?: unknown }).error).toBeUndefined()
  })

  it('resolvePending 就地推进挂起卡状态', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.setPending({ kind: 'ask', text: 'q' })

    chat.resolvePending({ status: 'submitting' })
    expect(chat.pending?.status).toBe('submitting') // 提交中仍算挂起,Composer 继续禁用

    chat.resolvePending({ status: 'resolved', answer: '只看 docs/' })
    expect(chat.pending).toBeNull()
    expect(chat.items.find((it) => it.kind === 'interrupt')).toMatchObject({
      status: 'resolved',
      answer: '只看 docs/',
    })
  })

  it('提交中的挂起卡随本轮结束落定为已解决', () => {
    const chat = useChatStore()
    chat.beginTurn()
    chat.setPending({ kind: 'memory', text: '用户偏好中文' })
    chat.resolvePending({ status: 'submitting', approved: true })
    chat.endTurn()

    expect(chat.items.find((it) => it.kind === 'interrupt')).toMatchObject({
      status: 'resolved',
      approved: true,
    })
    expect(chat.pending).toBeNull()
  })

  it('400 失败:挂起卡标失效 + toast 原文 + 刷新会话列表(坑 10)', async () => {
    mockMeta.mockResolvedValue(metaResponse([A]))
    const chat = useChatStore()
    chat.beginTurn()
    chat.setPending({ kind: 'ask', text: 'q' })
    chat.resolvePending({ status: 'submitting' })
    chat.failTurn('该会话没有待处理的挂起', 400)
    await Promise.resolve()

    const failed = chat.items.find((it) => it.kind === 'interrupt')
    expect(failed).toMatchObject({ status: 'failed', error: '该会话没有待处理的挂起' })
    expect(useUiStore().toasts.map((t) => t.msg)).toContain('该会话没有待处理的挂起')
    expect(mockMeta).toHaveBeenCalled()
  })

  it('流开始后切走会话,输出仍写回原会话(不串台)', () => {
    const chat = useChatStore()
    const a = 'sess-aaaa1111'
    const b = 'sess-bbbb2222'
    chat.switchThread(a, { hydrate: false })
    chat.beginTurn()
    chat.switchThread(b, { hydrate: false })
    chat.appendToken('A 的回答')
    chat.flushTokens()

    expect(chat.items).toEqual([]) // 当前是 B,看不到 A 的输出
    const inA = chat.itemsByThread[a] ?? []
    expect(inA[inA.length - 1]).toMatchObject({ kind: 'assistant', text: 'A 的回答' })
  })
})
describe('后台任务待汇总标记(awaitingTasks)', () => {
  it('派发路由置位:dispatch 且有任务时标记该会话等待汇总', () => {
    const chat = useChatStore()
    chat.switchThread(A, { hydrate: false })
    expect(chat.hasAwaitingTasks(A)).toBe(false)

    chat.beginTurn()
    chat.pushRoute({
      next: 'dispatch',
      question: null,
      tasks: [{ agent: 'research', task: '调研 X', reason: 'r' }],
    })

    expect(chat.hasAwaitingTasks(A)).toBe(true)
    expect(chat.hasAwaitingTasks(B)).toBe(false) // 只标记发起会话
  })

  it('非 dispatch 路由(或空任务列表)不置位', () => {
    const chat = useChatStore()
    chat.switchThread(A, { hydrate: false })
    chat.beginTurn()
    chat.pushRoute({ next: 'answer', question: null, tasks: null })
    expect(chat.hasAwaitingTasks(A)).toBe(false)

    chat.beginTurn()
    chat.pushRoute({ next: 'dispatch', question: null, tasks: [] })
    expect(chat.hasAwaitingTasks(A)).toBe(false)
  })

  it('清位后标记消失,并随本地元数据持久化(刷新后仍在)', () => {
    const chat = useChatStore()
    chat.switchThread(A, { hydrate: false })
    chat.beginTurn()
    chat.pushRoute({
      next: 'dispatch',
      question: null,
      tasks: [{ agent: 'retriever', task: 't', reason: 'r' }],
    })
    expect(chat.hasAwaitingTasks(A)).toBe(true)

    const raw = JSON.parse(localStorage.getItem('tf.threads') ?? '{}') as {
      data?: Record<string, { awaitingTasks?: boolean }>
    }
    expect(raw.data?.[A]?.awaitingTasks).toBe(true)

    chat.setAwaitingTasks(A, false)
    expect(chat.hasAwaitingTasks(A)).toBe(false)
    const raw2 = JSON.parse(localStorage.getItem('tf.threads') ?? '{}') as {
      data?: Record<string, { awaitingTasks?: boolean }>
    }
    expect(raw2.data?.[A]?.awaitingTasks).toBeUndefined()
  })
})

describe('会话预热(prefetchRecent)', () => {
  it('loadThreads 后回填最近 12 个会话:标题补齐、已载入的不重复请求', async () => {
    mockMeta.mockResolvedValue(metaResponse([A, B, 'sess-cccc3333']))
    mockMessages.mockImplementation((id: string) =>
      Promise.resolve(messagesResponse(id, [{ role: 'user', content: `问题 ${id}` }])),
    )
    const chat = useChatStore()

    await chat.loadThreads()
    await new Promise((r) => setTimeout(r, 0))

    expect(mockMessages).toHaveBeenCalledTimes(3)
    expect(chat.threadMeta[A]?.title).toContain('问题')

    mockMessages.mockClear()
    chat.ensureHydrated(A)
    await new Promise((r) => setTimeout(r, 0))
    expect(mockMessages).not.toHaveBeenCalled() // 已有内容:不再请求
  })
})
