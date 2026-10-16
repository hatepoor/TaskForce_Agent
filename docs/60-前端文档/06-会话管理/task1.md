# Task 1: thread_id 生成与本地元数据

> 模块: `06-会话管理`
> 前置 task: 无
> 模块依赖: 04
> 状态: ✅ 已完成

## 目标

会话身份工具就位:前端生成合规 id,localStorage 存本地标题与时间。

## 前置准备

- [ ] 模块 04 完成;模块 01 的 task1~3 已完成(B1/B2/B3 可用)

## 实现步骤

1. **`src/utils/id.ts`**(用户誊写,全文见 ARCHITECTURE §M2):
   - 文件: `dev/front/src/utils/id.ts`
   - 详情: `sess-` + `crypto.randomUUID()`,非安全上下文降级分支
2. **`src/utils/time.ts`**:相对时间格式化(会话列表用)
3. **`src/composables/useLocalStore.ts`**:localStorage JSON 封装(版本号 + 容错)
   - 文件: `dev/front/src/composables/useLocalStore.ts`
4. **本地元数据读写**:键 `tf.threads`,结构 `{[threadId]: {title, createdAt, lastActiveAt}}`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/utils/id.ts` | 新增 | 用户誊写 |
| `dev/front/src/utils/time.ts` | 新增 | |
| `dev/front/src/composables/useLocalStore.ts` | 新增 | |

## 验收标准

- [x] `newThreadId()` 恒以 `sess-` 开头
- [x] 刷新页面后 localStorage 数据可读回
- [x] HTTP(非 localhost)访问时不抛 TypeError(降级分支生效)

> 验收说明:三条均由 `utils/id.test.ts` / `composables/useLocalStore.test.ts` 覆盖(`vi.stubGlobal('crypto', {})` 模拟非安全上下文;`createFakeStorage` 模拟刷新后重读);另在 headless 探针中实测浏览器真实 localStorage 写入 `{"v":1,"data":{...}}` 信封。
