# 记忆页 开发进度

> 编号: `10`
> 依赖模块: 04
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | 记忆列表、过滤与删除 | ✅ | 模块04 |

## 进度日志

### 2026-09-16

- ⬜ task1: 未开始

### 2026-09-17

- ✅ task1: `MemoryView.vue`(列表状态 + 本地过滤 + 主区五态:加载 / 读取失败可重试 / 无记忆 / 无匹配 / 列表)+ `MemoryToolbar.vue`(条数文案 + 过滤输入 + 刷新,加载中按钮内联 Spinner)+ `MemoryList.vue`(列表容器,删除事件上抛)+ `MemoryItem.vue`(正文全文不折叠 + source 徽标色彩区分且 `title` 给释义 + 相对时间悬停显绝对时间 + 删除钮)+ `DeleteMemoryDialog.vue`(完整回显原文 + 「删除后智能体不再记得这条信息,不可恢复」+ danger 钮;默认焦点给「取消」,Esc / 遮罩可取消,删除中两者失效)
- ✅ 纯函数层 `components/memory/memoryFormat.ts`:`sourceMeta`(explicit→用户明示 / confirmed→自动确认 / 其余→来源未知,附释义)、`parseIsoMs`(缺失/非法一律 0)、`fmtMemoryTime`(相对时间)/ `fmtMemoryAbsolute`(悬停绝对时间)、`sortByCreatedAtDesc`(降序 + 缺失时间稳定落末尾)、`filterMemories`(纯前端 includes,大小写不敏感)、`countText`(过滤时补匹配数)、`limitHint`(≥100 条才提示上限)
- 契约核对:`GET /memory` 真实返回 4 条,已按 `created_at` 降序,`source` 为 `confirmed`/`explicit`,`created_at` 为 6 位秒小数 + `+00:00`(V8 `Date.parse` 正常解析,已钉单测样本);`key` 编码走 `api/memory.ts` 的 `encodeURIComponent`,视图层不二次编码
- 失败处理:`listMemories` 失败 → toast 原文 + 有旧数据保留旧数据、无数据时主区空态给「重试」;`removeMemory` 失败 → toast 原文 + 保留弹窗与原文可重试
- 验证证据:vitest `src/components/memory/memoryFormat.test.ts` **14/14 通过**(source 映射、时间解析与降级、降序与稳定性、过滤边界、条数/上限文案);全仓 `npx vitest run` **146/146 通过**;`npx vue-tsc --noEmit` **全项目 0 错误**
- 未实测项(需浏览器端到端,交主会话统一验):列表渲染与徽标配色、过滤即时反馈、删除后条目消失且刷新仍不存在(需真实 `DELETE`,属数据写入未执行)、模块 08 确认写入 → 列表出现 `confirmed` 条目的跨模块联动、100 条上限提示(当前 4 条未触发)
- 偏差(受本模块文件边界所限,详见 [develop.md](./develop.md) 文末):ContextPanel 记忆条目数未落地(禁改 `layout/**`);删除弹窗未与模块 09 的 `DeleteDocDialog` 合并成公共 `ConfirmDialog`(禁改 `components/common/**`)

## 相关事实(写给后续模块,排查沉淀)

- **`source` 两个值都要有徽标**:`explicit` = 用户明说「记住…」直写(不经过确认卡),`confirmed` = 智能体自主提案 + 用户确认。空串是缺字段,落到「来源未知」中性徽标,不要当成第三种写入路径。
- **`DELETE /memory/{key}` 幂等**:删不存在的 key 也返 200,所以前端删除成功后直接本地移除即可,不需要先做存在性校验,也不需要把 404/500 特殊化成"可能已不存在"(这点与模块 09 的 knowledge 删除不同)。
- **`GET /memory` 无分页、硬编码 `limit=100`**;UI 只在返回条数 ≥ 100 时提示"更早的记忆未列出"(`limitHint`),不承诺"显示全部"。
- **过滤是纯前端的,不匹配 `key`**:`key` 在 UI 上不展示,若参与匹配会出现"看不见原因"的命中,故只匹配 `content`。
- **管理页被 `KeepAlive` 缓存**:`AppShell` 对四个视图整体 KeepAlive,`onMounted` 只在首次进入时触发。记忆页用 `onActivated`(首次跳过,避免重复请求)在每次切回时重取 —— 这样对话里刚确认写入的记忆切页即可见。后续管理页(设置页等)如需"切回即最新",照此处理。
- **ContextPanel 记忆计数是遗留缺口**:需外壳模块/主会话在 `ContextPanel.vue` 按路由注入;条数数据源可用 `GET /memory` 返回的条数(本模块未进 Pinia,属页面局部状态)。