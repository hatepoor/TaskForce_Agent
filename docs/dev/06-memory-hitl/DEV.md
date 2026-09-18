# 06-Memory-Hitl 模块开发文档:长期记忆 + 统一 HITL

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`settings/db/store.py`、`agent/{memory.py,ask.py}`、`cli/`
> 一句话:做完本模块,Agent 跨会话记得你,并且会在不确定时主动问你、写记忆前请求批准。**全项目风险最高模块,严格按三步内部分解推进。**

> **⚠️ 2026-09-04 架构变更(ADR-0011)**:T1/T2 已按"注入式"(每轮检索 top-5 塞 system)实现的部分是**过渡态**。本模块后续 T3-T6 与 ARCH-REVIEW §5 的 Step 3 合并落地时,记忆读/写改为 **memory-as-tool**(`memory_search` / `store_memory` 两个 @tool,结果以 ToolMessage 进消息流,不再注入 system)。本文件 T1-T6 的任务标题保留(功能点不变),机制描述以 ADR-0011 与 [ARCH-REVIEW.md](../../ARCH-REVIEW.md) 为准。

## 1. 目标与范围

- **做什么**:长期记忆 Store 工厂(langgraph-store-postgres + pgvector);原子事实条目(一句话 + 来源 explicit/confirmed + 时间);每条用户消息向量检索 top-5 注入主智能体系统提示词(无命中不注入);memory 节点(显式写入直写 / 确认写入 interrupt + `/confirm yes|no`);ask 节点(interrupt 问询,自由文本即回答);agents.md 启动注入;`/memory list|delete` 命令;单一挂起点原则落地。
- **范围外**:子智能体不注入记忆、不 interrupt(架构已定,ADR-0008);敏感信息打码(backlog)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [02-persistence-cli](../02-persistence-cli/DEV.md) | checkpointer、REPL 命令注册表 |
| [03-graph-skeleton](../03-graph-skeleton/DEV.md) | 主图骨架、Route(memory/ask 路由)、load_prompt |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `settings/db/store.py` | `get_store(database_url)`(PostgresStore + pgvector,setup 幂等) |
| `agent/memory.py` | memory 节点:显式直写 / interrupt 确认写 |
| `agent/ask.py` | ask 节点:interrupt 问询,resume 后答案进 messages |
| `agent/build.py`(改) | 注入记忆检索(每消息 top-5)、agents.md 段、两节点实装 |
| `cli/repl.py`(改) | `/confirm yes|no`、`/memory list|delete`、挂起态拦截 |
| `prompts/memory.md` | 记忆提案压缩指令(显式/确认写入共用) |
| `tests/test_memory.py` | store 插查删 roundtrip + interrupt 往返(fake model) |

> ask 节点无独立提示词:问询内容直接来自 Route.question(supervisor 结构化输出的 question 字段,路由说明已含"何时该 ask"的引导)。

## 4. 分步任务清单(按风险递增排序,每步可跑)

### T1:Store 工厂与记忆条目
- [ ] `get_store()`:PostgresStore(连接池、setup 幂等);条目 value 为 `{"content": 一句话, "source": "explicit|confirmed", "created_at": iso}`;namespace 按 `("memory", user_id)`。
- 验收:插查删 roundtrip 单测(put/search/delete)全绿。

### T2:检索注入 + agents.md(无 interrupt,先跑通读路径)
- [ ] 每条用户消息:embed 后 `store.search(namespace, query, top_k=5)`,命中条目渲染成列表追加到主智能体系统提示词的 agents.md 段之后(无命中不注入该段);agents.md 固定路径读取(文件不存在给默认占位提示),会话线程启动时注入。
- 验收:写入一条记忆后,新会话提问相关话题,日志可见注入内容且回答体现记忆。

### T3:显式写入(仍无 interrupt)
- [ ] 用户说"记住 X" -> supervisor 路由 memory -> 节点判断显式 -> LLM 按提示词 `load_prompt("memory", ...)` 压缩成一句话原子事实 -> 直写 store -> 回 supervisor(通常 answer 确认"已记住")。
- 验收:演示"记住我偏好中文回复" -> 新会话生效。

### T4:ask 问询(第一个 interrupt,REPL 内测通)
- [ ] supervisor 路由 ask 时节点 `interrupt({"question": ...})`;REPL 检测线程挂起态(经 `graph.get_state(config)` 的 next/interrupts),打印问题,**用户自由文本输入即回答**;REPL 将输入以 `Command(resume=text)` 恢复,ask 节点把答案作为 user message 追加,回 supervisor 继续。挂起态为 confirm 时拦截普通输入并提示先 `/confirm`。
- 验收:真模型演示"帮我查天气"(缺城市)-> 智能体提问城市 -> 输入"北京" -> 继续执行;fake model 单测覆盖挂起/恢复往返。

### T5:确认写入(第二个 interrupt)
- [ ] memory 节点对自主提案:先 `interrupt({"proposal": ...})`,REPL 显示"智能体想记住:……,批准吗?",`/confirm yes` -> `Command(resume=True)` 落库,`/confirm no` -> resume=False 跳过;两者都回 supervisor。
- 验收:诱导一次自主记忆 -> 拒绝后 `/memory list` 无该条;批准后有。

### T6:/memory 命令 + 回归
- [ ] `/memory list`(全量倒序)、`/memory delete <id>`;全量回归 test_graph + test_memory。
- 验收:命令生效;`uv run pytest -q` 全绿;**重启服务后 /confirm 依然可恢复**(checkpointer 持久化挂起点)。

## 5. 验收标准(整模块)

- [ ] 演示剧本:①"记住我偏好 X" 直写 -> 新会话生效;②缺参数任务 -> ask 提问 -> 回答后继续;③自主记忆 -> 确认流程批准/拒绝两分支;
- [ ] 任意时刻至多一个挂起 interrupt(单测断言);
- [ ] `uv run pytest -q` 全绿;ruff 通过。

## 6. 核心概念速查

- **Store vs checkpointer**:Store 跨线程持久(长期记忆),checkpointer 按线程存图状态(短期记忆);两者都挂 compile。
- **interrupt/resume**:`interrupt(payload)` 在节点内挂起并持久化;恢复 = 对同 thread_id 再次 invoke/stream 时传 `Command(resume=值)`,节点从断点拿到值继续。
- **单一挂起点**(ADR-0008):interrupt 只在 ask/memory;子图绝不 interrupt。
- 注入格式与压缩纪律见 `docs/PROMPT-DESIGN.md` §1.1/§2。

## 7. 常见坑与规避

| 坑 | 规避 |
|---|---|
| interrupt + 流式组合出诡异行为 | 全同步架构(已定);T4 先在 REPL 单独测通再叠加;一次只挂一个 |
| resume 后状态错乱 | resume 前后各 `get_state` 断言;fake model 往返测试是基线 |
| 记忆污染(存成整段对话) | 写入前 LLM 压缩为一句话原子事实;source 字段留审计 |
| agents.md 不生效 | 只在新会话线程启动时注入(设计如此),改文件要 /new |
| 检索每消息一次 embedding 调用变慢 | 可接受(单用户);不要为此上缓存(过度设计) |
| interrupt 挂起的 UI 呈现只放一处 | 问题打印统一在 REPL 主循环挂起检测(get_state.interrupts),run_turn 的 on_* 回调不呈现——两处并存必双重打印(详见 troubleshooting/06 #3) |
| 流式回调只认 AIMessageChunk;挂起路径必须清理 rich Live | ask/memory 节点回填的 HumanMessage 也会过 messages 流白名单,若触发 on_token 会误启 Live;且 resume 分支 return None 前不收 Live 会吞掉后续输入回显(盲打),详见 troubleshooting/06 #4 |
| 白名单内节点勿用结构化输出 | streaming=True 下 with_structured_output 的 JSON 会经 messages 流泄漏到终端;memory 节点已改普通 invoke + JSON 解析(兼拿 usage),详见 troubleshooting/06 #5 |
| HNSW 索引 2000 维上限 | 智谱 embedding 实测 2048 维,ann_index_config 必须用 `flat` 而非 `hnsw`(详见 troubleshooting/06 #1) |
| PostgresStore 的 embed 是批量契约 | `index.embed` 直接复用 `embed_texts`(批量签名 `list[str]->list[list[float]]`),勿自造单文本函数(详见 troubleshooting/06 #2) |

## 8. 契约接口

**本模块定义**:
```python
# settings/db/store.py
@lru_cache
def get_store(database_url: str) -> PostgresStore: ...
```

**本模块消费**:`Route`/`load_prompt`(03)、checkpointer(02)、`embed_texts`(04 的智谱 embedding 封装,namespace 检索由 Store 自带向量能力承担)。
