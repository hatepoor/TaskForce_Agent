# SSE传输层 开发进度

> 编号: `05`
> 依赖模块: 04
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | sse.ts 传输层实现 | ✅ | 无 |
| [task2](./task2.md) | Vitest 单测 | ✅ | task1 |

## 进度日志

### 2026-09-17

- ✅ task1: sse.ts(splitFrames/parseFrame/SseError/sseFetch+静默看门狗 120s);chat.ts 三入口接通
- ✅ task2: sse.spec.ts 18 条用例(切帧/残帧/CRLF/五类事件+unknown/坏 JSON/多行 data/中文跨片/错误分支)— npm test 28/28
- 验收证据:浏览器探针 token 57 条逐条(1.16s~1.61s 流入)+ route/usage/done + 400 detail 原文;零 JS 异常
- 验收期修复(后端,连带发现):langchain-openai 1.x 默认 json_schema 被 DeepSeek 端点拒绝(400)→ 结构化路由被静默兜底、route 帧永不发出;改显式 method="function_calling"+兜底日志+回归测试(troubleshooting/common.md #5)
- 备注:B4 已落地,按逐帧形态验收;临时探针已删(备份 SseProbeView.removed.vue.bak)
