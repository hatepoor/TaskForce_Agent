# 记忆页

> 编号: `10`
> 英文标识: `memory-view`
> 状态: ✅ 已完成
> 最后更新: 2026-09-17

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [04-API层与类型镜像](../04-API层与类型镜像/develop.md) | `api/memory.ts` | list / remove(key 编码) |
| [03-应用外壳与路由](../03-应用外壳与路由/develop.md) | 原子组件 | `EmptyState` |

---

## 概述

长期记忆管理视图:列表(source 徽标)、本地过滤、删除确认。体量最小的视图模块。

## 功能清单

- **列表**:content 全文 + source 中文映射徽标(explicit→用户明示 / confirmed→自动确认)+ 本地时间
- **本地过滤**:前端 `includes` 匹配(后端无搜索参数,不假装成搜索接口)
- **删除**:确认弹窗完整回显原文

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `MemoryView` 及子组件 | 组件 | 挂 `/memory` 路由;ContextPanel 显示条目数 |

## 模块开发规范

### 本模块关键约束

- key 可能含中文/斜杠,删除必须 `encodeURIComponent`(已在 api 层封装,视图层勿二次编码)
- 空态区分"还没有记忆"与"检索失败"两种
- 后端固定 limit=100,UI 不承诺"显示全部"

### 落地说明(2026-09-17)

- 纯函数集中在 `src/components/memory/memoryFormat.ts`(排序 / 过滤 / source 文案 / 时间与条数文案),由 `memoryFormat.test.ts` 在 node 环境单测(14 条),组件层只做渲染与编排。

---

## 落地情况与偏差(2026-09-17)

**落地文件**

| 文件 | 说明 |
|------|------|
| `src/views/MemoryView.vue` | 页面装配:列表状态 + 本地过滤 + 主区五态(加载 / 读取失败可重试 / 无记忆 / 无匹配 / 列表)+ 删除确认;KeepAlive 下 `onActivated` 自动重取 |
| `src/components/memory/MemoryToolbar.vue` | 条数统计 + 过滤输入(本地 `includes`)+ 刷新(加载中内联 Spinner) |
| `src/components/memory/MemoryList.vue` | 条目列表容器,删除事件上抛 |
| `src/components/memory/MemoryItem.vue` | 单条:正文全文 / source 徽标(色彩区分 + title 释义)/ 相对时间(悬停显绝对时间)/ 删除 |
| `src/components/memory/DeleteMemoryDialog.vue` | 删除确认弹窗:完整回显原文 + 不可恢复提示 + danger 钮;Esc / 遮罩取消,删除中失效 |
| `src/components/memory/memoryFormat.ts` | 纯函数:降序排序 / 过滤 / source 文案 / 时间与条数文案 / 上限提示 |
| `src/components/memory/memoryFormat.test.ts` | 14 条单测(node 环境,无 DOM) |

**偏差(受本模块文件边界所限,需主会话或后续模块收口)**

1. **`ContextPanel` 记忆条目数未落地**:本模块不允许改 `src/components/layout/**`,ContextPanel 对 `/memory` 仍渲染占位文案。条数统计目前落在 `MemoryToolbar` 内(`data-testid="memory-count"`)。需主会话(或外壳模块)在 `ContextPanel.vue` 里按路由注入记忆列表 / 计数。
2. **删除确认弹窗未抽公共件**:`DeleteMemoryDialog.vue` 与模块 09 的 `DeleteDocDialog.vue` 结构同构(mask + role=dialog + Esc + danger 钮),但 `src/components/common/**` 不在本模块可写范围,未合并;后续收尾可抽 `ConfirmDialog` 原语。

**未实测项(需浏览器端到端,由主会话统一验)**

- 列表渲染、source 徽标的实际配色呈现、过滤输入即时生效的视觉反馈
- 删除后条目消失 + 刷新仍不存在(需真实 `DELETE`,属数据写入,本次未执行)
- 跨模块联动:模块 08 里确认写入的记忆出现在列表且 `source=confirmed`(需对话侧真实写入)
- 100 条上限提示(`limitHint`)仅在返回条数 ≥ 100 时出现,当前库内 4 条,未触发
