# 知识库页 开发进度

> 编号: `09`
> 依赖模块: 04(+01 的 B7 建议)
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | 文档列表与删除 | ✅ | 模块04 |
| [task2](./task2.md) | 串行上传队列 | ✅ | task1 |

## 进度日志

### 2026-09-16

- ⬜ task1~task2: 未开始
- 备注:与模块 07/08 无依赖,可并行

### 2026-09-17

- ✅ task1: `KnowledgeView.vue`(列表状态 + 删除确认 + 复制反馈)+ `DocTable.vue`(加载 / 空态 / 错误重试三态)+ `DocRow.vue`(文件名 / doc_id 点击复制 / 入库时间 / 切片右对齐 / 复制 + 删除)+ `DeleteDocDialog.vue`(文件名 + 切片数回显、danger 确认、Esc 取消、按钮内联 loading、默认焦点给弹窗容器不误触回车)
- ✅ task2: `UploadPanel.vue`(拖拽 + `<input type="file" multiple>` 隐藏输入,串行闸门 `draining` + `nextQueuedIndex` 循环 `await`,一次只发一个;`File` 存旁路 `Map` 不进响应式)+ `UploadQueueItem.vue`(四态行 + `role="progressbar"` 进度条 + 失败重试)+ `xhrUpload.ts`(XHR `upload.onprogress` 拿进度,错误形状同 `ApiError`)
- ✅ 纯函数层 `utils/knowledge.ts`:`isOversize` / `makeQueueItem`(超限直接落 failed,不排队)/ `nextQueuedIndex` / `progressPercent` / `progressText`(100% 后切"解析入库中…")/ `doneText`(created:false → "已存在,已复用")/ `isDocGoneStatus` / `fmtBytes` / `fmtDateTime` / `shortDocId` / `sortDocsByCreatedAt`
- 契约过渡:`created:false` 不计失败,队列行与 toast 都说"已存在,已复用";`DELETE` 返 404 或 500 一律按"该文档可能已不存在,已刷新列表"提示并重拉列表;其余错误保留弹窗可重试
- 验证证据:vitest `src/utils/knowledge.test.ts` **17/17 通过**(体积预检边界、队列推进与重试迁移、进度归一与文案、判重文案、删除过渡状态码、格式化、排序不改入参);`npx vue-tsc --noEmit` **全项目 0 错误**;真实后端实测(`http://127.0.0.1:8001`)`GET /knowledge` 返回字段与契约一致(3 篇文档,`doc_id` 32 位 hex / `created_at` 6 位秒小数 + `+00:00`)、`DELETE /knowledge/{不存在 id}` 返回 **500** 且响应体为纯文本 `Internal Server Error`(无 `detail`)
- 未实测项(需浏览器端到端,交主会话统一验):进度条逐项推进与 2s 高亮时序、删除后行消失、`已复制` 内联反馈、真实拖拽入队、`created:false` 判重链路(需真实重复上传,属数据写入未执行)
- 偏差(受本模块文件边界所限,详见 [develop.md](./develop.md) 文末):ContextPanel 文档计数未落地(禁改 `layout/**`);XHR 上传包装未进 `api/knowledge.ts`(禁改 `api/**`);未新建 `composables/useAsync.ts`(共享件易与并行模块撞车,视图内联三件套)

## 相关事实(写给后续模块,排查沉淀)

- **删不存在的文档,500 的响应体没有 `detail`**:FastAPI 未捕获异常直接返回纯文本 `Internal Server Error`,所以过渡分支只能判状态码(`isDocGoneStatus`),不能指望 `errText` 拿到后端文案(它会退回 `HTTP 500`)。B7 落地后应改为 404 + `文档不存在:{doc_id}`。
- **`GET /knowledge` 的 `created_at` 是 6 位秒小数 + `+00:00`**(`datetime.isoformat()`),V8 能正常解析(单测已钉真实样本);`fmtDateTime` 显示 `MM-DD HH:mm`,完整值放 `title`。
- **上传响应里没有 `chunks`**:`{ doc_id, created, name }` 三字段,队列行的"N 切片"必须等列表刷新后按 `doc_id` 回填(`UploadPanel` 的 `chunkMap` prop)。
- **上传超时预算 120s**(契约 §3.6):XHR 的 `timeout` 设的是 120s,`fetch` 版封装同样是 120s;后端解析 + embedding 是同步阻塞,排队串行上传时总耗时按文件数线性叠加。
- **ContextPanel 文档计数是遗留缺口**:需要外壳模块/主会话在 `ContextPanel.vue` 按路由注入,数据源可用 `GET /knowledge` 的条数(本模块已按"局部状态"实现,未进 Pinia)。