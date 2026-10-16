# Task 1: 文档列表与删除

> 模块: `09-知识库页`
> 前置 task: 无
> 模块依赖: 04
> 状态: ✅ 已完成(2 处偏差见实现步骤批注)

## 目标

KnowledgeView 列表 + 删除可用,ContextPanel 联动显示文档数。

## 前置准备

- [x] 模块 04 完成;后端 PG 已起且知识库有测试文档(实测 `GET /knowledge` 返回 3 篇文档,字段与契约一致)

## 实现步骤

1. **`KnowledgeView.vue` + `DocTable.vue` + `DocRow.vue`**(用户誊写,线框见 UI-DESIGN §4.1):
   - 文件: `dev/front/src/views/KnowledgeView.vue`、`dev/front/src/components/knowledge/DocTable.vue`、`DocRow.vue`
   - 详情: `useAsync` 三件套拉列表;doc_id 等宽字体点击复制;悬停整行高亮
   - 批注: **未新建 `src/composables/useAsync.ts`**(本模块文件边界不含 `composables/**`,且属记忆页/设置页共享件,并行开发易撞车),三件套在 `KnowledgeView` 内联实现;doc_id 显示为前 8 位 + `…`(线框同款),`title` 与复制内容均为完整 32 位 hex
2. **`DeleteDocDialog.vue`**:
   - 文件: `dev/front/src/components/knowledge/DeleteDocDialog.vue`
   - 详情: 显示文件名 + "切片将一并移除,不可恢复";danger 确认钮;删除中按钮内联 loading
3. **ContextPanel 联动**:文档计数展示
   - 批注: **未落地**——本模块不允许改 `src/components/layout/**`,ContextPanel 对 `/knowledge` 仍渲染占位文案,需主会话/外壳模块收口

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/views/KnowledgeView.vue` | 修改(替换占位) | |
| `dev/front/src/components/knowledge/DocTable.vue` / `DocRow.vue` / `DeleteDocDialog.vue` | 新增 | 用户誊写 |
| `dev/front/src/utils/knowledge.ts` + `knowledge.test.ts` | 新增 | 纯函数与单测(替代 `useAsync`,见步骤 1 批注) |
| `dev/front/src/composables/useAsync.ts` | **未新增** | 受文件边界限制,三件套在视图内联 |

## 验收标准

- [x] 列表字段与契约一致(实测 `GET /knowledge` 真实返回:`doc_id` 32 位 hex / `filename` / `created_at` 带时区 ISO / `chunks` 数字,渲染字段一一对应);`chunks` 右对齐为 CSS 声明(`.row__num { text-align: right }`),**浏览器呈现未实测**(主会话统一验)
- [ ] 删除后行移除 + toast,刷新仍不存在 —— **未实测**:需浏览器端到端;实现为 `removeDoc` 成功后本地 filter 移除行 + toast「已删除:{文件名}」+ 重拉列表
- [x] 删除不存在的文档按"可能已不存在"提示并刷新,不崩 —— 后端实测:`DELETE /knowledge/0000…0000` 返回 **500**(B7 未落地,响应体是纯文本 `Internal Server Error`,无 `detail`,故走 `ApiError(500)` 分支);前端 `isDocGoneStatus(404|500)` 分支有单测覆盖,UI 端到端未跑
