# ADR-0011: 固定 system + 动态 messages + 记忆工具化

> 状态:已定稿(2026-09-04)| 关联:ADR-0008(单一挂起点)、ADR-0009(多智能体架构修正)、ADR-0010(ReAct 子智能体)
> 背景:架构评审(见 `docs/ARCH-REVIEW.md`,7 agents 团队审查 + 权威调研)确认三处设计缺陷:①每轮把 agents.md 全文与记忆 top-5 动态渲染进 SystemMessage,破坏提示词前缀缓存(且与 PROMPT-DESIGN §1.1 自身"静态段连续排列以利缓存"相悖);②记忆检索未工具化,每轮无条件检索注入 system,Agent 无法按需检索,同一轮最多重复检索 3 次;③记忆写入完全缺失、子结果占 HumanMessage 角色、路由 prompt 过重。本 ADR 定稿修复方向,细化方案见 ARCH-REVIEW.md。

## 决议

| # | 决议 | 说明 |
|---|---|---|
| R1 | **固定 system,动态内容一律进 messages** | SystemMessage 构建期装配一次(角色 + agents.md 全文 + 能力清单 + 输出格式硬约束),字节级稳定,会话内不重渲染;会话历史、当前用户消息、记忆/子结果等动态内容全部追加到 messages 末尾。agents.md 在 build_graph 期读入缓存(路径入 settings,消除 cwd 依赖),不再每轮读盘 |
| R2 | **记忆工具化(memory-as-tool),废除注入式检索** | 封装 `memory_search(query, top_k)` 与 `store_memory(content, source)` 两个 @tool(同 kb_search 模式),由 Agent 判断需要时调用,结果以 ToolMessage 进消息流;删除 `retrieve_memory` 注入与 supervisor/answer 的 `$memory` 渲染。system 只声明"可调用记忆工具",不含记忆正文。依据:LangChain 官方 Long-term memory(memory as tools)、LangMem |
| R3 | **prompt caching 从"明确不做"改为"静态前缀工程化"** | 废除 PROMPT-DESIGN §4.2 对 prompt caching 的"明确不做(过度设计)";改为静态 system 前缀 + 动态段进 messages 的结构性工程化,配合 UsageTracker 采集 cache_read_tokens 做量化观测。注意:不承诺 provider 必然命中(LRU 语义),只承诺结构上不破坏缓存 |
| R4 | **路由 prompt 精简为轻量 router** | supervisor 提示词改为"角色 + next 四选一 + 能力清单 + JSON schema",不再注入 agents.md 全文与记忆正文;路由侧保留 memory_search 工具按需取。agents.md/记忆正文只在 answer/ask 侧按需使用。依据:Anthropic Building effective agents(router 轻量) |
| R5 | **写入闭环(hot-path)** | 记忆写入按 06 模块计划落地:`store_memory` 工具 + memory 节点显式写入/interrupt 确认写入,source 标 explicit/confirmed,与 memory_search 成读写闭环 |
| R6 | **装配规范化** | store 改经 `graph.compile(checkpointer=..., store=...)` 注入,节点内经 runtime.store 访问,废除 lambda 闭包;user_id 由 settings 注入(不再硬编码模块常量) |
| R7 | **可观测性补位** | 记忆检索/路由失败不再吞异常静默降级,失败显式化(日志 + 错误消息让模型可见);service.py 补 messages 数/token 超阈值日志告警(兑现 ADR-0009 承诺) |

## 红线(违反必踩坑)

1. **禁止把任何每轮变化的运行时数据放回 system**——记忆命中、子结果、时间戳等一律进 messages;记忆工具结果作为 ToolMessage,绝不渲染回 SystemMessage;
2. **记忆工具失败必须显式**(返回"未找到相关长期记忆"占位或错误文本),禁止 try/except 吞掉返回空串;
3. 固定 system 的实现须用测试断言"同一线程多轮 system 字节级一致",防 provider 或代码路径悄悄注入动态段。

## 影响

- **文档**:PROMPT-DESIGN §1.1(七段结构改为固定层/动态层划分)、§4.2(治理优先级);DESIGN §3(记忆检索/注入描述);ROADMAP §7 契约变更登记;本 ADR 与 ARCH-REVIEW.md 相互引用。
- **代码**(分步落地,见 ARCH-REVIEW §5,每步独立验收):memory_ctx 改造为工具、supervisor/answer 提示词装配、build_graph 注入方式、UsageTracker 扩展、service 告警。
- **顺序**:Step 1 文档先行(本 ADR 即其一);Step 2 固定 system;Step 3 记忆工具化;后续步骤不影响 06 模块主线,可穿插。
