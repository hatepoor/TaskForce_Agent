# 10-Research-Parallel 模块开发文档:调研智能体 + 并行派发

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`agent/subagents/research.py`、`agent/supervisor.py`
> 一句话:压轴模块--调研 ReAct 子图上线(持 web_search 工具的搜-评-再搜循环,复用 R 共享骨架),supervisor 解锁多任务 Send 并行 fan-out,"一次派 2 调研 + 1 检索同时跑"成为现实。

## 1. 目标与范围

- **做什么(ADR-0010 修订:ReAct 化)**:research ReAct 子图(复用 R 的 build_react_subgraph 骨架;共享键 + 私有 messages/iteration);pyproject 加 `ddgs`;`web_search` 工具(返回 top3-5 的 title+snippet,截断内聚在工具内);循环上限 8 轮;supervisor 多任务并行(结构化输出天然支持 tasks 列表,放开单发限制);并行连接纪律落地;agents.md 全文注入 research 系统提示词(裁决,见 PROMPT-DESIGN §2.2)。
- **范围外**:搜索 API 仍可替换(用户预留);并行 interrupt(禁止,ADR-0008)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [03-graph-skeleton](../03-graph-skeleton/DEV.md) | Send 通道、TaskContract/ResultSummary、supervisor |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `agent/subagents/research.py` | ReAct 调研子图(复用 R 骨架;共享键直挂,ADR-0009) |
| `agent/supervisor.py`(改) | 放开多任务派发(提示词明确"无依赖的子任务应并行") |
| `agent/build.py`(微调) | research 节点指向真子图 |
| `prompts/subagents/research.md` | [10] ReAct 角色块(搜-评-再搜纪律与收尾规则) |
| `tests/test_research.py` | fake model + 假搜索的循环单测;并行 fan-out/fan-in 断言 |

## 4. 分步任务清单

### T1:搜索工具封装
- [ ] pyproject 加 `ddgs`;`web_search(query, max_results=5)` 返回 `[{title, url, snippet}]`,snippet 截断(~300 字);超时与失败返回空列表(不崩)。
- 验收:单测(mock ddgs)格式正确;真网络冒烟可选。

### T2:调研子图(ReAct 循环,复用 R 骨架)
- [ ] agent 节点:LLM bind web_search 工具,自主"搜-评-再搜"(评估只见 title+snippet,区分"检索到的"与"推断的");条件边:无 tool_calls 或 iteration≥8 -> 收尾;收尾节点产出 ResultSummary(信息不足以 partial 诚实返回)。
- 验收:fake model 脚本化"两轮后收敛"与"8 轮到顶"两分支单测。

### T3:工具结果截断与上下文闸门(ADR-0010 修订)
- [ ] web_search 工具内截断(每条 snippet ≤300 字,只返回 top3-5);全文仅对选中项抓取(如有抓取工具),用完即弃;messages 膨胀超阈值时提示模型收尾(PROMPT-DESIGN §2.5)。
- 验收:单测断言工具返回条数与长度上限;构造长对话验证收尾触发。

### T4:多任务并行派发
- [ ] supervisor 提示词增加派发规则:"任务可分解且子任务无依赖时,同轮并行派发;同一子智能体可多实例";(结构本身 03 已就绪,这里只放开提示词与验证);确认并行分支各自独立取 psycopg 连接(不共享);Send 扇出数受 `max_parallel_subagents`(初值 3,ADR-0009 §3.4)约束;recursion_limit 按"最坏子图节点数 × 轮数"预算复核(初值 25,不够上调至 40,仅 config 数值)。
- 验收:fake model 断言一次 dispatch 返回多个 Send(且 ≤ 上限);真模型演示见 §5。

### T5:端到端黄金剧本
- [ ] 真模型 REPL:"对比 LangGraph 与 CrewAI 的优劣,并结合我知识库里的笔记"(需 04+05 已完成)。
- 验收:终端轨迹显示一轮派发 2×research + 1×retriever 并行执行;墙钟时间 ≈ 最慢分支(打时间戳验证);answer 一次汇总引用三方来源。

## 5. 验收标准(整模块)

- [ ] 黄金剧本通过(并行可见、一次汇总、来源引用);
- [ ] 5 轮上限与压缩闸门单测全绿;
- [ ] `uv run pytest -q` 全量回归通过(test_graph 基线含并行断言);
- [ ] /stats 显示该轮 token 消耗与估算(对照 PROMPT-DESIGN §4.1 的 4 万 token 量级)。

## 6. 核心概念速查

- **Send 多任务**:supervisor 返回 `[Send(...), Send(...)]`,同超步线程池并行;同节点可多实例(2×research)。
- **fan-in**:全部 Send 完成才回 supervisor(引擎保证)。
- **ReAct 循环状态**:循环即子图私有 messages;截断/上限闸门见 PROMPT-DESIGN §2.5(ADR-0010 修订)。
- 并行=线程≠异步:IO-bound 等待释放 GIL,墙钟≈最慢分支(ADR-0006)。

## 7. 常见坑与规避

| 坑 | 规避 |
|---|---|
| ddgs 被限流/无结果 | 失败返回空列表;evaluate 判定"查不到"诚实返回 partial |
| 并行分支共享 psycopg 连接 | 每路径独立取连接(02 的纪律在此验证) |
| 搜索结果全文塞上下文 | 只喂 title+snippet;全文不抓(PROMPT-DESIGN 闸门) |
| 演示时网络抖动 | 固定演示剧本里准备离线兜底问答;黄金剧本提前彩排 |

## 8. 契约接口

**本模块定义**:无新共享契约。

**本模块消费**:`TaskContract`/`ResultSummary`(03)、Send 通道(03)、agents.md 注入(06 的读取函数复用)。
