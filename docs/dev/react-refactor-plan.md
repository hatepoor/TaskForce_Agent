# 模块 R:子智能体 ReAct 化改造计划(最高优先级,插队执行)

> 状态:计划定稿(2026-09-04),经三代理组(提示词重设计 / ReAct 主流调研 / 差距分析)讨论产出 | 决策记录:[ADR-0010](../adr/0010-react-subagents.md)
> 一句话:三个子智能体统一为 ReAct 工具循环(手写循环 + 共享骨架),supervisor 保持结构化路由;05 已实现的管线版 retriever 作废重写,10 设计先行修正。

## 1. 目标形态

### 1.1 拓扑(不变)

supervisor 结构化路由(with_structured_output → Route)→ Send 派发 → 子图 → fan-in → supervisor → answer;共享键直挂(ADR-0009 方案 A)不变;契约冻结(TaskContract / ResultSummary)不变。

### 1.2 子图标准形态(ReAct 手写循环,共享骨架)

```
START → agent(bind_tools) ──有 tool_calls 且 iteration<max──> tools(ToolNode) → agent
              └──无 tool_calls 或达上限───────────────────────→ finalize → END
```

- **ReactState(实现定稿)**:
  - 共享键(不动):`contract` / `subagent_results`;
  - 私有键:`react_msgs`(Annotated[list, add_messages];**实测修正(2026-09-04):不得命名为 `messages`**——直挂模式下父子图同键名即共享通道,子图 ReAct 消息会并进主图历史,supervisor/answer 全部可见)、`iteration`(自数轮数)。
  - hits 不设 state 键:finalize 从 react_msgs 中 kb_search 的 ToolMessage(JSON)确定性重建并跨调用去重(单一事实源,杜绝 LLM 转述)。
- **任务契约注入**:agent 节点首帧把 TaskContract 渲染为 SystemMessage(base + 角色块)+ HumanMessage(四件套)。
- **finalize 收尾**:
  - hits 为空 → `need_clarification` 摘要(不调 LLM,语义保留);
  - 达上限 → `partial` + warnings(["达到工具调用轮数上限,结果可能不完整"]);
  - 正常 → LLM 结构化 AnswerOut → ResultSummary(`data={"hits": [...]}`、`sources=doc_ids[:10]`,与现管线形状一致)。
- **双层防失控**:子图自数 max_iterations(retriever 5 / research 8 / executor 12,每轮 ≈2 super-steps);主图 recursion_limit=25 仅全局兜底(ADR-0009 §2B v3 补注)。

### 1.3 kb_search 工具(`tools/rag/kb_search.py`,新建)

- `@tool` 装饰;RAGStore 惰性单例(lru_cache,测试 monkeypatch 注入 FakeStore);
- 去重((doc_id, seq))+ content 截断(500 字)内聚在工具内(确定性保障不依赖 LLM);
- 空命中返回明确提示文本("知识库无相关内容");
- REPL `/kb` 与 11 的 `/knowledge` router 不受影响(仍直连 RAGStore)。

### 1.4 红线(见 ADR-0010)

循环留在编译子图内部;messages 键必须 add_messages;fake tool_calls 的 id 配对;豆包 bind_tools 先探针。

## 2. 代码影响图

**不动**:contracts/* 全部、state.py、supervisor.py、answer.py、stub.py(research/executor 桩保留至 09/10)、build.py 直挂方式、tools/rag/store.py、settings/*、cli/repl.py(/kb 已有)、test_rag / test_minimal / test_smoke。

**小改**:`src/agent/service.py` 流式过滤——由"排除 supervisor"改为主图节点白名单 `{answer, ask, memory}`(防子图内部 agent/tools 消息泄漏,风险 R1)。

**新建**:`tools/rag/kb_search.py`;`agent/subagents/react.py`(共享骨架 `build_react_subgraph(llm, tools, system_prompt, max_iterations, finalize_fn)`,05/09/10 复用);`tests/test_kb_search.py`。

**重写**:`agent/subagents/retriever.py`(管线 → 循环);`prompts/subagents/retriever.md`(已按 ReAct 重写 ✅);`tests/test_retriever.py`(FakeReActLLM 脚本化 AIMessage.tool_calls 序列;store 注入点迁移到 monkeypatch `tools.rag.kb_search._default_store`);`tests/test_graph.py`(FakeScriptedLLM 增 bind_tools 分发;轨迹断言改 `["supervisor","agent","tools","agent","finalize","retriever","supervisor","answer"]`,建议改子序列断言降低脆弱性)。

## 3. 分步任务(T1-T9;业务代码 Claude 给全文、用户誊写,测试 Claude 落盘)

| # | 任务 | 验收 | 规模 |
|---|---|---|---|
| T1 | kb_search 工具封装 + `tests/test_kb_search.py` | `uv run pytest tests/test_kb_search.py -q`;`uv run ruff check src/tools` | 1h |
| T2 | 共享骨架 `agent/subagents/react.py`(fake 冒烟,不接主图) | `uv run pytest -q` 不回归 | 1h |
| T3 | retriever 重写(循环 + finalize + hits 形状 + 无命中语义)+ test_retriever.py 重写 | `uv run pytest tests/test_retriever.py -q` 全绿 | 2-3h |
| T4 | 全图接线:build.py 挂真子图 + test_graph fake 扩展 + 全量回归 | `uv run pytest -q` 全绿 | 1-1.5h |
| T5 | 循环上限落地(达上限 partial;retriever=5) | `uv run pytest tests/test_retriever.py -k "cap or partial" -q` | 0.5h |
| T6 | 无命中 need_clarification 语义回归(不调收尾 LLM) | `uv run pytest tests/test_retriever.py -k "clarification" -q` | 0.5h(可并入 T3) |
| T7 | service.py 白名单过滤 + 豆包 bind_tools 探针 + REPL 泄漏实证 | REPL 手工观察 + run_turn 返回值无子图残留 | 1h |
| T8 | 真模型端到端验收(黄金剧本:上传→提问命中→引用;库外问题→诚实) | REPL 剧本 + `uv run pytest -q` + `uv run ruff check .` | 0.5-1h |
| T9 | 文档同步收尾(勾选 TODO/ROADMAP;grep 无"查询改写→检索"管线残留) | 通读 docs/ 一致 | 0.5h |

合计约 8-10h。T1→T2→T3→T4 顺序执行;T5/T6 可并入 T3/T4。

> **进度(2026-09-04)**:T1-T9 全部完成。T7 真模型探针完成(glm-5.3-flash bind_tools 可用,实测三坑已修并登记 troubleshooting/R #4-#5:测试清库→隔离 schema;glm QA 型收尾不调强制工具→finalize 解析最终消息零二次调用;轮数上限判据按最后消息);隔离库真模型全链路复验 **success,hits=11**;T8 用户 REPL 黄金剧本验收通过;T9 文档收尾完成(TODO/ROADMAP 置 ✅,grep 无管线残留)。

## 4. 风险与对策

| 风险 | 对策 |
|---|---|
| R1 子图消息经 stream_mode="messages" 泄漏(agent 的 tool_calls / kb_search 的 ToolMessage 打到终端;现管线 rewrite/organize 已有同类隐患,因 05 T4 未验收未暴露) | T7 白名单过滤 + ADR-0010 红线 1(循环留在子图内) |
| R2 并行多子图实例线程安全 | RAGStore 每次调用独立取 psycopg 连接(既有纪律);embed client 并发留 10 模块实测 |
| R3 豆包 bind_tools 兼容性(工具调用与结构化输出是两条能力线,与模型档位强相关) | T7 探针先行;不通过则核对 LLM_MODEL 档位 |
| R4 循环上限与 recursion_limit 交互(retriever 5 轮 ≈10 步,25 预算可能被单子图吃光) | 双层策略;不够按 ADR-0009 §6 上调 40(仅 config 数值) |
| R5 `data={"hits": ...}` 行为形状漂移 | finalize 从私有 hits 键确定性重建,禁止 LLM 转述 |
| R6 文档-代码双轨漂移 | T9 收尾核对;ROADMAP §7 已登记变更 |

## 5. 决策依据(团队调研来源精选,2026-09-04)

- LangGraph v1 弃用 create_react_agent / create_agent 迁移:docs.langchain.com/oss/python/releases/langgraph-v1、docs.langchain.com/oss/python/migrate/langgraph-v1
- 官方 ReAct 手写循环(模型节点 + ToolNode + 条件边)与 agentic RAG:docs.langchain.com/oss/python/langgraph/workflows-agents、docs.langchain.com/oss/python/langgraph/agentic-rag
- Router 与 supervisor 的区分(结构化路由是官方认可形态):docs.langchain.com/oss/python/langchain/multi-agent/router
- ToolNode 行为(handle_tool_errors / messages 键契约):reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolNode
- 流式与子图输出过滤:docs.langchain.com/oss/python/langgraph/streaming
- 豆包工具调用兼容性:volcengine.com/docs/82379/1355331 等

## 6. 整模块验收

- [ ] `uv run pytest -q` 全绿 + `uv run ruff check .` 全绿;
- [ ] REPL 黄金剧本:`/kb upload` → 提问命中引用文档;库外问题诚实 needs_clarification;
- [ ] 轨迹可见 supervisor → agent/tools/finalize 循环;工具过程不泄漏到终端;
- [ ] TODO / ROADMAP / 05-DEV 勾选同步。
