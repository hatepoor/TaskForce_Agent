# Task 1: sse.ts 传输层实现

> 模块: `05-SSE传输层`
> 前置 task: 无
> 模块依赖: 04
> 状态: ✅ 已完成

## 目标

`src/api/sse.ts` 完成,能对后端三个 SSE 端点发请求并逐帧回调。

## 前置准备

- [ ] 模块 04 的类型与 `api/chat.ts` 签名占位已就位
- [ ] ARCHITECTURE §4.2 完整实现已通读

## 实现步骤

1. **`splitFrames` + `parseFrame`**(用户誊写):
   - 文件: `dev/front/src/api/sse.ts`
   - 详情: CRLF 归一化、`\n\n` 切分、`data:` 多行合并、坏帧 null
2. **`SseError` + `sseFetch`**(用户誊写):
   - 文件: `dev/front/src/api/sse.ts`
   - 详情: 非 2xx 按 JSON detail 抛 http;AbortError 静默返回;`{stream: true}` 解码;收尾 `decoder.decode()` 冲残留 + 尾帧尝试;unknown 事件 warn 后继续
3. **`api/chat.ts` 三个 SSE 函数接通**(替换模块 04 的 NotImplemented):
   - 文件: `dev/front/src/api/chat.ts`
   - 详情: send / submitAnswer / submitConfirm 均转发 `sseFetch`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/api/sse.ts` | 新增 | 用户誊写 |
| `dev/front/src/api/chat.ts` | 修改 | 接通三函数 |

## 验收标准

- [x] 后端 task4(B4)已落地:curl -N 可见逐帧,浏览器实测 token 回调逐条触发
- [ ] B4 未落地(攒完一批):回调仍全部触发,只是集中到达——两种形态解析器行为一致
- [x] 停后端发请求 → `onError(SseError('network'))`;恢复端点 400 → `SseError('http', 400)` 含 detail

> 验收说明:B4 已落地(模块 01),按逐帧形态判定通过;"攒批"形态为同一解析器的累积输入(splitFrames 有单测覆盖),行为一致。network 分支以受控单测覆盖(浏览器经 vite proxy 时,后端不可达会先收到代理层 500,无法稳定复现 fetch 级网络失败);400 分支浏览器实测含 detail 原文("该会话没有待处理的挂起")。
