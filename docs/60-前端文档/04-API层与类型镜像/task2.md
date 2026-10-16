# Task 2: 六资源封装(api/)

> 模块: `04-API层与类型镜像`
> 前置 task: task1
> 模块依赖: 02
> 状态: ✅ 已完成

## 目标

`src/api/` 六个资源模块封装完成,特殊请求形状(query 参数/multipart/URL 编码)全部在封装层消化。

## 前置准备

- [ ] task1 已完成并通过验收

## 实现步骤

1. **`api/knowledge.ts`**:list / upload(FormData,不设 Content-Type)/ remove;upload 返回处理 `created: false` 的类型标注(用户誊写)
2. **`api/memory.ts`**:list / remove(key `encodeURIComponent`)
3. **`api/skills.ts`**:list
4. **`api/mcp.ts`**:list / create(`?name=` + config body,文件头注释坑 12)/ remove / test(30s 超时)
5. **`api/chat.ts`**:threads / threadsMeta / threadMessages(B1 端点);`send` / `submitAnswer` / `submitConfirm` 只留函数签名,内部转发到模块 05 的 `sseFetch`(此时可先抛 `NotImplemented`)
6. **`api/health.ts`**:模块 02 已建,补齐类型引用

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/api/chat.ts` | 新增/修改 | SSE 签名占位 |
| `dev/front/src/api/knowledge.ts` / `memory.ts` / `skills.ts` / `mcp.ts` | 新增 | 用户誊写 |

## 验收标准

- [x] `vue-tsc --noEmit` 零错误
- [x] mcp.ts 文件头有 name-in-query 注释
- [x] 所有 fetch 调用都经 `request` 或 `sseFetch`,组件层无裸 fetch
