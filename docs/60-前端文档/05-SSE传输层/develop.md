# SSE传输层

> 编号: `05`
> 英文标识: `sse-transport`
> 状态: ✅ 已完成
> 最后更新: 2026-09-17

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [04-API层与类型镜像](../04-API层与类型镜像/develop.md) | SSE 五事件类型与三端点签名 | `RoutePayload`、`InterruptEnvelope`、`UsageEvent`、`ErrorEvent` |
| [01-后端契约改造](../01-后端契约改造/develop.md) | B4 error 帧(可选,未落地按 broken 推断) | `{"error": {message, code?}}` |

---

## 概述

实现 `src/api/sse.ts` 纯传输层:fetch + ReadableStream 手工解析 SSE 帧(POST 不能用 EventSource),经回调驱动上层。纯函数可单测,是前端唯一写 Vitest 的地方。

## 功能清单

- **帧切分**:`splitFrames(buffer)`(CRLF 归一化 + `\n\n` 分帧 + 残帧保留)
- **帧解析**:`parseFrame(raw)`(单键分发、坏帧返回 null)
- **流驱动**:`sseFetch(path, body, handlers, signal)`(非 2xx JSON detail、AbortError 语义、stream:true 解码、看门狗)

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `sseFetch` | 函数 | 唯一 SSE 传输入口,仅 `useChatStream`(模块 07)允许调用 |
| `splitFrames` / `parseFrame` | 纯函数 | 可单测 |
| `SseError(kind, status, message)` | 类 | kind: http/network/nobody/parse |

## 模块开发规范

### 本模块关键约束

- **传输层零业务语义**:不认识 store、不认识会话,只搬运事件
- `TextDecoder` 必须显式 `{stream: true}`(中文 3 字节跨片,坑 1)
- 坏帧丢弃计数,**绝不因单帧坏掉中断整条流**
- 不设总超时,静默看门狗 120s(每帧重置)
- 实现全文以 ARCHITECTURE.md §4.2 为准(用户誊写);Vitest 用例由 Claude 给全文
