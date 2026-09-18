# Task 1: 类型镜像(types/ 六文件)

> 模块: `04-API层与类型镜像`
> 前置 task: 无
> 模块依赖: 02
> 状态: ✅ 已完成

## 目标

`src/types/` 六个文件完成契约镜像,`vue-tsc` 通过。

## 前置准备

- [ ] 通读 [API-CONTRACT.md](../../API-CONTRACT.md) §二全部端点与 §三 SSE 协议

## 实现步骤

1. **`types/api.ts`**:`ApiError`、`Result<T>` 通用包装(用户誊写)
2. **`types/chat.ts`**:RoutePayload / TaskPayload / `InterruptEnvelope {kind, text}` / UsageEvent / ErrorEvent / ChatItem 平铺联合 / TurnState / PendingInterrupt / ThreadMetaRow(全文见 ARCHITECTURE §5.3)
3. **`types/mcp.ts`**:`MCPServerConfig` 判别联合(stdio: command 必填 + args/env 可选;http: url 必填 + headers 可选),可选字段按契约"可能整个缺失"处理
4. **`types/knowledge.ts` / `memory.ts` / `skills.ts`**:KDoc / MemoryItem / SkillMeta(字段名严格按契约示例)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/types/api.ts` | 新增 | 用户誊写 |
| `dev/front/src/types/chat.ts` | 新增 | 用户誊写 |
| `dev/front/src/types/mcp.ts` | 新增 | 判别联合 |
| `dev/front/src/types/knowledge.ts` / `memory.ts` / `skills.ts` | 新增 | |

## 验收标准

- [x] `vue-tsc --noEmit` 零错误
- [x] `InterruptEnvelope` 的 kind 联合含 `'unknown'` 兜底
- [x] MCP 可选字段全部以 `?:` 声明
