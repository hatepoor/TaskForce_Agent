/**
 * 上传单文件(带进度):fetch 拿不到上传进度,只有 XHR 的 `upload.onprogress` 能拿到
 * (契约 §2.3 / UI-DESIGN §4.1),故本模块在 `api/knowledge.uploadDoc` 之外单开一个 XHR 版本。
 * 错误形状与 api/http 的 ApiError 对齐,errText 可直接复用。
 *
 * 注:模块 09 的文件边界不允许改 src/api/**,XHR 包装暂放组件目录;
 * 后续收尾模块若要合并,直接把本函数搬进 api/knowledge.ts 并让 uploadDoc 转发即可。
 */
import { ApiError, BASE } from '@/api/http'
import type { KUploadResult } from '@/types/knowledge'
import { progressPercent } from '@/utils/knowledge'

/** 20MB 文件 + embedding 的预算(契约 §3.6)。 */
const UPLOAD_TIMEOUT_MS = 120_000

/**
 * POST /knowledge/upload,multipart 字段名固定 `file`。
 * - 不手动设 Content-Type:让浏览器带 boundary(契约 §2.3);
 * - onProgress 回调给 0..100 的整数(取不到总长时给 0)。
 */
export function uploadDocWithProgress(
  file: File,
  onProgress: (percent: number) => void,
): Promise<KUploadResult> {
  return new Promise<KUploadResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${BASE}/knowledge/upload`)
    xhr.timeout = UPLOAD_TIMEOUT_MS

    xhr.upload.onprogress = (e: ProgressEvent): void => {
      onProgress(progressPercent(e.loaded, e.total))
    }

    xhr.onload = (): void => {
      const body = parseBody(xhr.responseText)
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as KUploadResult)
        return
      }
      reject(new ApiError(xhr.status, detailOf(body, xhr.status)))
    }

    xhr.onerror = (): void => reject(new TypeError('无法连接后端,请确认 uvicorn 已启动'))
    xhr.ontimeout = (): void => reject(new DOMException('请求超时', 'TimeoutError'))
    xhr.onabort = (): void => reject(new DOMException('请求已取消', 'AbortError'))

    const fd = new FormData()
    fd.append('file', file)
    xhr.send(fd)
  })
}

/** 错误体里的 detail 原文;拿不到就退回状态码文案(与 api/http 同策略)。 */
function detailOf(body: unknown, status: number): unknown {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    return (body as { detail: unknown }).detail
  }
  return `HTTP ${status}`
}

function parseBody(text: string): unknown {
  try {
    return JSON.parse(text) as unknown
  } catch {
    return null
  }
}