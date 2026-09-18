# TaskForce 上下文设计方案

> 定稿于 2026-08-28。与 `DESIGN.md` 配套;术语见 `CONTEXT.md`。

## 0. 总原则:三层压缩,各归其位

上下文设计的本质是明确**每一步压缩由谁承担**:

1. **派发前压缩(Supervisor)**:把完整会话压缩成自包含的任务契约,经 Send 注入;
2. **子智能体内部压缩(子智能体)**:把多轮工具调用过程压缩成事实增量,模型只看局部投影;
3. **回传后压缩(子智能体 -> 主图)**:把执行过程压成结构化摘要,经 subagent_results 交回。

统一哲学:**模型上下文里永远只有"当前任务 + 局部事实";过程性信息放运行时状态,不塞回对话。**

## 1. 主智能体上下文

### 1.1 系统提示词:固定层(system)+ 动态层(messages)(ADR-0011)

> 2026-09-04 架构评审重构(见 `docs/ARCH-REVIEW.md` 与 ADR-0011):原"七段全进 system"改为**固定层(system,构建期装配一次,字节级稳定)+ 动态层(messages,追加末尾)**,兑现前缀缓存与 context rot 治理。原七段结构中"长期记忆 top-5 / 子智能体结果"两个动态段**移出 system,改为进消息流**;输出格式硬约束前移到固定段尾部,不再被动态段推后。

**固定层(system,构建期装配一次,会话内不重渲染;禁止任何每轮变化的运行时数据进入)**:

| 段 | 内容 | 归属 | 典型 token |
|---|---|---|---|
| 1 | 人设与全局指令(协调者身份、路由职责、诚实原则、简洁风格) | supervisor + answer | 200-300 |
| 2 | agents.md 全文(标注"权威背景,与长期记忆冲突时以此为准") | **仅 answer/ask 侧**;路由侧不注入(ADR-0011 R4) | ~500 |
| 3 | 路由架构 + 三个子智能体能力清单(各自适合/不适合、派发规则) | **仅 supervisor** | ~400 |
| 4 | Skills 元数据列表(name + description,07 模块按需) | 按需 | ~400 |
| 5 | 输出格式约束(Route schema JSON)/ 输出风格硬约束 | supervisor + answer,固定段**尾部** | ~300 |

**动态层(messages,一律追加到末尾,绝不进 system)**:

| 内容 | 形态 |
|---|---|
| 会话历史 + 当前用户消息 | 消息流(checkpointer 持久化) |
| 长期记忆命中 | ToolMessage(memory_search 工具按需调用,ADR-0011 R2) |
| 子智能体结果 | 结构化资源消息(metadata 标注来源,不用 HumanMessage 占 user 角色) |

**顺序理由**:静态段 1-5 在 system 内字节级连续,provider 前缀缓存可整段命中;记忆/子结果等动态内容全部落在 messages 末尾,不再破坏 system 前缀;输出格式硬约束固定在静态段尾部,始终位于缓存前缀内、贴近任务输入。

### 1.2 每轮调用的消息窗口(已作废)

> **⚠️ 本节已作废(2026-09-01 决议,ADR-0009 R1)**:滑动窗口方案废除,改为**上下文全量保留**(路由与汇总均用完整 messages);"压缩上下文"功能排入 backlog(阈值触发 LLM 摘要折叠,方案与模块后定)。全量保留过渡期在 service.py 加"消息数/token 超阈值"日志告警(只观测不阻断)。以下原文仅存档。

- ~~**路由调用**:messages 取最近 **10 条**;~~
- ~~**answer 汇总调用**:放宽到最近 **20 条**(需要更多上文组织最终回答);~~
- ~~超窗截断,不做滚动摘要(摘要需额外 LLM 调用且引入失真,v2 再说);用户显式引用早期内容时从 checkpointer 按需拉取。~~
- **subagent_results 消费即清**(仍然有效):answer 完成后清空该列表,下一轮 dispatch 重新累积--这是防止并行结果跨轮堆积的关键阀门(3 行代码)。

### 1.3 subagent_results 的呈现

不原文拼接,渲染成固定三键格式,每条形如:

```
[1] agent=retriever | 任务:<回显> | 结果:<conclusion + key_points> | 澄清:<needs_clarification,如有>
```

answer 直接基于摘要组织语言,不做二次转述;结果冲突时明示并说明采信理由;信息不足如实告知缺口,禁止补编。

### 1.4 主层 token 预算

- 单次输入:路由 5-9k / 汇总 6-10k,硬上限 10k,超限先砍历史窗口再砍摘要长度;
- 系统提示词固定 ~2.5k(固定税),历史窗口典型 ~3k,子结果 ~1k;
- 一轮典型消耗:纯 answer/ask/memory 约 6-7k;dispatch 往返(路由+汇总)约 13-16k。

## 2. 子智能体上下文

### 2.1 Send 携带的最小上下文:任务契约四件套

| 字段 | 内容 |
|---|---|
| `task` | 自包含任务描述:目标 + 输入 + 输出要求 + 成功标准 + 环境事实(supervisor 重构,非用户原话) |
| `user_utterance` | 用户原话(意图锚点,防重构失真) |
| `input_data` | 结构化输入:具体路径、文件、查询词、候选来源等,显式列出而非让子智能体推断 |
| `output_schema` | 结果摘要模板与长度约束 |

**明确不带**:完整消息历史、主图工具日志、长期记忆、其他子智能体的中间结果(交叉污染源)。子智能体的世界 = 系统提示 + 任务契约,不知道会话来龙去脉,不知道还有谁在并行。**Supervisor 是唯一叙事者**:子智能体决策需要的会话信息,必须由 supervisor 写进 task。

### 2.2 agents.md 注入策略(裁决:不切片,按智能体差异注入)

- **知识库检索智能体:不注入**--多余背景会污染查询改写与向量召回;
- **调研、执行智能体:注入全文**--agents.md 用户手写通常 <1k token,全文注入代价可忽略,免去切片解析的实现复杂度("能跑就行")。

(子架构师原方案为按小节切片注入,因增加实现复杂度被裁决简化;若日后 agents.md 膨胀再升级为切片。)

### 2.3 系统提示词骨架:共享底座 + 角色块

共享底座(三智能体通用,~200 字):声明"你只拥有本系统提示与任务契约,没有对话历史;信息不足时在 needs_clarification 标注,不编造;不与用户或其他子智能体对话;按结果摘要 schema 返回;跟随用户语言(默认中文)"。

角色块各自 ~300-500 字:

- **知识库检索(ReAct)**:持 kb_search(query, top_k=5) 单工具;先拆解任务产出 1-3 条查询逐条检索(复合问题拆开、指代补全、名词短语),命中不足可改写补检一轮;只基于命中 content 作答,不夹带模型自身知识;命中数据含 doc_id/filename/seq/content/score(score 越小越相似);无命中如实标 needs_clarification。
- **调研(ReAct)**:持 web_search 工具的搜-评-再搜循环(上限 8 轮,ADR-0010);每轮只评估候选结果的 title+snippet,仅对选定结果抓取全文;区分"检索到的"与"推断的";查不到就明说。
- **执行(ReAct)**:先从任务提取可验收的成功标准(不明则视为待澄清);文件读写等基础操作用内置工具(read_file/write_file/list_files,作用域为沙箱工作区);优先用已有 Skill 而非临场发挥;写操作前想清副作用,遵守任务中的路径约束;warnings 必须列出改过的文件、跑过的命令、遗留资源。

### 2.4 执行智能体的工具集控制

- **工具索引常驻**:所有工具(内置文件工具 + Skills 元数据 + MCP 工具)只注入 short_desc(名称 + 一句话用途,单条 ≤30 字),索引总量 ≤2k token;
- **按需拉详情**:提供 `get_tool_detail(name)` / `load_skill(name)` 工具,模型表达使用意图后再拉取完整 schema;
- **兜底**:索引超 3k token 时按任务类型预筛白名单(文件操作类/搜索类),不让模型硬啃;
- **工具返回截断**:搜索 snippet、沙箱 stdout/stderr 一律截断(如 10k 字符),防止单次工具结果撑爆窗口。

### 2.5 调研智能体内部循环控制(ADR-0010 修订:ReAct 特化)

循环状态即子图私有 `messages`(ReAct 循环,不再外置 facts/last_queries/round 三键)。原四闸门保留,重映射到 ReAct 机制:

1. 单轮截断:web_search 工具内只返回 top 3-5 摘要(title+snippet,每条 ≤300 字);
2. 评估只看摘要:全文仅对选中项抓取,用完即弃;
3. 上下文膨胀:messages 累积超阈值时提示模型尽快收尾("压缩上下文"backlog 承接进一步优化);
4. 硬上限:子图自数 iteration ≥8 即经条件边强制进收尾,不足则以 `partial` 状态诚实返回(不依赖主图 recursion_limit 一刀切)。

## 3. 结果摘要 schema(subagent_results 单项)

固定 key、定长约束,supervisor 按字段决策而非解析长文本:

```json
{
  "agent": "retriever | research | executor",
  "task_id": "Send 时分配的唯一 id",
  "task": "任务描述回显(≤100字)",
  "status": "success | partial | need_clarification | failed",
  "conclusion": "一句话直接结论(≤100字)",
  "key_points": ["要点(≤5条,每条≤50字)"],
  "data": {},
  "sources": ["id/url(≤10条)"],
  "needs_clarification": ["缺失项"],
  "warnings": []
}
```

`data` 按智能体约定:retriever 为命中条目(doc_id/title/score/snippet);research 为关键事实+来源;executor 为 files_changed/commands_run/artifacts。

supervisor 决策规则:success 且无澄清 -> 组合作答;need_clarification -> 走 ask 路由向用户追问;failed -> 降级或如实告知。

## 4. Token 成本治理

### 4.1 成本核算(面试可背诵)

一次典型对话(上传文档提问 -> 并行 1 检索 + 2 调研 -> 汇总)约 **10 次 LLM 调用、4 万 token(输入 3.6 万 + 输出 0.36 万),按豆包 pro 档约 4 分钱**。成本结构:系统提示词 ~2.5k 是与轮次无关的固定税;长会话历史是唯一跨轮复利部分。到"几毛钱"档的只有三种情况:256k 大档位模型、10+ 轮长会话不裁、派发数更多。

### 4.2 治理优先级

- **P0(做,几行代码)**:subagent_results 消费即清;工具返回截断;**固定 system 前缀工程化(ADR-0011:静态 system + 动态进 messages,让 provider 前缀缓存可整段命中)**;
- **P1(变更,ADR-0009 R1)**:~~固定滑窗(路由 10 条 / answer 20 条)~~ → 上下文全量保留 + 超阈值日志告警;"压缩上下文"为替代方案,排入 backlog(优先级提升:06 前或并行);
- **明确不做(过度设计)**:对话摘要压缩、动态工具选择、tiktoken 精确计量、多层记忆分层、用量配额限流、trim_messages 库(手写 3 行等价)、rerank。
  - ~~prompt caching 主动工程化~~ **已移除(2026-09-04)**:改列为 P0"固定 system 前缀工程化",见 ADR-0011 R3;不再以"过度设计"为由回避。

### 4.3 成本观测埋点(面试素材,合计 <30 行)

1. LLM 调用外层统一打点:读 API 返回的 `usage.prompt_tokens / completion_tokens`,记"节点名/model/in/out/耗时"结构化日志;
2. REPL `/stats` 命令:显示当前会话累计 token 与预估费用。

## 5. 落地顺序

1. 先定结果摘要 schema 与 Route/Task schema(契约先行);
2. supervisor 侧 `build_task_contract()`:会话 -> 四件套(含 agents.md 注入策略),三智能体共用;
3. 主层系统提示词组装器(静态前缀拼一次 + 每轮刷新动态段;消息全量保留,ADR-0009 R1);
4. 执行智能体工具索引 + 按需拉取;
5. 调研智能体 ReAct 循环控制(§2.5,ADR-0010 修订);
6. usage 打点与 /stats;
7. CLI 打真实问题端到端验证摘要质量与 token 消耗。
