# 知识库页

> 编号: `09`
> 英文标识: `knowledge-view`
> 状态: ✅ 已完成(1 项交付偏差:ContextPanel 文档计数未落地,见文末)
> 最后更新: 2026-09-17

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [04-API层与类型镜像](../04-API层与类型镜像/develop.md) | `api/knowledge.ts` | list / upload(FormData)/ remove |
| [01-后端契约改造](../01-后端契约改造/develop.md) | B7(建议;未落地删除按 500 兜底) | 404 / 400 语义 |
| [03-应用外壳与路由](../03-应用外壳与路由/develop.md) | 原子组件 | `EmptyState`、`Spinner` |

---

## 概述

知识库管理视图:文档列表、删除、多文件串行上传队列(带进度)。可与模块 07/08 并行开发。

## 功能清单

- **文档列表**:DocTable(filename / doc_id / created_at / chunks),复制 doc_id
- **删除**:确认弹窗(显示文件名)、失败刷新列表
- **上传队列**:多选拆串行单文件请求,四态行(排队/上传中带进度/成功/失败可重试),20MB 前端预检,`created:false` 判重提示

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `KnowledgeView` 及子组件 | 组件 | 挂 `/knowledge` 路由;ContextPanel 显示文档数 |

## 模块开发规范

### 本模块关键约束

- **串行上传**,不并发(后端同步阻塞 + embedding,并发只会让进度打架)
- 上传进度用 `XMLHttpRequest.upload.onprogress`(fetch 拿不到上传进度)
- FormData 不手动设 Content-Type
- ContextPanel 文档列表复用同一数据源,加载一次两处共享(页面局部状态即可)

---

## 落地情况与偏差(2026-09-17)

**落地文件**

| 文件 | 说明 |
|------|------|
| `src/views/KnowledgeView.vue` | 页面装配:列表状态 + 上传队列 chunkMap + 删除确认 + 复制反馈 |
| `src/components/knowledge/DocTable.vue` | 表格三态(加载 / 空态 / 错误重试)+ 表头 |
| `src/components/knowledge/DocRow.vue` | 单行:文件名 / doc_id(点击复制)/ 入库时间 / 切片(右对齐)/ 复制 + 删除 |
| `src/components/knowledge/DeleteDocDialog.vue` | 删除确认弹窗(文件名 + 切片数 + Esc 取消 + 按钮内联 loading) |
| `src/components/knowledge/UploadPanel.vue` | 拖拽 / 多选 → 串行队列 → 成功回传 doc_id |
| `src/components/knowledge/UploadQueueItem.vue` | 四态行(排队 / 上传中带进度条 / 已入库 / 失败可重试) |
| `src/components/knowledge/xhrUpload.ts` | XHR 上传包装(带进度),错误形状同 `ApiError` |
| `src/utils/knowledge.ts` | 纯函数:体积预检 / 格式化 / 队列推进 / 判重与删除过渡文案 |
| `src/utils/knowledge.test.ts` | 17 条单测(node 环境,无 DOM) |

**偏差(受本模块文件边界所限,需主会话或后续模块收口)**

1. **ContextPanel 文档计数未落地**:本模块不允许改 `src/components/layout/**`,ContextPanel 对 `/knowledge` 仍渲染占位文案。需要主会话(或外壳模块)在 `ContextPanel.vue` 里按路由注入文档列表组件 / 计数。
2. **XHR 上传包装未进 `api/knowledge.ts`**:本模块不允许改 `src/api/**`,故 `uploadDocWithProgress` 暂放 `src/components/knowledge/xhrUpload.ts`(复用 `api/http` 的 `BASE` / `ApiError`)。收尾模块可原样搬迁进 `api/knowledge.ts`,组件侧只改 import。
3. **未新建 `src/composables/useAsync.ts`**:`composables/**` 不在本模块可写范围(且属记忆页/设置页共享件,并行开发易撞车),`KnowledgeView` 内联了 loading / error / run 三件套。共享 composable 落地后可平滑替换。

**未实测项(需浏览器端到端,由主会话统一验)**

- 进度条逐项推进的视觉表现、成功行 2s 高亮、删除后行消失、`已复制` 内联反馈的时序
- 真实拖拽入队(代码路径与选择文件共用 `addFiles`,仅事件源不同)
- `created:false` 判重路径(需真实重复上传,属数据写入,未在本次验证中执行)
