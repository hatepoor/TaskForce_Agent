import { describe, expect, it } from 'vitest'

import type { KDoc } from '@/types/knowledge'

import {
  DOC_GONE_MSG,
  MAX_UPLOAD_BYTES,
  OVERSIZE_MSG,
  type UploadItem,
  doneText,
  fmtBytes,
  fmtDateTime,
  isDocGoneStatus,
  isOversize,
  makeQueueItem,
  nextQueuedIndex,
  progressPercent,
  progressText,
  shortDocId,
  sortDocsByCreatedAt,
} from './knowledge'

function item(id: number, state: UploadItem['state']): UploadItem {
  return {
    id,
    name: `f${id}.md`,
    size: 1024,
    state,
    percent: 0,
    message: '',
    docId: '',
    created: false,
  }
}

function mk(docId: string, createdAt: string, chunks = 1): KDoc {
  return { doc_id: docId, filename: `${docId}.md`, created_at: createdAt, chunks }
}

describe('isOversize / makeQueueItem', () => {
  it('恰好 20MB 放行,超过才拦(与后端 > 20MB 同义)', () => {
    expect(isOversize(MAX_UPLOAD_BYTES)).toBe(false)
    expect(isOversize(MAX_UPLOAD_BYTES + 1)).toBe(true)
    expect(isOversize(0)).toBe(false)
  })

  it('超限项直接落 failed 且不排队(串行推进不会给它发请求)', () => {
    const big = makeQueueItem({ name: '论文.pdf', size: MAX_UPLOAD_BYTES + 1 }, 7)
    expect(big.state).toBe('failed')
    expect(big.message).toBe(OVERSIZE_MSG)
    expect(big.percent).toBe(0)

    const ok = makeQueueItem({ name: '架构.md', size: 1024 }, 8)
    expect(ok.state).toBe('queued')
    expect(ok.message).toBe('')
    expect(ok.docId).toBe('')
    expect(ok.created).toBe(false)
  })
})

describe('nextQueuedIndex', () => {
  it('跳过已完成 / 上传中 / 失败项,取第一个排队项', () => {
    const items = [item(1, 'done'), item(2, 'uploading'), item(3, 'failed'), item(4, 'queued')]
    expect(nextQueuedIndex(items)).toBe(3)
  })

  it('无排队项返回 -1;失败项重试回 queued 后重新被拾起', () => {
    const items = [item(1, 'done'), item(2, 'failed')]
    expect(nextQueuedIndex(items)).toBe(-1)

    const retried = items[1]
    if (retried === undefined) throw new Error('测试数据缺失')
    retried.state = 'queued'
    expect(nextQueuedIndex(items)).toBe(1)
  })
})

describe('progressPercent / progressText', () => {
  it('归一为 0..100 整数并夹取边界', () => {
    expect(progressPercent(0, 200)).toBe(0)
    expect(progressPercent(100, 200)).toBe(50)
    expect(progressPercent(124, 200)).toBe(62)
    expect(progressPercent(200, 200)).toBe(100)
    expect(progressPercent(300, 200)).toBe(100)
    expect(progressPercent(-5, 200)).toBe(0)
  })

  it('拿不到总长(0 / NaN)时给 0,不显示假进度', () => {
    expect(progressPercent(100, 0)).toBe(0)
    expect(progressPercent(100, Number.NaN)).toBe(0)
  })

  it('发完请求体后文案切到"解析入库中",避免进度条看着卡死', () => {
    expect(progressText(0)).toBe('上传中 0%')
    expect(progressText(62)).toBe('上传中 62%')
    expect(progressText(99)).toBe('上传中 99%')
    expect(progressText(100)).toBe('解析入库中…')
  })
})

describe('doneText', () => {
  it('created:false 是判重命中,文案为"已存在,已复用"', () => {
    expect(doneText(false, undefined)).toBe('已存在,已复用')
    expect(doneText(false, 42)).toBe('已存在,已复用 · 42 切片')
  })

  it('created:true 为已入库;切片数拿不到(还没刷新到)就只显示前半句', () => {
    expect(doneText(true, undefined)).toBe('已入库')
    expect(doneText(true, 0)).toBe('已入库 · 0 切片')
    expect(doneText(true, 84)).toBe('已入库 · 84 切片')
    expect(doneText(true, Number.NaN)).toBe('已入库')
  })
})

describe('isDocGoneStatus', () => {
  it('404 与 B7 落地前的 500 同一处理,其余状态码走普通错误', () => {
    expect(isDocGoneStatus(404)).toBe(true)
    expect(isDocGoneStatus(500)).toBe(true)
    expect(isDocGoneStatus(400)).toBe(false)
    expect(isDocGoneStatus(0)).toBe(false)
    expect(DOC_GONE_MSG).toBe('该文档可能已不存在,已刷新列表')
  })
})

describe('fmtBytes', () => {
  it('B / KB / MB 三档,去掉多余的 .0', () => {
    expect(fmtBytes(0)).toBe('0B')
    expect(fmtBytes(Number.NaN)).toBe('0B')
    expect(fmtBytes(512)).toBe('512B')
    expect(fmtBytes(1023)).toBe('1023B')
    expect(fmtBytes(1024)).toBe('1KB')
    expect(fmtBytes(1536)).toBe('1.5KB')
    expect(fmtBytes(10240)).toBe('10KB')
    expect(fmtBytes(1_258_291)).toBe('1.2MB')
    expect(fmtBytes(MAX_UPLOAD_BYTES)).toBe('20MB')
  })
})

describe('fmtDateTime', () => {
  it('ISO 8601 按本地时区显示 MM-DD HH:mm,个位数补零', () => {
    // 用本地时间造 Date 再转 ISO,断言与运行机器时区无关
    expect(fmtDateTime(new Date(2026, 8, 14, 17, 22).toISOString())).toBe('09-14 17:22')
    expect(fmtDateTime(new Date(2026, 0, 3, 4, 5).toISOString())).toBe('01-03 04:05')
  })

  it('空串 / 非法时间返回空串(列里不显示 1970)', () => {
    expect(fmtDateTime('')).toBe('')
    expect(fmtDateTime('not-a-date')).toBe('')
  })

  it('解析后端真实格式(秒小数 6 位 + 时区偏移),不返回空串', () => {
    // 后端 uuid4 + isoformat 的真实输出,GET /knowledge 实测样本
    const iso = '2026-09-03T19:55:43.692410+00:00'
    const d = new Date(Date.parse(iso))
    const p = (n: number): string => String(n).padStart(2, '0')
    expect(fmtDateTime(iso)).toBe(
      `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`,
    )
  })
})

describe('shortDocId', () => {
  it('32 位 hex 截前 8 位 + 省略号;短串原样返回', () => {
    expect(shortDocId('3f2a9c1b8e4d4f6a9b0c1d2e3f4a5b6c')).toBe('3f2a9c1b…')
    expect(shortDocId('abc12345')).toBe('abc12345')
    expect(shortDocId('')).toBe('')
  })
})

describe('sortDocsByCreatedAt', () => {
  it('按 created_at 升序,不改动入参数组', () => {
    const input = [
      mk('c', '2026-09-16T08:31:22.145+00:00'),
      mk('a', '2026-09-14T00:00:00+00:00'),
      mk('b', '2026-09-15T00:00:00+00:00'),
    ]
    const out = sortDocsByCreatedAt(input)
    expect(out.map((d) => d.doc_id)).toEqual(['a', 'b', 'c'])
    expect(input.map((d) => d.doc_id)).toEqual(['c', 'a', 'b'])
    expect(out).not.toBe(input)
  })

  it('缺失 / 非法时间视为最早,排在最前(不让坏数据顶掉正常顺序)', () => {
    const out = sortDocsByCreatedAt([
      mk('ok', '2026-09-14T00:00:00+00:00'),
      mk('bad', ''),
    ])
    expect(out.map((d) => d.doc_id)).toEqual(['bad', 'ok'])
  })
})