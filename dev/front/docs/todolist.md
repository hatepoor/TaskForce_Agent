# TaskForce 前端开发进度总览

> 最后更新: 2026-09-17

## 模块进度总览

| 编号 | 模块 | 进度 | 依赖 | 备注 |
|------|------|------|------|------|
| 01 | [后端契约改造](./01-后端契约改造/todolist.md) | ✅ | 无 | B1~B5 全部完成;模块 06/07 依赖阻塞已解除 |
| 02 | [工程脚手架](./02-工程脚手架/todolist.md) | ✅ | 无(验收依赖后端可跑) | Claude 代写完成;proxy 实测打通 |
| 03 | [应用外壳与路由](./03-应用外壳与路由/todolist.md) | ✅ | 02 | Claude 代写完成;headless 冒烟 36/36;折叠 bug 已修 |
| 04 | [API层与类型镜像](./04-API层与类型镜像/todolist.md) | ✅ | 03 | Claude 代写完成;headless 探针实测全过 |
| 05 | [SSE传输层](./05-SSE传输层/todolist.md) | ✅ | 04 | 含 Vitest 单测(18 条);验收期修复结构化路由 json_schema 坑 |
| 06 | [会话管理](./06-会话管理/todolist.md) | ✅ | 04 + 01(task1~3) | 会话列表/切换/历史回填/本地标题;轮次动作空壳留给 07 |
| 07 | [对话流](./07-对话流/todolist.md) | ✅ | 05 + 06 + 01(task4) | 轮次机制/流式渲染/轨迹/用量/错误态;08 依赖已解除 |
| 08 | [挂起交互](./08-挂起交互/todolist.md) | ✅ | 07 | ask/memory/unknown 三类卡;09/10/11 可并行 |
| 09 | [知识库页](./09-知识库页/todolist.md) | ✅ | 04 + 01(B7) | 列表/删除确认/串行上传队列;B7 未落地按 500 过渡 |
| 10 | [记忆页](./10-记忆页/todolist.md) | ✅ | 04 | 列表/本地过滤/删除;source 徽标区分 explicit/confirmed |
| 11 | [系统设置页](./11-系统设置页/todolist.md) | ✅ | 04 + 01(B6/B8) | Health 三态轮询/MCP 管理/Skills;按契约现状实现 |
| 12 | [生产集成收尾](./12-生产集成收尾/todolist.md) | ✅ | 01~11 全部 | 形态 B 同源托管 + 全链路验收 + 文档登记 |

## 进度日志

### 2026-09-16

- ✅ 01 后端契约改造:B1~B5 全部完成(curl 实测 token 帧逐条到达;全量回归 209 passed)
- ✅ 02 工程脚手架:Vite7 + Vue3.5 + TS 工程落地 — build/test/typecheck 全绿,proxy `/api/health` 实测透传;页面显示已由用户复核通过(全 ok);验收期修复后端 /health 沙箱误报(troubleshooting/11-api.md #6)
- ⬜ 03~12:未开始
- 备注:09/11 与 07/08 无相互依赖,可在 04 完成后穿插;03 依赖 02(已就绪)
- 备注:API 入口(src/api/main.py)已支持 IDE 直接运行;.env 锚定项目根,与工作目录无关

### 2026-09-17

- ✅ 03 应用外壳与路由:hash 路由 + 四段式外壳(导航轨/上下文栏/主区)+ 5 原子组件 + Toast — 落地
- 验收证据:vue-tsc 零错误、build 通过、vitest 10/10、headless Edge 冒烟 36/36;临时验证块已按流程移除
- 备注:新增依赖 vue-router@4.6.4 / pinia@3.0.4;04(API 层与类型镜像)依赖已就绪,可开工
- ✅ 04 API 层与类型镜像:types/ 六文件 + api/ 六资源封装完成(headless 探针实测 29 项全过,探针已删)
- 验收期修复(后端):/chat/threads/meta 500 — 带参 SQL 字面 % 未转义(psycopg);补真库回归测试、后端已重启(troubleshooting/common.md #4)
- ✅ 05 SSE传输层:sse.ts 传输层 + chat.ts 三入口接通 + 18 条单测;浏览器探针全过(token×57/route/400 detail),探针已删
- 验收期修复(后端,连带发现):结构化路由 json_schema 被 DeepSeek 拒绝致静默兜底(route 帧永不发出)→ 显式 function_calling + 回归测试(troubleshooting/common.md #5)
- ✅ 06 会话管理:utils/id + utils/time + composables/useLocalStore(版本信封+容错)、stores/chat.ts 骨架与回填、ThreadList/SessionItem、ContextPanel 注入、ChatView 装配 — 落地
- 验收证据:vue-tsc 零错误、build 通过、vitest 59/59(06 新增 31 条)、headless Edge 探针 20/20(真实后端 47 条会话/14 条历史逐条一致/挂起 ask 占位恢复/刷新保持/零 JS 异常),探针已删
- 备注:07(对话流)依赖 05 + 06 + 01(task4)全部就绪,可开工;06 的业务代码本轮由 Claude 落盘(用户指示,非常规教学模式)
- ✅ 07 对话流:store 轮次动作实现化 + useChatStream + Composer;MessageList/TurnBlock/UserBubble/AssistantMessage/RouteTrail/UsageBadge + markdown.ts(marked+dompurify);ErrorNotice 三形态与贴底六规则 — 落地
- 验收证据:vue-tsc 零错误、build 通过、vitest 77/77(07 新增 18 条)、headless 探针 18/18(真实模型流式:纯文本→Markdown、用量角标本轮增量、轨迹条默认折叠、断网错误条+草稿保留+重试不重复插气泡、停止接收灰字提示、零未捕获异常),探针已删
- 依赖新增:marked@^18.0.13、dompurify@^3.4.15
- 备注:08(挂起交互)依赖已解除;轨迹展开态与回底胶囊断言并入 08 探针
- ✅ 08 挂起交互:InterruptCard 分发 + AskInterruptCard(内联输入/自动聚焦/原地折叠)+ MemoryConfirmCard(proposal 引用块/忽略默认焦点)+ unknown 兜底卡;store 补 endTurn 落定 submitting 卡、failTurn 400 分支(toast + 刷新) — 落地
- 验收证据:vue-tsc 零错误、build 通过、vitest 80/80、headless 探针 21/21 + 忽略路径专项探针 2/2(真实后端/模型:ask 作答折叠续写、memory 记入后 source=confirmed、忽略不写入、unknown 兜底、轨迹展开、回底胶囊),探针已删
- 事实澄清:「记住 X」是 T3 显式直写不挂起,只有自主提案才出确认卡(08 task2 验收原文措辞与后端语义不符,已在模块文档登记)
- 备注:09/10/11 三个独立页面并行开发中
- ✅ 09 知识库页:UploadPanel(串行闸门 + XHR 进度 + 四态队列)/ DocTable+DocRow(列表三态 + doc_id 复制反馈)/ DeleteDocDialog(回显文件名与切片数);`utils/knowledge.ts` 纯函数 17 例
- ✅ 10 记忆页:MemoryToolbar(条数 + 本地过滤)/ MemoryList+MemoryItem(source 徽标)/ DeleteMemoryDialog(回显原文);`memoryFormat.ts` 纯函数 14 例;KeepAlive 下 onActivated 自动重取
- ✅ 11 系统设置页:HealthSection+HealthCard(三态 + 30s 轮询 + 可见性暂停)/ McpSection 全套(列表/徽标/新增抽屉/连通性测试/删除确认)/ SkillsSection 只读;`healthModel.ts`+`mcpModel.ts` 纯函数 35 例 + SSR 渲染冒烟 9 例
- 三模块均由子代理落盘、主会话抽检(读实现 + 跑测试);页面级端到端由模块 12 探针统一验
- ✅ 12 生产集成收尾:`src/api/main.py` 条件挂载 StaticFiles(形态 B 同源托管);形态 B 探针 30/30 + 设置页专项 13/13;UI-DESIGN 九条清单逐条核对;README(前端起步段 + 端口注意)、`docs/dev/TODO.md` 登记
- 验收期发现:本机 8000 是沙箱 SSH 隧道(`SANDBOX_URL=http://127.0.0.1:8000`),形态 B 同端口会自指递归拖死服务 → 改 8010 验收,已写入 README
- 全仓状态:vitest 154/154(13 文件)全绿、`npx vue-tsc --noEmit` 零错误、`npm run build` 通过;等待用户执行全量测试(前端 vitest + 后端 pytest)
- **最终全量测试(用户执行,全绿)**:前端 `npm run test` + `vue-tsc --noEmit` + `npm run build` 全过;后端 `uv run pytest -q` + `uv run ruff check .` 全过
- 验收期修复(后端 lint,先前会话遗留):`health.py` 超长注释行、`usage.py` import 顺序、`test_api.py` 超长行 → `ruff check .` All checks passed,`pytest tests/test_api.py` 16 passed
- 备注:端口冲突一事经用户确认**不沉淀**到 docs/troubleshooting
- **前端 12 个模块交付完成 ✅**

### 2026-09-18(交付后体验优化,用户提出)

- ✅ **设置页分节独立**:`/settings/:section(mcp|skills|health)?` 三条子路由 + 侧栏节列表(`SettingsNav.vue`)切换;弃用原先的页内锚点(`scrollIntoView` 在内容不高时"点了没反应",且与 UI-DESIGN §1.2"上下文栏=节列表"的既定设计不符——现在与设计对齐)。`SettingsView` 只渲当前节,刷新/深链直达可用。
- ✅ **知识库 / 记忆侧栏内容**:新增共享数据源 `composables/useDocsFeed.ts` / `useMemoriesFeed.ts`(主区与侧栏读同一份,上传/删除两边同步;并发拉取合流);侧栏列表 `DocMiniList.vue` / `MemoryMiniList.vue`,点击把主区对应行滚入视野并高亮 2s(与"刚上传行"同一套反馈)。
- ✅ **对话页 AI 头像 + 思考动效**:新增 `AiAvatar.vue`(三点连线中性图标,思考中描边转强调色并呼吸);`AssistantMessage` 在"已开轮但还没有 token"期间显示三点跳动(覆盖装配图 / MCP / 首字延迟的等待),token 到达即切换为正文 + 光标。
- 验收:vitest **158/158**(设置页 SSR 冒烟按新分节行为重写:4 条);`vue-tsc` 零错误;`npm run build` 通过;headless 探针 **18/18**(分节切换与刷新停留 / 侧栏列表条数与 API 一致 / 点击定位高亮 / 头像与动效出现与收束 / 零未捕获异常)
- 坑位(vue-router):**可选参数缺失时 `route.params.x` 是空字符串而非 `undefined`**,直接 `typeof === 'string'` 判断会取到空串 → 高亮态失效;判空串再回落默认值。
- 配置调整:`vite.config.ts` 代理目标默认从 8000 改为 **8001**(与 `api/main.py` 默认端口一致,并避开 8000 的沙箱隧道),`.env.development` 注释同步。
- UI-DESIGN 偏差(按用户要求,已在设计文档就地标注):AI 回复补头像;动画从"仅轨迹点呼吸"扩展为"轨迹点 + 头像呼吸 + 思考三点"。

### 2026-09-18(Web 侧主动汇总闭环,用户报"结果回来后主智能体不主动回答")

- ✅ **后端(Claude 落盘,用户指示"我直接改")**:`TaskManager` 结果带会话线程归属 + `on_done` 改全批完成才触发 + 非消费 `status(thread_id)` peek;`route_node` 经 LangGraph 注入的 config 取 `thread_id`(按线程 drain/submit);`AUTO_NOTICE` 上移到 `agent/service.py`;`GET /chat/tasks` + `POST /chat/summary`(守卫:无待汇总结果 400);历史回填过滤 `(系统通知)` 前缀;**零 token 轮整段补发 token 帧**——派发确认/记忆确认文本此前在 Web 上完全不下发(那一轮只显示"本轮没有产生文本输出"兜底文案)。
- ✅ **前端**:`useTaskWatch.ts` 3s 轮询(页面隐藏 / KeepAlive 失活暂停、15 分钟上限、**用户轮优先**、切走会话不代汇总),`pending === 0 && done > 0` 且空闲时自动发起汇总轮(不插用户气泡);`ThreadMeta.awaitingTasks` 随本地元数据持久化——**刷新页面后继续等**,不必重新提问。
- 语义对齐 REPL:`_auto_summary_worker` 的 turn_lock"用户询问优先、答完自动汇总"在前端由"流式中不发、下一拍再试"实现;两边共用 `AUTO_NOTICE` 触发语与同一条 `run_turn` 业务层(双入口红线)。
- 验收证据:后端 **216 passed** + `ruff check .` 全绿(新增 tasks 归属/全批/peek、route_node 按线程 drain、`/chat/tasks`+`/chat/summary`、零 token 补发等用例);前端 **vitest 167/167** + `vue-tsc` 零错误 + `npm run build` 通过;httpx 探针跑通全链(派发 → peek 12s 后 `{pending:0,done:1}` → 汇总轮出正文 → 回读 0/0 → 历史无触发语泄漏);**headless 浏览器探针实测**:只输入一次派发问句,12 秒后汇总自动出现、输入框为空(用户未再输入)。
- 设计文档同步:API-CONTRACT §2.1.7/§2.1.8 新增 + §三 route 注更新;README「开放项」与 UI-DESIGN §7.2 由"首版不做"改为**已落地**(批次卡 SubagentBatchCard 取消);ARCHITECTURE 的 `ThreadMeta` 形状补 `awaitingTasks?`。

### 2026-09-18(设置页新增"模型"节:主模型 / Embedding 接入配置)

- ✅ **后端(新 router)**:`settings/model_overrides.py`(覆盖表读写 + 合并规则 + 掩码)+ `settings/config.py` 在 `get_settings()` 叠加覆盖、新增 `applied_overrides()` / `effective_config()` + `api/routers/model_settings.py` 的 `GET/PUT /models/config`;覆盖表落 `.taskforce/model_config.json`(.gitignore 已含),**`.env` 仍是默认值来源,不写回**。
- ✅ **前端**:设置页第 4 节"模型"(`/settings/:section` 扩为 `…|models`),`ModelsSection.vue` + `ModelCard.vue` + `modelsModel.ts`;顶部 OpenAI 兼容协议提示(`/chat/completions`、`/embeddings`),保存后按 `restart_required` 显示"重启后端生效"横幅,每张卡"恢复 .env 默认"。
- **安全/契约**:`api_key` 只回掩码(前后各 4 位),原文不出网关;PUT **只发改动项**(缺项=不动、空串=清除覆盖、掩码=保持不动),避免"全量提交把 .env 现值复制成覆盖、日后改 .env 被静默压住"。
- 验收:后端 `tests/test_model_settings.py` **12 passed**、全量 **236 passed** + ruff 全绿;前端 vitest **176/176** + `vue-tsc` + build 通过;headless 探针实测(掩码回显 / 改一项保存→徽标 1 项+重启横幅+输入框保持新值 / 恢复默认回落 / 落盘只含改动项 / 零未捕获异常)。
- 探针发现并修复的两处缺陷(首版实现):① 全量提交把未改动的 `.env` 值写成覆盖;② GET 返回"运行中值"导致保存后输入框被旧值盖回——改为返回"`.env`+覆盖表"(重启后口径)。

### 2026-09-18(观感打磨 + 感知性能,用户提"页面有点丑、有点卡")

- **先测再改**:CDP Tracing 实测(切 38 条消息的会话回填 + 真流式一轮,并按 4× CPU 降速复测)——**无任何 ≥40ms 长任务**,最重任务 3–5ms;后端接口 5–165ms。结论:渲染层无卡顿,**Web Worker 没有可卸载的负载**,不做多线程;改做"感知性能"。
- ✅ **去半成品感(最大来源)**:会话列表原样显示 `sess-xxx` + "未命名会话" → 改**标题为主**(回填时用首条用户消息补标题,`titleFromText` 截 20 字)、时间/短 id 为辅且 **id 仅悬停/当前项显形**;`loadThreads()` 后**预热最近 12 个会话**(回填顺带补齐标题 + 切换秒开,失败静默)。
- ✅ **消息区**:用户消息加描边气泡(右下角收口 `r-lg r-lg r-sm r-lg`);AI 头像改圆形徽标(`--r-full` + 加深描边 + 加粗字形);轨迹条改**胶囊**并左对齐 AI 正文(40px);Markdown 补 h1–h4/strong/li/blockquote/hr/表头/图片样式;正文行高与段落间距收紧。
- ✅ **导航轨**:品牌标记 + **文字标签**(对话/知识库/记忆/设置)+ 状态点接**真实轮询**——`useHealthPoll` 从 `components/settings/` 移到 `composables/` 并改**模块级单例**(导航轨与设置页共用一份数据、只跑一条轮询,11 模块文档里登记的「NavRail 接线」遗留项落地);删掉"假数据"占位与 TODO。
- ✅ **骨架屏与微交互**:历史回填由"正在加载…"改**骨架屏**(与最终版式同形,不跳版);轮次入场 160ms 淡入;动效统一带 `prefers-reduced-motion` 兜底;输入区圆角加大 + 焦点环 + 发送键主色;页头 `sess-` 原始 id 限宽省略。
- **一致性核对(未改代码)**:知识库/记忆表格的行悬停与各视图页标题(16px/600)本已一致,无需调整。
- 验收:`vue-tsc` 零错误、vitest **179/179**(新增:回填补标题 2 条、会话预热 1 条)、`npm run build` 通过;headless 深色截图逐项核对(标题齐、气泡/头像/胶囊轨迹/骨架屏/标签导航轨/真实状态点),零未捕获异常。
