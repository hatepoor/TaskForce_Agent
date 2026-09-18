# ADR-0010: 子智能体统一采用 ReAct 执行模式

> 状态:已定稿(2026-09-04)| 关联:ADR-0006(并行派发)、ADR-0008(单一挂起点)、ADR-0009(多智能体架构修正)
> 背景:用户裁决"本项目 agent 采用 ReAct 模式"。此前期望散落在各模块文档:仅 09(executor)有 ReAct 锚点,05(retriever)是三节点固定管线(且已按管线实现),10(research)是外置状态循环设计,DESIGN.md 从未定义统一的执行模式。本次经三代理组(提示词重设计 / ReAct 主流调研 / 差距分析)讨论定稿,调研来源见 `docs/dev/react-refactor-plan.md` 附录。

## 决议

| # | 决议 | 说明 |
|---|---|---|
| R1 | **三个子智能体统一 ReAct 工具循环** | 模型节点 bind_tools → 有 tool_calls 执行工具并回填 ToolMessage → 无则收尾;差异仅在工具集、循环上限(retriever 5 / research 8 / executor 12)与收尾逻辑 |
| R2 | **supervisor 保持结构化路由,不改 ReAct** | 官方文档明确区分 router(结构化输出路由)与 ReAct supervisor;本项目主图即 router 模式的并行增强版,是文档认可形态;结构化路由对国产模型 JSON 输出更稳 |
| R3 | **手写循环,不用 create_react_agent / create_agent** | create_react_agent 在 LangGraph v1 已弃用;langchain v1 create_agent 是黑盒 + middleware 体系,且不支持预绑定模型,与"bind_tools + 共享键直挂 + 契约注入 + 收尾节点"组合有摩擦;手写循环覆盖 StateGraph/条件边/ToolNode/add_messages 全部核心概念,契合练手学习目标 |
| R4 | **共享骨架**:`agent/subagents/react.py` 提供 `build_react_subgraph(...)`,05/09/10 复用 | 防三套循环实现并存;05 先落地,09/10 接入 |
| R5 | **检索能力封装为 `kb_search` 工具**(去重 + 截断内聚在工具内) | 查询改写由 LLM 多轮调工具涌现(Agentic RAG,官方教程形态);确定性保障(去重/截断/空命中提示)不依赖 LLM |
| R6 | **双层防失控** | 子图自数 `max_iterations`,超限经条件边优雅收尾(partial + warnings,保住 need_clarification 语义);主图 `recursion_limit=25` 仅作全局兜底(ADR-0009 §2B 预算公式因此修订,见其 v3 补注) |
| R7 | **契约冻结不变** | TaskContract / ResultSummary 原样;`data={"hits": [...]}` 行为形状保持,由 finalize 从工具结果确定性重建,禁止 LLM 转述 |

## 红线(调研实证,违反必踩坑)

1. **ReAct 循环必须留在编译子图内部**——平铺进主图会让工具消息并进主图 messages 通道,经 `stream_mode="messages"` 泄漏到终端;
2. 子图私有消息键**不得命名为 `messages`**:直挂模式下父子图同键名即共享通道(模块 R 实测:子图 ReAct 消息经同名通道并进主图 messages 历史,supervisor/answer 全部可见);应命名如 `react_msgs` 并配 `add_messages` reducer(工具节点手写,无 prebuilt ToolNode 的键名契约);
3. 测试构造 fake AIMessage 时 tool_calls 的 `id` 必须与 ToolMessage 的 `tool_call_id` 配对;
4. 豆包 bind_tools 开工先探针(工具调用与结构化输出是两条能力线,与模型档位相关);并行工具调用仅部分模型支持,必要时显式关闭。

## 影响

- 新增**模块 R(ReAct 化改造,最高优先级插队)**:任务 T1-T9 见 `docs/dev/react-refactor-plan.md`;05 已实现的三节点管线作废,由 R-T3 重写;10 设计先行修正(未开工,无返工);09 本就是 ReAct,改为复用共享骨架。
- 提示词 4 件(supervisor/answer/base/subagents/retriever)已按 ReAct 语义重写(2026-09-04)。
- 文档同步:DESIGN §2、PROMPT-DESIGN §2.3/§2.5、05/09/10-DEV、ROADMAP §1/§6/§7、CONTEXT.md、ADR-0009 v3 补注。
