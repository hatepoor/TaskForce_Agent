# TaskForce 架构评审与改进方案(ARCH-REVIEW)

> 2026-09-04 成立多智能体团队(3 代码审查 + 3 权威调研 + 1 综合,共 7 agents / 156 次工具调用)对项目 Agent 架构做全面评审。**本文件只给方案,不包含任何代码改动**;落地拆分为 7 步迁移,详见 §5。本文件的决策依据已登记 [ADR-0011](adr/0011-static-prompt-memory-tools.md)。

## 1. 总诊断

**核心矛盾:每轮变化的动态内容被渲染进"应字节级固定的 SystemMessage",同时记忆未工具化、写入完全缺失、子结果用 HumanMessage 占 user 角色注入消息流——整体偏离当代"固定 system + 动态 messages + memory-as-tool + 精简路由"的 Agent 设计规范。** 用户的三个质疑(A 缓存 / B 记忆工具化 / C 整体架构)指向同一件事:**system 与 messages 的职责边界从未被清晰划分。**

## 2. 三个质疑的验证结论(均成立)

### A. 提示词动态化 → 前缀缓存失效 ✅
- **现状**:`agent/supervisor.py:59-60`、`agent/answer.py:44-45` 每轮把 agents.md 全文 + 记忆 top-5 渲染进同一个 `SystemMessage`;`$memory` 位于 `prompts/supervisor.md:38`,**其后的静态规则与输出格式随之每轮重算**;`make_llm` 无任何缓存配置。
- **权威依据**:Anthropic 官方 Prompt caching 文档明确——**system 中任何动态内容都会使该位置之后的整段缓存失效**,推荐 static-first / dynamic-last(静态进 system、动态进 messages);LangChain Models#prompt-caching 列出 provider 缓存配置与中间件(AnthropicPromptCachingMiddleware);LangChain Deep Agents 官方明确"静态前缀应变 + 记忆/技能动态即 cache bust"。
- **后果**:前缀缓存基本失效;同时违背项目自身 PROMPT-DESIGN §1.1"静态段 1-4 连续排列,未来若模型支持 prompt cache 可直接命中"的设计初衷(实现与设计相悖)。

### B. 记忆应工具化而非注入 ✅
- **现状**:`agent/memory_ctx.py:37-46` 每轮**无条件** `store.search(("memory","default"), query=last_user_text, top_k=5)` 塞进 system;supervisor 与 answer **各检索一次**,dispatch 回合 fan-in 回 supervisor 再路由一次,合计最多 3 次检索;query 硬编码为最后一条用户消息;`except Exception: return ""` 吞异常零日志;`USER_ID="default"` 硬编码。
- **权威依据**:LangChain 官方 **Long-term memory** 文档——标准示例即封装成工具(`get_user_info`/`save_user_info` via `runtime.store`),明确"Read/Write long-term memory in tools"而非注入 system;LangMem 官方库直接提供 `create_search_memory_tool` / `create_manage_memory_tool`;Anthropic 官方 memory tool 被定义为 "the key primitive for just-in-time context retrieval"。
- **后果**:每轮固定 embedding 网络往返(纯闲聊"你好"也触发);Agent 无法自主决定何时检索、换 query 重检、多次检索;记忆不进消息流、无 ToolMessage,调试不可见;检索失败零信号。

### C. 整体架构偏离当代规范 ✅(多点)
1. **记忆写入完全缺失**:`agent/build.py` 的 memory 节点是桩,全 src 无 `store.put`——只有读没有写闭环,记忆永远为空;
2. **路由太重**:supervisor 用"角色 + agents.md 全文 + 记忆 + 全量历史 + 输出格式"做分类路由,而官方 Router 应是轻量 prompt;agents.md/记忆正文不该进路由调用;
3. **消息角色污染**:`answer.py:46-47` 把子结果渲染成 `HumanMessage` 占 user 角色,迫使 `memory_ctx.last_user_text` 用 `startswith("子智能体结果已回收")` 字符串 hack 反查真实用户消息;
4. **无上下文管理**:每轮全量 messages 无裁剪/压缩/摘要,ADR-0009 承诺的"service.py 超阈值日志告警"未实现(PROMPT-DESIGN §1.2 承诺落空);
5. **装配偏离标准**:store 用 lambda 闭包注入 `build_graph`,而非 LangGraph 标准的 `graph.compile(checkpointer=..., store=...)` + 节点内经 `runtime.store` 访问;
6. **字符串 hack 遍地**:`RESET="__reset__"` 哨兵清空 subagent_results、桩判断靠 warnings 文本匹配 `"桩"`;
7. **agents.md 每轮读盘**:相对路径依赖 cwd,非仓库根启动(如 FastAPI 部署)时静默降级为占位符,系统提示词内容静默改变。

## 3. 完整问题清单(按严重度)

| # | 问题 | 严重度 | 证据(文件:行) | 权威依据 | 改进方向 |
|---|---|---|---|---|---|
| 1 | 动态内容渲染进 system,块级/前缀缓存失效 | high | supervisor.py:59-60、answer.py:44-45、memory_ctx.py:46 | Anthropic prompt caching(static-first/dynamic-last) | 静态 SystemMessage 构建期装配一次,动态内容进 messages |
| 2 | 记忆无条件注入非工具化 | high | memory_ctx.py:37-46、supervisor.py:58、answer.py:43 | LangChain Long-term memory / LangMem | 封装 `memory_search` @tool,按需调用 |
| 3 | 记忆写入完全缺失 | high | build.py memory 桩、grep 无 store.put | LangChain Concepts/Memory(hot path 写入) | `store_memory` 写工具 + 06 写入闭环 |
| 4 | 同一轮多次检索、supervisor/answer 上下文漂移 | high | supervisor.py:58 + answer.py:43 + fan-in 路由 | LangGraph node caching | 工具化后自然消除,或结果缓存 |
| 5 | 无上下文管理(全量 messages 无裁剪) | high | supervisor.py:73、service.py 无阈值日志 | Anthropic context engineering(context rot) | 先超阈值日志告警,再压缩 backlog |
| 6 | 子结果占 HumanMessage 角色污染 | medium | answer.py:46-47、memory_ctx.py:29-34 | LangChain 消息角色约定 | 结构化资源消息,删 startswith hack |
| 7 | agents.md 每轮读盘 + cwd 依赖 | medium | memory_ctx.py:21-26 | Deep Agents(启动装配一次) | build_graph 期读入缓存,路径入 settings |
| 8 | 无缓存命中观测,成本核算失真 | medium | settings/usage.py:30-32 | LangChain Models#prompt-caching | UsageTracker 采集 cache_read_tokens |
| 9 | 失败路径静默(路由/记忆都吞异常) | medium | supervisor.py:72-77、memory_ctx.py:39-42 | 可观测性规范 | 失败显式化(日志/错误消息) |
| 10 | supervisor 路由 prompt 过重 | medium | supervisor.py:57-59、prompts/supervisor.md 全文 | Anthropic Building effective agents(router 轻量) | 路由 prompt 精简,agents.md 不进路由 |
| 11 | store 闭包注入偏离标准 | low | build.py:56-65、memory_ctx.py:18 | LangGraph add-memory(compile(store=)) | `graph.compile(store=...)` + runtime.store |
| 12 | 字符串哨兵/RESET hack | low | state.py:17-23、supervisor.py:63-66 | 类型安全 | 对象哨兵 + 结构化桩标记 |
| 13 | 输出格式硬约束在动态块之后 | low | supervisor.md:47-51 在 $memory 之后 | 缓存前缀外 | 前移固定段尾部 |

## 4. 目标架构(target design)

```
固定层 system(构建期装配一次,字节级稳定,会话内不重渲染):
  角色/全局指令 + agents.md 全文 + 能力清单 + "## 输出格式"硬约束(前移)
  —— 不允许任何每轮变化的运行时数据进入;装配结果缓存(mtime/hash 失效)

动态层 messages(追加到末尾,绝不进 system):
  会话历史 + 当前用户消息 + 记忆检索结果(ToolMessage) + 子智能体结果(结构化资源消息,不用 HumanMessage)

记忆:memory_search(query, top_k) @tool(读,含 score/created_at,失败显式) 
      + store_memory(content, source) @tool(写,hot-path + interrupt 确认)
  —— Agent 判断需要时调用;system 只声明"可调用记忆工具",不含记忆正文

路由:supervisor prompt 精简为"角色 + next 四选一 + 能力清单 + JSON schema";
  agents.md/记忆正文不进路由调用;路由侧保留 memory_search 工具按需取

装配:graph.compile(checkpointer=..., store=...) 标准注入;节点内经 runtime.store 访问;
  user_id 由 settings 注入,统一 namespace ("memory", user_id)

观测:service.py messages 数/token 超阈值日志告警;UsageTracker 采集 cache_read_tokens,
  /stats 展示缓存命中率,作为缓存工程化收益的量化依据
```

## 5. 分步迁移(7 步,每步独立验收、不破坏现有功能)

| 步 | 内容 | 验收 |
|---|---|---|
| 1 | **文档先行**:PROMPT-DESIGN §4.2 把"prompt caching 明确不做"改为"静态前缀工程化";ADR-0011 登记 memory-as-tool + router 精简 + 固定 system;ROADMAP §7 登记 | 文档-代码一致,无自相矛盾 |
| 2 | **固定 system**:构建期装配静态 SystemMessage(角色+agents.md+规则+输出格式,load_agents_md 入 build 期,mtime 失效,路径入 settings);记忆段移出 system | 同一线程多轮 system 字节级一致(测试断言) |
| 3 | **记忆工具化**:`memory_search` + `store_memory` 两个 @tool(同 kb_search 模式);删除 retrieve_memory 注入与 $memory 渲染;USER_ID 改 settings 注入;读写工具行为测试 | 只在该工具被调用时才检索/写入;无命中/失败显式化 |
| 4 | **观测先行**:UsageTracker 采集 cache_read_tokens;REPL /stats 展示缓存命中 token/占比/节省成本 | 缓存是否生效可量化;质疑 A 有数据闭环 |
| 5 | **消息流清理**:子结果改结构化资源消息(metadata 标注来源,不用 HumanMessage);删 last_user_text startswith hack;service.py 超阈值日志告警 | 长会话有告警输出;角色不污染 |
| 6 | **装配规范**:`graph.compile(checkpointer=..., store=...)`;路由 prompt 精简为轻量;agents.md 只进 answer/ask 侧 | 图测试通过;路由 token 显著下降 |
| 7 | **写入闭环(06)**:store_memory hot-path 写入(显式 + interrupt 确认,source explicit/confirmed),与 memory_search 成闭环;配合 06 T3/T5 | 演示剧本:记住→新会话生效→/memory 可见 |

## 6. 风险与权衡(诚实标注)

1. **确定性收益 vs 缓存**:DeepSeek/火山方舟缓存为 LRU 淘汰、不保证命中——本方案只承诺"结构上不破坏缓存"(固定 system 前缀 + 动态不进 system),不承诺必然省钱;故 Step 4 先做观测,用数据说话。
2. **memory-as-tool 的代价**:多一次 LLM 工具调用(延迟/token)。若产品确要"每轮都有记忆背景"的 chatbot 体验,退化为"记忆追到 messages 用户消息之后、不进 system"(缓存前缀仍稳定),禁止回退到注入 system。
3. **路由精简的边界**:supervisor 看不到 agents.md 全文后,可能轻微影响 ask/memory 边界判断——用"路由侧保留 memory_search 工具按需取"补偿,回归验证 dispatch 识别率。
4. **agents.md 全文进固定 system**:当前 <1k token 可接受;若膨胀到数 k,参考 Deep Agents"system 只放摘要+索引、全文按需取"降级。
5. **06 未完成前的过渡态**:Step 2/3 若早于 06 写入落地,"记忆永远为空"的注入态会持续——期间用 T1 已建的 store 测试脚本造数据,或让 06 写入优先于 Step 3。
6. **provider 合并不保证顺序**:部分 provider 可能合并/重排 SystemMessage;Step 2 实现后用字节级断言确认固定前缀顺序。

## 7. 权威资料清单

- Anthropic:Prompt caching(docs.anthropic.com/en/docs/build-with-claude/prompt-caching)、Effective context engineering for AI agents、Building effective agents、Memory tool(docs.claude.com)
- LangChain / LangGraph:Long-term memory、Concepts/Memory、Add long-term memory、Stores、Graph API#node-caching、Models#prompt-caching、Deep Agents、Multi-agent 模式(Subagents/Router)、Personal Assistant(supervisor 实战)
- LangMem(github.com/langchain-ai/langmem)、OpenAI ChatGPT memory
