# 模块 03:多智能体骨架 — 问题与解决记录

> 时间:2026-09-02 | 全部为实踩复现后修复,含回归测试(tests/test_graph.py)。

## 1. 节点返回裸 `[Send(...)]` 列表 → `InvalidUpdateError: Expected dict`

- **现象**:supervisor 节点直接 `return [Send(...)]`,运行即抛 `InvalidUpdateError: Expected dict, got [Send(...)]`。
- **根因**:LangGraph 把节点返回值当 state update 处理,只接受 dict / `Command`;fan-out 不是节点返回值的合法形态。
- **解决**:fan-out 必须包在 `Command(goto=[Send(...), ...])` 里。ADR-0009 与官方文档均未明示,系 ADR-0009 §5 第 0 步最小实验实测发现。
- **关联**:`agent/supervisor.py`(`dispatch_sends`)、ADR-0009。

## 2. 并行多子图写回共享键 `contract` 冲突 → `InvalidUpdateError: Can receive only one value per step`

- **现象**:一次派 2 个任务(retriever + research)并行,子图写回时崩溃。
- **根因**:共享键直挂下子图结束时会把共享键写回主图;`contract` 无 reducer,同一 step 两个并行值冲突。而主图根本不读 `contract`(它只是子图输入)。
- **解决**:主图 `AgentState` **移除 `contract` 键**,共享键仅留 `subagent_results`(带 reducer);`contract` 由 Send payload 直达子图,不经主图。
- **关联**:`agent/state.py`、ROADMAP §7(2026-09-02 登记)、ADR-0009 第 0 步实验延伸发现。

## 3. `operator.add` 语义 reducer 加空列表无法清空 `subagent_results`

- **现象**:answer 消费后返回 `[]` 想清空,结果无效,结果跨轮累积。
- **根因**:加法 reducer 对空列表是 no-op,不改原值。
- **解决**:哨兵重置——answer 返回 `{"subagent_results": [RESET]}`,`_add_or_reset` 收到哨兵 `__reset__` 整体重置为 `[]`。
- **关联**:`agent/state.py`(`RESET`/`_add_or_reset`)、`agent/answer.py`。

## 4. Send payload 到子图是 dict,不是 pydantic 对象

- **现象**:子图内 `state["contract"].task` 报 `'dict' object has no attribute 'task'`。
- **根因**:Send payload 是 `model_dump()` 的 dict,TypedDict schema 不做类型转换。
- **解决**:子图边界手动校验构造 `SubgraphContract(**state["contract"])`——这就是"payload 经子图 schema 校验"的实际含义。
- **关联**:`agent/subagents/stub.py`、`agent/contracts/subgraph.py`。

## 5. supervisor 第二次路由感知不到回收结果 → 真模型路由乒乓

- **现象**:真模型下 dispatch → 子图 → 回 supervisor,LLM 又派发一轮(而非汇总),循环到 `recursion_limit` 兜底。
- **根因**:`$subagent_results` 已从 supervisor 系统提示词挪到 answer 消息流(ROADMAP §7,前缀缓存考虑),supervisor 只看 messages,完全不知道结果已回收。
- **解决**:`route_node` 在 `subagent_results` 非空时,向**调用消息流末尾**注入"子智能体结果已回收:…"(三键格式,复用 `_render_results`),引导 LLM 汇总。不写 state、不进历史。
- **关联**:`agent/supervisor.py`、`agent/answer.py`、`tests/test_graph.py::test_route_node_injects_subagent_results`。
- **后续(真模型实测)**:消息注入是软引导,LLM 仍可能再派发——表现为"很慢(30s+)甚至像卡死",实为乒乓循环跑到 `recursion_limit=25`(每步一次 LLM 调用,几分钟)。配合 supervisor.md 派发规则第 4 条硬规则("出现'子智能体结果已回收'必须 answer")后收敛。另:崩溃过的旧会话 checkpoint 含脏数据,重测前先 `/new`。

## 6. `stream_mode="messages"` 泄漏 supervisor 的路由 JSON 且合并崩溃

- **现象**:REPL 打印出 `{"next": "answer", ...}` 原始 JSON;两轮路由后 `TypeError: Additional kwargs key parsed already exists ... unsupported type Route`。
- **根因**:`with_structured_output` 的 token 也走 messages 流;两次路由 chunk 的 `additional_kwargs.parsed`(Route 对象)在 chunk 相加时 merge 冲突。
- **解决**:`run_turn` 按 `meta.get("langgraph_node") != "supervisor"` 过滤——supervisor 的 JSON 不打印不攒,answer/ask/memory 正常流。
- **关联**:`agent/service.py`(`run_turn`)。

## 7. `with_structured_output` 解析失败是抛异常,不是返回 None

- **现象**:LLM 输出不合法 JSON 时 supervisor 抛异常,图挂死。
- **解决**:`route_node` 用 try/except 包住 invoke,异常与 None 都回退 `Command(goto="answer")`,图永不因解析错误挂死。
- **关联**:`agent/supervisor.py`。

## 8. `ResultSummary.task` 的 `max_length=100` 与自由生成文本矛盾 → 整轮崩溃

- **现象**:supervisor 生成 >100 字符的任务描述,子图边界抛 `ValidationError` 且穿透 `run_turn`(只捕 `GraphRecursionError`)。
- **根因**:task 是自由文本的**回显**字段,长度不可控,加上限必然偶发崩溃。
- **解决**:删 task 上限(ROADMAP §7 登记);`conclusion` 的 100 上限保留(决策字段),真实子图(05)落地前注意边界截断。
- **关联**:`agent/contracts/summary.py`、ROADMAP §7。

## 9. `last_route` 存 pydantic 对象 → checkpointer msgpack 告警

- **现象**:`Deserializing unregistered type agent.contracts.route.Route from checkpoint. This will be blocked in a future version.` + Pydantic serializer warning。
- **解决**:`last_route` 改存 `route.model_dump()` dict(state 注解改 `dict`,消费方 `_print_route` 本就兼容);`subagent_results` 的 `ResultSummary` 同类告警暂留,属有意决策,05 前统一处理。
- **关联**:`agent/state.py`、`agent/supervisor.py`、`settings/db/checkpointer.py`。
- **后续(正式解决)**:在 `settings/db/checkpointer.py` 为 PostgresSaver 替换序列化器:`saver.serde = JsonPlusSerializer(allowed_msgpack_modules=[("agent.contracts.route", "Route"), ...])`,显式允许三个契约类型,反序列化告警消除(对旧 checkpoint 数据同样生效)。allowlist 格式为 `(模块名, 类名)` 元组列表。

## 10. 空 dispatch(`tasks=[]`)让图静默停在 supervisor

- **现象**:LLM 输出 `{"next":"dispatch","tasks":[]}` 时 `Command(goto=[])` 无路可走,`run_turn` 把用户自己的消息当回复返回,REPL 原样回显问题。
- **解决**:空任务列表退化走 answer(含 `last_route` 更新)。
- **关联**:`agent/supervisor.py`(`route_node`)。

## 11. langgraph 1.x 的 `Send` payload 属性名是 `.arg`

- **现象**:测试断言写 `s.payload` 报 `AttributeError: 'Send' object has no attribute 'payload'`。
- **解决**:用 `s.node` / `s.arg`(`Command` 用 `.goto`)。
- **关联**:`tests/test_graph.py`。

## 12. (环境)Windows GBK 终端打印中文乱码

- **现象**:REPL / python -c 输出中文乱码。
- **解决**:入口处 `sys.stdout.reconfigure(encoding="utf-8")`(`repl.py` 已内置;pyproject 对 cli/api 放开 E402 即为此)。
- **关联**:`cli/repl.py`、`pyproject.toml`。

## 13. 桩的"未执行"结论诱发 supervisor 反复重派(真模型乒乓二次根因)

- **现象**:真模型下 dispatch → 桩返回"(桩)未实际执行" → supervisor 视其为"可重试的失败",反复重派(甚至在任务描述里写"不得返回桩结果"试图逼桩干活),循环 6-7 次才放弃;用户追问时再次进入循环。
- **根因**:① 桩结论"未执行"对 LLM 是可重试失败信号;② 提示词"结果明显不足才可补充派发"给了重派许可;③ 没有任何信息告诉 LLM"重派不会有新信息"。
- **解决**(三管齐下,05 真子图上线后自动失效):① 桩 `ResultSummary.warnings` 打统一标记"桩子图:未真实执行"(`stub.py`);② `route_node` 注入时检测全部结果带桩标记 → 附加"重派不会获得新信息,请 answer 如实转达"(`supervisor.py`,真子图结果无桩标记,分支自动短路);③ supervisor.md 第 4 条明确"桩结果也不许重派,如实告知能力未上线"。另:REPL 端 `warnings.filterwarnings` 过滤 with_structured_output 的已知 Pydantic 序列化告警(功能无影响)。
- **关联**:`agent/subagents/stub.py`、`agent/supervisor.py`、`prompts/supervisor.md`、`cli/repl.py`。05 落地时需回头删除 supervisor.md 中"桩"相关表述。

## 14. 子结果"双截断 + data/sources 未渲染" → 主智能体拿不到子智能体的产出

> 状态:**已修复并验证**(2026-09-18)。修复要点:`agent/answer.py` 新增 `_render_evidence()`,`_render_results(results, with_evidence=True)` **只在 answer 侧**渲染"依据/来源"(supervisor 的回收提示保持精简);`agent/subagents/research.py` 把检索条目收进 `data["results"]`。验证:后端全量 `pytest` 216 passed + `ruff check .` 全绿;全新实例(:8010)真实 dispatch 复现原场景,回答正确列出《04-LangGraph中断与工具与部署.md》《05-LangGraph高级特性.md》并给出"中断机制 / 流式 stream_mode / 检查点快照 / 子图"等真实要点——修复前只能报出两个文档名。

- **现象**:派发 retriever / research 后,汇总回答**每次都**说"结果被截断了,只传回开头……后面就断了"。实例:retriever 已检出《04-LangGraph中断与工具与部署.md》《05-LangGraph高级特性.md》,但回答只能报出两个文档名;天气调研只能报出"中国天气网显示明天(18 日)南阳为……"半句。用户侧感受像是"子智能体一直失败"。
- **根因**(三处叠加,缺一不足以解释"每次必断"):
  1. `prompts/subagents/retriever.md:29` 提示词**明确要求**子智能体"结论(conclusion)不超过 100 字;要点(key_points)不超过 5 条";
  2. `agent/contracts/summary.py:32` 契约 `conclusion` 钉死 `max_length=100`,且 `agent/subagents/react.py:61/76` 的 `extract_answer()` 又做了一次 `[:100]` 兜底截断(模型不吐 JSON 摘要时折叠空白后同样截 100 字);
  3. `agent/answer.py:25 _render_results()` **只渲染 `agent / task / conclusion / key_points / 澄清`**——`ResultSummary.data`(retriever 的 `hits`:文档名 + 正文片段;research 的检索片段)与 `sources`(doc_id / URL)**从未进过提示词**。
  ⇒ answer 节点可见的内容上限约 100 字,模型"如实汇报截断"不是幻觉,是它确实只收到这么多。
- **连带现象**:`key_points` 只有模型**自发**输出 JSON 摘要时才解析得到(`react.py:70-77` 的成功分支),否则恒为空 → 回答里从来见不到分条要点。
- **为何此前未暴露**:异步派发(2026-09-11)之后,子图结果**只能**经 `ResultSummary` 回到主图(`drain_done` → `subagent_results` → `answer`),没有第二条内容通道;同步 Send 时代还能靠消息流兜底,所以 §8 只留了"注意边界截断"的预防性提示,直到真跑通才暴露。
- **解决(已实施,2026-09-18)**:
  - `agent/answer.py` 新增 `_render_evidence(r)`:按已约定形状渲染 `data` —— retriever 的 `hits` 渲染成 `《文件名》#seq:片段`,research 的 `results` 渲染成 `标题(url):摘要`,其它形状退化为标量 `key=value`;`sources` 渲染成一行。**渲染有预算**(`EVIDENCE_ITEMS_MAX=4` / `EVIDENCE_ITEM_CHARS=250` / `EVIDENCE_TOTAL_CHARS=1200` / `SOURCES_MAX=5`),防多任务叠加撑爆 answer 上下文。
  - `_render_results(results, with_evidence=False)` 加开关:answer 节点传 `True`,supervisor 的"子智能体结果已回收"提示保持决策字段(路由不需要正文,也不该为此付 token)。
  - 同批补:`warnings`(执行侧效应/风险提示)也进了渲染行(此前同样没被渲染,剧本 ④ 的"如实说明在远程沙箱执行"依赖它)。
  - `agent/subagents/research.py`:`_collect_sources()` → `_collect_results()`(带 title/url/snippet),`data["results"]` 随摘要回传;`_sources_of()` 从条目里取 URL。
  - 契约 `conclusion` 的 `max_length=100` **未动**(决策字段的定长约束是模块 03 的设计,不需要改;正文走 `data`)。
  - 回归:`tests/test_graph.py` 新增 4 条渲染用例(依据渲染 / 默认保持精简 / 预算边界 / research 形状 + warnings),`tests/test_research.py` 的 `_collect_results` 用例与成功流断言同步更新。
- **关联**:`agent/answer.py`(`_render_results` / `_render_evidence`,supervisor 亦复用 `_render_results`)、`agent/contracts/summary.py`、`agent/subagents/react.py`、`agent/subagents/research.py`、`prompts/subagents/retriever.md`、`prompts/subagents/research.md`;模块 03 / 05 / 10、`docs/troubleshooting/03-graph-skeleton.md` §8(预防性提示在此转成实踩)。
