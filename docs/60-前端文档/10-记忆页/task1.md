# Task 1: 记忆列表、过滤与删除

> 模块: `10-记忆页`
> 前置 task: 无
> 模块依赖: 04
> 状态: ✅ 已完成

## 目标

MemoryView 完整可用,与模块 08 的记忆写入联动验证。

## 前置准备

- [x] 模块 04 完成(`api/memory.ts` + `types/memory.ts` 已就绪)
- [x] 记忆库有测试数据(实测 `GET /memory` 返回 4 条:`confirmed` 2 条 + `explicit` 2 条)

## 实现步骤

1. **`MemoryView.vue` + `MemoryToolbar.vue` + `MemoryList.vue` + `MemoryItem.vue`**(用户誊写,线框见 UI-DESIGN §4.3):
   - 文件: `dev/front/src/views/MemoryView.vue`、`dev/front/src/components/memory/` 三组件
   - 详情: 条数统计 + 过滤输入框(本地 includes)+ 刷新;source 徽标;created_at 本地时区
   - 批注: 纯函数抽到 `src/components/memory/memoryFormat.ts`(排序 / 过滤 / source 文案 / 时间与条数文案 / 上限提示),node 环境单测,组件层只做渲染与编排;时间用 `fmtRelative` 相对文案,悬停 `title` 给绝对本地时间,缺失时间为空串时不渲染该 span
2. **`DeleteMemoryDialog.vue`**:
   - 文件: `dev/front/src/components/memory/DeleteMemoryDialog.vue`
   - 详情: 完整回显原文 + "删除后智能体不再记得这条信息,不可恢复";danger 钮
   - 批注: 默认焦点给「取消」、Esc / 点遮罩取消(删除进行中两者失效);失败保留弹窗与原文并 toast,便于直接重试
3. **ContextPanel 联动**:记忆条目数
   - 批注: **未落地**——本模块不允许改 `src/components/layout/**`,ContextPanel 对 `/memory` 仍渲染占位文案,需主会话/外壳模块收口;条数统计落在 `MemoryToolbar`(见 develop.md 偏差 1)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/views/MemoryView.vue` | 修改(替换占位) | |
| `dev/front/src/components/memory/MemoryToolbar.vue` / `MemoryList.vue` / `MemoryItem.vue` / `DeleteMemoryDialog.vue` | 新增 | 用户誊写 |
| `dev/front/src/components/memory/memoryFormat.ts` + `memoryFormat.test.ts` | 新增 | 纯函数与单测(14 条) |
| `dev/front/src/components/layout/ContextPanel.vue` | **未修改** | 受文件边界限制,见步骤 3 批注 |

## 验收标准

- [x] 列表按 created_at 倒序,source 徽标正确 —— 倒序由 `sortByCreatedAtDesc` 单测锁定(降序 / 缺失时间落末尾 / 稳定),`sourceMeta` 单测锁定两值映射为「用户明示」「自动确认」且文案与释义互不相同;真实 payload 核验:`GET /memory` 4 条已按 `created_at` 降序,source 为契约内的两个值。**浏览器端徽标配色呈现未实测**(主会话统一验)
- [x] 过滤为纯前端匹配,输入即时生效 —— 单测 3 条覆盖:空/全空白返回全部、子串匹配、大小写不敏感、前后空白忽略、不匹配 key 字段、无命中返回空数组;接线为 `computed` 派生(无请求、无防抖),"即时生效"是 computed 的固有行为,**视觉即时反馈未实测**
- [ ] 删除后条目消失,刷新仍不存在 —— **未实测**:需浏览器端到端 + 真实 `DELETE`(属数据写入,本次未执行);实现为 `removeMemory(key)` 成功后本地 `items.filter(key)` + toast「已删除该条记忆」,失败保留弹窗与原文并 toast 错误原因(key 编码由 `api/memory.ts` 的 `encodeURIComponent` 负责,视图层不二次编码)
- [ ] 模块 08 里确认写入的记忆出现在列表且 source=confirmed(跨模块联动) —— **未实测**:需对话侧真实写入(`POST /chat/confirm`);已用真实数据核验库内 2 条 `confirmed` 条目可正确映射为「自动确认」徽标,且视图在 KeepAlive 下每次切回都会 `onActivated` 重取,不需手动刷新

> 验证证据:14 条单测全绿(`npx vitest run src/components/memory/memoryFormat.test.ts`);全仓 146 条单测全绿;`npx vue-tsc --noEmit` 零错误。UI 端到端(渲染 / 删除 / 跨模块联动)交主会话统一验。