# Python 风格规范(python-camel-style)违规清单 — 2026-09-25

> 规范出处:`~/.agents/skills/python-camel-style/SKILL.md`(驼峰命名、悬挂缩进 8 格、尾逗号、一行一参数、避免正则,与 PEP 8 有意不同)。
> 本次为**存量检查**,按用户决定**不修代码**;后续"谁改到谁顺手改",以本清单为工作底单。命名类问题(变量/函数/参数/键名)本次未排查。

## 一、总览

| 规则 | 违规数 | 说明 |
|---|---|---|
| 悬挂缩进(续行应=首行+8,闭括号=首行) | **524 条语句 / 731 块** | 738 个跨行括号块中仅 7 个合规——整库是统一 PEP 8/Black 风格(续行 +4),系统性不一致 |
| 尾逗号(多行结构末项) | **332** | 展开的调用/字典/列表末项缺逗号 |
| 一行一参数 | **216** | def 多参数、展开调用的参数未逐行 |
| 展开边界 | **77** | 过度展开 25 处(≤100 字符且 ≤3 参数却拆行)+ 单行挤参数 52 处(>3 参数一行) |
| 正则滥用 | **2** | 见 §四 |
| 合计 | **≈1150** | 91/135 个文件有违规;单行超 100 字符 **0 处** |

结论:这不是零星疏漏,而是"整库与规范系统性不一致"。零违规 exemplar:`src/tools/tool/clock.py`(无多行结构)。

## 二、按文件统计(违规数降序;悬挂/尾逗号/一参/正则/边界/合计)

| 文件 | 悬挂 | 尾逗号 | 一参 | 正则 | 边界 | 合计 |
|---|---|---|---|---|---|---|
| src/rag_v01/tests/test_evaluate.py | 28 | 36 | 35 | 0 | 1 | 100 |
| tests/test_graph.py | 42 | 35 | 20 | 0 | 2 | 99 |
| tests/test_api.py | 28 | 15 | 21 | 0 | 0 | 64 |
| tests/test_api_history.py | 23 | 17 | 19 | 0 | 1 | 60 |
| src/cli/repl.py | 12 | 13 | 20 | 0 | 3 | 48 |
| src/rag_v01/tests/test_chunk.py | 16 | 24 | 1 | 0 | 5 | 46 |
| src/rag_v01/evaluation.py | 25 | 10 | 7 | 0 | 2 | 44 |
| src/rag_v01/store.py | 23 | 9 | 6 | 0 | 2 | 40 |
| src/agent/planner.py | 11 | 16 | 2 | 1 | 1 | 31 |
| tests/test_research.py | 14 | 9 | 3 | 0 | 0 | 26 |
| src/agent/contracts/summary.py | 8 | 8 | 0 | 0 | 7 | 23 |
| tests/test_retriever.py | 9 | 8 | 6 | 0 | 0 | 23 |
| src/api/routers/chat.py | 7 | 7 | 1 | 0 | 7 | 22 |
| src/rag_v01/tests/test_embed.py | 12 | 5 | 2 | 0 | 2 | 21 |
| src/rag_v01/tests/test_store.py | 18 | 2 | 0 | 0 | 0 | 20 |
| src/agent/supervisor.py | 10 | 8 | 1 | 0 | 1 | 20 |
| src/rag_v01/tests/test_retrieve.py | 14 | 1 | 0 | 0 | 4 | 19 |
| tests/test_mcp.py | 7 | 5 | 6 | 0 | 1 | 19 |
| src/rag_v01/tests/test_clean.py | 10 | 5 | 0 | 0 | 2 | 17 |
| tests/test_cli_commands.py | 5 | 4 | 7 | 0 | 1 | 17 |
| src/rag_v01/tests/test_pipeline.py | 6 | 1 | 7 | 0 | 2 | 16 |
| tests/test_executor.py | 4 | 6 | 5 | 0 | 0 | 15 |
| tests/test_memory_inject.py | 6 | 5 | 4 | 0 | 0 | 15 |
| src/rag_v01/tests/test_cli.py | 13 | 1 | 0 | 0 | 1 | 15 |
| src/rag_v01/embed.py | 6 | 5 | 2 | 0 | 2 | 15 |
| src/rag_v01/parsers/common.py | 5 | 2 | 2 | 0 | 6 | 15 |
| src/agent/contracts/task_contract.py | 4 | 4 | 0 | 0 | 4 | 12 |
| tests/test_model_settings.py | 5 | 3 | 2 | 0 | 1 | 11 |
| src/tools/mcp/client.py | 5 | 4 | 0 | 0 | 1 | 10 |
| src/agent/contracts/route.py | 4 | 4 | 0 | 0 | 2 | 10 |
| src/settings/db/checkpointer.py | 5 | 3 | 0 | 0 | 0 | 8 |
| tests/test_sandbox.py | 4 | 0 | 4 | 0 | 0 | 8 |
| src/agent/contracts/plan.py | 4 | 3 | 0 | 1 | 0 | 8 |
| src/rag_v01/chunk/__init__.py | 4 | 3 | 0 | 0 | 2 | 9 |
| src/rag_v01/tests/test_parse.py | 5 | 0 | 2 | 0 | 2 | 9 |
| src/agent/subagents/research.py | 5 | 1 | 0 | 0 | 0 | 6 |
| src/agent/subagents/executor.py | 4 | 0 | 2 | 0 | 0 | 6 |
| src/cli/commands/mcp.py | 3 | 3 | 0 | 0 | 0 | 6 |
| src/rag_v01/__init__.py | 6 | 0 | 0 | 0 | 0 | 6 |
| src/rag_v01/retrieve.py | 3 | 2 | 0 | 0 | 1 | 6 |
| tests/test_memory_node.py | 4 | 1 | 1 | 0 | 0 | 6 |
| src/rag_v01/chunk/children.py | 5 | 1 | 0 | 0 | 0 | 6 |
| src/rag_v01/clean.py | 3 | 2 | 0 | 1 | 0 | 6 |
| src/api/main.py | 1 | 1 | 2 | 0 | 1 | 5 |
| src/api/routers/model_settings.py | 2 | 1 | 1 | 0 | 1 | 5 |
| src/cli/streaming.py | 2 | 1 | 2 | 0 | 0 | 5 |
| tests/test_plan_confirm.py | 3 | 1 | 0 | 0 | 1 | 5 |
| tests/test_rag_facade.py | 2 | 1 | 2 | 0 | 0 | 5 |
| src/rag_v01/parsers/__init__.py | 2 | 2 | 0 | 0 | 1 | 5 |
| src/agent/subagents/retriever.py | 4 | 0 | 0 | 0 | 0 | 4 |
| src/agent/memory_ctx.py | 3 | 0 | 0 | 0 | 0 | 3 |
| src/agent/subagents/react.py | 3 | 1 | 0 | 0 | 0 | 4 |
| src/rag_v01/chunk/parents.py | 2 | 1 | 1 | 0 | 0 | 4 |
| src/rag_v01/pipeline.py | 2 | 1 | 1 | 0 | 0 | 4 |
| src/tools/sandbox/client.py | 3 | 1 | 0 | 0 | 0 | 4 |
| tests/test_plan_progress.py | 2 | 1 | 1 | 0 | 0 | 4 |
| tests/test_session.py | 1 | 2 | 1 | 0 | 0 | 4 |
| src/agent/service.py | 2 | 1 | 0 | 0 | 1 | 4 |
| src/agent/tasks.py | 1 | 0 | 2 | 0 | 1 | 4 |
| src/settings/model_overrides.py | 2 | 0 | 2 | 0 | 0 | 4 |
| src/agent/ask.py | 1 | 1 | 0 | 0 | 1 | 3 |
| src/agent/subagents/stub.py | 1 | 2 | 0 | 0 | 0 | 3 |
| src/cli/commands/memory.py | 1 | 1 | 1 | 0 | 0 | 3 |
| src/settings/embeddings.py | 3 | 0 | 0 | 0 | 0 | 3 |
| tests/test_smoke.py | 1 | 1 | 1 | 0 | 0 | 3 |
| src/settings/config.py | 1 | 1 | 0 | 0 | 1 | 3 |
| tests/test_ask.py | 1 | 1 | 0 | 0 | 1 | 3 |
| tests/test_tasks.py | 1 | 0 | 1 | 0 | 1 | 3 |
| src/agent/memory.py | 1 | 1 | 0 | 0 | 0 | 2 |
| src/cli/commands/knowledge.py | 1 | 1 | 0 | 0 | 0 | 2 |
| src/cli/commands/session.py | 1 | 1 | 0 | 0 | 0 | 2 |
| src/rag_v01/parsers/md.py | 1 | 1 | 0 | 0 | 0 | 2 |
| src/settings/db/store.py | 2 | 0 | 0 | 0 | 0 | 2 |
| src/tools/sandbox/test/tencent_test.py | 1 | 1 | 0 | 0 | 0 | 2 |
| tests/test_interrupt_payload.py | 1 | 0 | 1 | 0 | 0 | 2 |
| src/agent/build.py | 1 | 0 | 0 | 0 | 1 | 2 |
| src/tools/websearch/search.py | 1 | 0 | 1 | 0 | 0 | 2 |
| tests/test_planner.py | 2 | 0 | 0 | 0 | 0 | 2 |
| tests/test_memory.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/agent/contracts/__init__.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/agent/subagents/registry.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/cli/commands/__init__.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/rag_v01/load.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/settings/usage.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/tools/rag/kb_search.py | 1 | 0 | 0 | 0 | 0 | 1 |
| src/tools/skills/loader.py | 1 | 0 | 0 | 0 | 0 | 1 |

干净文件(44 个):多为小 `__init__.py`、contracts、tools 小文件(无多行结构);`src/tools/tool/clock.py` 与其测试零违规。

## 三、重点文件详例(行号为 2026-09-25 时点)

### planner.py(悬挂 11 / 尾逗号 16 / 一参 2 / 过度展开 1 / 正则 1)

悬挂+尾逗号,`_dispatch_ready` L69-74——续行已 +8 但闭括号在 4(应=首行 0),末参数缺逗号:

```python
def _dispatch_ready(
        plan: Plan,
        tasks,
        thread_id: str,
        limit: int = MAX_PARALLEL_SUBAGENTS
    ) -> list[str]:
```

一行多参数,`plan_confirm_node` L137-142(update 字典 2 项挤一行、末项缺逗号、闭括号 `)]}` 未独行;L147-152 同型):

```python
        return Command(
            goto="answer",
            update={"plan": None, "messages": [AIMessage(
                content=f"当前运行方式不支持分批执行计划,已放弃:\n{plan.snapshot()}"
            )]},
        )
```

过度展开,L143-145(`interrupt(` 拆 3 行,单行约 95 字符仅 1 参数,应写回一行)。

### supervisor.py(悬挂 10 / 尾逗号 8 / 一参 1 / 挤参数 1)

def 多参数未逐行,`_advance_plan` L68-70:

```python
def _advance_plan(
    state: AgentState, injected: list[ResultSummary], tasks, config=None
) -> tuple[str | None, dict]:
```

悬挂,print L52-57(续行 12 应 16,闭括号应 8);另 build_contract L38-43、两个 update 字典 L93-102、派发 Command L184-193 同型。

### contracts/plan.py(悬挂 4 / 尾逗号 3 / 正则 1)

字典悬挂+尾逗号,`_MARKS` L25-31(应续行 8、闭括号 0、末项带逗号);L44-47 Field、L72-76 ready_steps、L147-150 to_plan 同型。

### tasks.py(悬挂 1 / 一参 2 / 挤参数 1)

异常兜底 ResultSummary L105-109(一行挤 3 参数 + 挤 2 参数,续行应 20);L48 `submit(5 参)` 单行。

### repl.py(悬挂 12 / 尾逗号 13 / 一参 20 / 挤参数 3)—— 一参重灾区

def 多参数未逐行(每个 `_resume_*` 与 `_auto_summary_worker` 同型),L37-38;run_turn 调用挤参数 L65-66、L97-98、L121-122、L149-150、L247-250;`ReplContext(...)` L184-193;三个 `_resume_*` 调用单行 4-5 参数。

### streaming.py(悬挂 2 / 尾逗号 1 / 一参 2)—— 接近合规

Live 调用 L75-76(续行应 16、末项缺逗号);`_STATUS_BY_NODE` L22-28 悬挂。

### 其余重点

- tests/test_plan_confirm.py L102-108、L66-83(展开嵌套整体 +4);L110 单行 4 参数
- tests/test_plan_progress.py L34-36(complete 挤 5 参数)、L79-98(两个展开字典 +4)
- tests/test_memory_inject.py L81-83(字典 3 项挤一行)、L103-105 等 monkeypatch 2 项/行、L68-76/L239-247 AIMessage 层缺尾逗号

## 四、正则专项(全库仅 5 文件 import re)

| 位置 | 用法 | 判定 |
|---|---|---|
| src/agent/contracts/plan.py L22/L132/L137 | `_STEP_ID_RE` 提取步骤编号数字 | **违规候选**:`s.id[1:].isdigit()` + `int(s.id[1:])` 可等价替代,无注释豁免 |
| src/rag_v01/clean.py L49/L233 | `_PURE_NUMBER` 判断 1-4 位数字(页码残片) | **边界候选**:`strip().isdigit() and len ≤4` 可等价 |
| src/rag_v01/chunk/children.py L30 | 中文句界+闭引号集合匹配 | 不报:多字符集合,str 不能胜任 |
| src/tools/mcp/config.py、src/tools/skills/loader.py | `^[a-z0-9_-]+$` 名称校验 | 不报:整串字符集校验,isalnum 语义不等价 |
| src/rag_v01/clean.py 其余 6 处 | 控制符/私用区/多空格/多换行/数字归一 | 不报:字符类/重复匹配,str 无等价物 |

## 五、边界规则明细

- 单行 >100 字符:**0 处**。
- 过度展开 25 处:pydantic Field 声明(route.py 2、summary.py 7、task_contract.py 4)、单参数 raise/print(parsers/__init__.py 44、config.py 64、service.py 77、planner.py 143)、HTTPException/emit(chat.py 56/113、model_settings.py 71)、mcp/client.py 59、test_chunk.py 233/245、test_api_history.py 154、test_graph.py 345。
- 单行挤参数 52 处:chat.py(5 处 `_sse_run`)、rag_v01/parsers/common.py(6 处)、repl.py(3 处 `_resume_*`)、rag_v01/tests/test_retrieve.py(4 处)、tasks.py L48 等。

## 六、修复策略备注(未执行,仅备忘)

- 量级 1150 处,人工逐处修不现实。若未来决定落地存量:悬挂缩进/尾逗号/逐行参数走 **codemod 脚本**(tokenize 定位跨行块,按"续行=首行+8、闭括号=首行、逐项一行、补尾逗号"重排),以全量 471 tests + ruff 验证;pydantic Field 类单参数声明、测试里的多参数断言辅助需人工确认。
- 渐进策略(现行):新写代码严格遵循(clock.py 已合规);存量**谁改到谁顺手改**,本清单即底单。

## 七、命名裁决(2026-09-25,用户拍板)

- **新代码强制驼峰**:此后新写的变量/函数/参数/方法一律 camelCase(强制例外清单照旧:dunder、pytest 的 `test_` 函数与 fixture、第三方 kwargs、覆写父类签名)。
- 库内既有 snake_case 不回改;裁决前已落地的新标识符(如 `load_skill_reference` 工具)不追溯改名。
- 后果:库内将存在两代命名风格并存,随"谁改到谁顺手改"渐进收敛;新增标识符遇"与既有同类对齐"的诱惑时,以本裁决为准。
