# Task 2: 串行上传队列

> 模块: `09-知识库页`
> 前置 task: task1
> 模块依赖: 04
> 状态: ✅ 已完成(1 处偏差:upload 未改 `api/knowledge.ts`)

## 目标

多文件上传队列:拖拽/选择 → 串行请求 → 四态行与进度条 → 成功刷新列表。

## 前置准备

- [x] task1 已完成并通过验收
- [x] UI-DESIGN §4.1 上传交互要点已通读

## 实现步骤

1. **`UploadPanel.vue` + `UploadQueueItem.vue`**(用户誊写):
   - 文件: `dev/front/src/components/knowledge/UploadPanel.vue`、`UploadQueueItem.vue`
   - 详情: `<input type="file" multiple>` + 拖拽区;20MB `file.size` 预检;队列串行推进(`XMLHttpRequest` 包一层拿 `upload.onprogress`);四态行;失败项可重试
   - 实现要点: 串行闸门 `draining` + `nextQueuedIndex` 取下一个排队项,循环内 `await` 单个请求,天然不并发;`File` 对象不进响应式状态(按 item id 存 `Map`),成功即释放;超限项落 `failed` 且不参与排队,`重试` 钮对超限项不显示(重试也无意义)
2. **判重与成功路径**:`created:false` toast"已存在,已复用";成功后刷新列表 + 新 doc_id 高亮 2s
   - 实现要点: 队列行文案 `已入库 / 已存在,已复用` 由 `doneText(created, chunks)` 现算,`chunks` 从刷新后的列表按 doc_id 回填(`UploadPanel` 收 `chunkMap` prop,两处共用同一份数据)
3. **失败文案**:后端 400/500 detail 原样展示
   - 实现要点: 失败行 `errText(e)` 原文 + toast;`errText` 兼容 500 纯文本响应体(退回 `HTTP 500`)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/knowledge/UploadPanel.vue` | 新增 | |
| `dev/front/src/components/knowledge/UploadQueueItem.vue` | 新增 | 用户誊写 |
| `dev/front/src/components/knowledge/xhrUpload.ts` | 新增 | XHR 包装(带进度);因本模块不允许改 `src/api/**`,`uploadDoc` 未改签名,XHR 版暂放此处,收尾模块可原样迁入 `api/knowledge.ts` |
| `dev/front/src/api/knowledge.ts` | **未修改** | 受文件边界限制(见上) |

## 验收标准

- [x] 串行推进不并发 —— `drain()` 单闸门 + 循环内 `await`,逻辑层由 `nextQueuedIndex` 单测钉住(跳过 done/uploading/failed);**选 3 个文件的实际进度条推进未实测**(需浏览器端到端)
- [x] 超 20MB 文件前端即拦,不发请求 —— 单测覆盖:`makeQueueItem` 直接落 `failed` + `OVERSIZE_MSG`,该状态不被 `nextQueuedIndex` 拾起;重试路径再次 `isOversize` 复检
- [ ] 重复上传同内容 → "已存在,已复用"提示,列表不出现重复项 —— 文案分支单测覆盖(`doneText(false, …)`);**判重链路未实测**(需真实重复上传,属数据写入,本次未执行;卡片 `created:false` 为契约 §2.3 已定义行为)
- [x] 失败项保留在队列可重试 —— 失败项留在 `items` 不弹出,`retry()` 置回 `queued` 并被下一轮 `drain()` 拾起(单测覆盖状态迁移);浏览器实测未做
