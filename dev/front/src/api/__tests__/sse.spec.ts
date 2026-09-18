import { afterEach, describe, expect, it, vi } from 'vitest'

import { SseError, parseFrame, sseFetch, splitFrames } from '../sse'

/* ---------- splitFrames:切帧与残帧 ---------- */

describe('splitFrames', () => {
  it('单帧完整:切出一帧,rest 为空', () => {
    const { frames, rest } = splitFrames('data: {"token":"a"}\n\n')
    expect(frames).toEqual(['data: {"token":"a"}'])
    expect(rest).toBe('')
  })

  it('多帧一次切分:完整帧全部返回,未完成段留 rest', () => {
    const { frames, rest } = splitFrames('data: {"token":"a"}\n\ndata: {"token":"b"}\n\ndata: {"tok')
    expect(frames).toEqual(['data: {"token":"a"}', 'data: {"token":"b"}'])
    expect(rest).toBe('data: {"tok')
  })

  it('残帧留 buffer:半条 JSON 不切出', () => {
    const { frames, rest } = splitFrames('data: {"token":"你说的')
    expect(frames).toHaveLength(0)
    expect(rest).toBe('data: {"token":"你说的')
  })

  it('CRLF 归一化:\\r\\n\\r\\n 变形也能切开(代理改造场景)', () => {
    const { frames, rest } = splitFrames('data: {"token":"a"}\r\n\r\ndata: {"token":"b"}\r\n\r\n')
    expect(frames).toEqual(['data: {"token":"a"}', 'data: {"token":"b"}'])
    expect(rest).toBe('')
  })

  it('LF/CRLF 混用:先归一化再切', () => {
    const { frames } = splitFrames('data: {"token":"a"}\r\n\ndata: {"token":"b"}\n\n')
    expect(frames).toEqual(['data: {"token":"a"}', 'data: {"token":"b"}'])
  })
})

/* ---------- parseFrame:五类事件 + unknown + 坏帧 ---------- */

describe('parseFrame', () => {
  it('token:载荷为字符串', () => {
    expect(parseFrame('data: {"token":"你好"}')).toEqual({ type: 'token', data: '你好' })
  })

  it('route:载荷为 RoutePayload 对象', () => {
    const route = { next: 'answer', question: null, tasks: null }
    expect(parseFrame(`data: ${JSON.stringify({ route })}`)).toEqual({ type: 'route', data: route })
  })

  it('interrupt:B3 对象信封 {kind, text}', () => {
    const it0 = { kind: 'ask', text: '你的服务端部署在什么环境?' }
    expect(parseFrame(`data: ${JSON.stringify({ interrupt: it0 })}`)).toEqual({
      type: 'interrupt',
      data: it0,
    })
  })

  it('usage:四字段载荷', () => {
    const usage = { thread_id: 'sess-x', calls: 3, input_tokens: 4821, output_tokens: 763 }
    expect(parseFrame(`data: ${JSON.stringify({ usage })}`)).toEqual({ type: 'usage', data: usage })
  })

  it('error(B4):message + 可选 code', () => {
    const err = { message: '本轮任务循环过深', code: 'recursion_limit' }
    expect(parseFrame(`data: ${JSON.stringify({ error: err })}`)).toEqual({ type: 'error', data: err })
  })

  it('unknown:未知键归为 unknown 记录,不中断流', () => {
    const ev = parseFrame('data: {"heartbeat": 1}')
    expect(ev?.type).toBe('unknown')
    if (ev?.type === 'unknown') expect(ev.data).toBe(1)
  })

  it('坏 JSON:返回 null 而非抛出', () => {
    expect(parseFrame('data: {"token":"半')).toBeNull()
  })

  it('无 data 行(注释/心跳帧):返回 null', () => {
    expect(parseFrame(': keep-alive')).toBeNull()
    expect(parseFrame('')).toBeNull()
  })

  it('多行 data:按 SSE 规范合并后解析', () => {
    expect(parseFrame('data: {"token":\ndata: "拼接"}')).toEqual({ type: 'token', data: '拼接' })
  })
})

/* ---------- 中文跨片(坑 1):TextDecoder {stream:true} ---------- */

describe('中文跨片解码(坑 1)', () => {
  it('三字节中文被劈开:stream 解码拼回原文并可解析;朴素解码出替换符', () => {
    const frame = 'data: {"token": "你好世界"}\n\n'
    const bytes = new TextEncoder().encode(frame)
    // 在"你"的 3 字节中间劈开(前缀为纯 ASCII,长度即字节偏移)
    const cut = 'data: {"token": "'.length + 1
    const dec = new TextDecoder('utf-8')
    const p1 = dec.decode(bytes.slice(0, cut), { stream: true })
    const p2 = dec.decode(bytes.slice(cut), { stream: true })
    const p3 = dec.decode()
    expect(p1 + p2 + p3).toBe(frame)

    const { frames } = splitFrames(p1 + p2 + p3)
    const [first] = frames
    expect(first).toBeDefined()
    expect(parseFrame(first ?? '')).toEqual({ type: 'token', data: '你好世界' })

    // 对照:不带 stream 的朴素解码把被劈开的字符解成 U+FFFD(乱码根因)
    const naive = new TextDecoder('utf-8').decode(bytes.slice(0, cut))
    expect(naive).toContain('\uFFFD')
  })
})

/* ---------- sseFetch 错误分支(验收标准③:受控单测覆盖) ---------- */

describe('sseFetch 错误分支', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('网络不可达:fetch 抛 TypeError → onError(SseError network),不发 onDone', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))),
    )
    const errors: SseError[] = []
    let done = false
    await sseFetch('/chat', {}, { onError: (e) => errors.push(e), onDone: () => (done = true) })
    expect(errors).toHaveLength(1)
    expect(errors[0]?.kind).toBe('network')
    expect(errors[0]?.status).toBe(0)
    expect(done).toBe(false)
  })

  it('非 2xx(400):解析 JSON detail → onError(SseError http/400 含 detail 原文)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 400,
          json: () => Promise.resolve({ detail: '该会话没有待处理的挂起' }),
        } as unknown as Response),
      ),
    )
    const errors: SseError[] = []
    let done = false
    await sseFetch('/chat/confirm', {}, { onError: (e) => errors.push(e), onDone: () => (done = true) })
    expect(errors[0]?.kind).toBe('http')
    expect(errors[0]?.status).toBe(400)
    expect(errors[0]?.message).toBe('该会话没有待处理的挂起')
    expect(done).toBe(false)
  })

  it('响应无 body:onError(SseError nobody)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: true, status: 200, body: null } as unknown as Response)),
    )
    const errors: SseError[] = []
    await sseFetch('/chat', {}, { onError: (e) => errors.push(e) })
    expect(errors[0]?.kind).toBe('nobody')
  })
})