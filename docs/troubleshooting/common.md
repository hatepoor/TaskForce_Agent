# 通用问题与解决记录(跨模块/工具链)

> 格式规范见 [README.md](README.md)。本文件登记跨模块通用坑位(与具体模块无关,或影响多个模块)。

## 1. ThreadPoolExecutor 的 except 块内二次异常被静默吞掉:任务"丢了"却无任何日志

- **现象**:异步派发改造后,后台线程执行子图,`_run` 的 `try/except` 兜底构造 `ResultSummary(agent="ghost", ...)`,结果测试里 `drain_done()` 永远为空、超时,任务无声消失;进程无任何报错。
- **根因**:`ResultSummary.agent` 是 `Literal["retriever","research","executor"]` 契约,unknown agent 在 **except 块内**构造摘要时再次抛 `ValidationError`。except 块内的异常不会被外层捕获,线程池工作线程把它**静默丢弃**(ThreadPoolExecutor 不打印未捕获异常,只存在 future 里且无人取 result())——结果永不写入任务表,表象是"任务凭空消失"。
- **解决**:except 兜底里再构造模型时同样可能失败,需保证兜底本身不可能抛——unknown agent 归一为契约允许的值(`agent if agent in _BUILDERS else "retriever"`),结论截断到契约 max_length(`[:100]`)。经验:**线程池回调/执行体里的兜底逻辑必须"兜底到不可能失败",且调试时先怀疑"异常被吞"——给工作线程加 `ThreadPoolExecutor(..., thread_name_prefix=...)` 便于按线程名定位,或临时在 except 里 print**。
- **关联**:src/agent/tasks.py::_run、agent/contracts/summary.py。

## 2. LangGraph 的 recursion_limit 必须 ≥1:传 0 是 ValueError 而非 GraphRecursionError

- **现象**:想用 `recursion_limit=0` 快速触发超限兜底测试,`graph.stream` 抛 `ValueError: recursion_limit must be at least 1`,run_turn 的 `except GraphRecursionError` 没接住,测试失败。
- **根因**:LangGraph 在 `_defaults` 里对 config 做前置校验,recursion_limit < 1 直接 ValueError(与执行超限的 GraphRecursionError 是两回事)。
- **解决**:超限兜底测试不用"极限小 limit",改为假图直接 `raise GraphRecursionError`(run_turn 的兜底分支纯粹可测);真实超限场景用 `recursion_limit=1` 以上的正常值配合循环路径。
- **关联**:tests/test_graph.py::test_run_turn_recursion_limit_fallback、agent/service.py::run_turn。

## 3. LangGraph 节点内修改 state 不写回主图:注入"看起来成功"实则只有路由 LLM 看见(严重)

- **现象**:异步派发改造后,后台任务**正常完成**(stderr 日志 `[task] xxx research 完成: success/partial`,结果确已写入任务表),supervisor 每轮也 `drain_done()` 拿到了结果并渲染了"子智能体结果已回收"段(路由 LLM 因此正确选了 answer),但 **answer 汇总时永远说"没有收到子智能体的执行结果"**。用户多轮追问均复现,功能像坏了一样。
- **根因**:`route_node` 里 `state = {**state, "subagent_results": [*state.get(...), *done]}` 只修改了**节点调用的局部 state**——它用于本次渲染给路由 LLM 没问题,但 supervisor 节点返回的 `Command.update` 只带了 `{"last_route": ...}`,**没有把注入的 subagent_results 写回主图 state**。下一个节点(answer)从 checkpointer 恢复的主图 state 里 `subagent_results` 仍是空,自然看不到结果。这是"局部注入"与"主图写回"的传递断层:中间任何环节(渲染、路由)看起来都成功,唯独数据没抵达消费方。
- **解决**:节点内需要跨节点传递的 state 修改,**必须显式放进返回的 `Command.update`**(共享键走 reducer 合并):`route_node` 统一构造 `update`,把本次注入的 `done` 放进 `update["subagent_results"]`,所有分支共用。同步 Send 通道(子图节点直接更新共享键)天然写回,异步注入通道必须手动补这一步。
- **关联**:src/agent/supervisor.py::route_node、agent/tasks.py;经验:**"节点内改 state"≠"写回主图 state"——LangGraph 节点只有返回值是写给引擎的;凡是要给下游节点看的数据,必须经 Command.update 显式返回,别依赖节点内局部修改**。测试盲区:全图测试若用脚本化 fake(只断言 fake 输出、不断言下游节点输入),这类传递断层会静默漏过;应记录每个 invoke 的输入并断言关键数据到达消费帧。

## 4. psycopg 带参 SQL 中字面 % 未转义:同型 SQL"无参正常、带参爆炸"

- **现象**:`GET /chat/threads/meta` 恒返回 500;后端日志 `psycopg.ProgrammingError: only '%s', '%b', '%t' are allowed as placeholders, got '%'`(抛出点 `settings/db/checkpointer.py` 的 `conn.execute`)。
- **根因**:`list_session_meta` 的 SQL 同时含**参数占位符**(`LIMIT %s`)与**字面百分号**(`LIKE 'sess-%'`)。psycopg 只在"带参数"时解析占位符,裸 `%'` 不是合法占位符 → ProgrammingError。同文件 `list_session_ids` 的 `LIKE 'sess-%'` **无参数**、不做解析,一直正常——同型 SQL 两种行为,迷惑性极强。测试盲区:端点测试用假 saver(不执行真 SQL);SQL 形状测试只断言了**含 bug 的文本**(`"LIKE 'sess-%'" in sql`),真执行才能拦住。
- **解决**:带参 SQL 中字面 `%` 写 `%%`(`LIKE 'sess-%%'`,psycopg 处理后即 `%`);同步修 `test_api_history.py` 断言;`test_session.py` 补**真库回归测试** `test_list_session_meta_runs_against_real_db`(照既有"DB 不可用自动 skip"约定,真执行一发)。已全仓排查其他 psycopg SQL(`tools/rag/store.py` 等):无同类问题。
- **关联**:src/settings/db/checkpointer.py::list_session_meta、tests/test_api_history.py、tests/test_session.py;经验:**SQL 形状/文本断言 ≠ 真执行断言,带参查询必须真库回归**。

## 5. langchain-openai 1.x 的 with_structured_output 默认 json_schema:DeepSeek 端点拒绝(400)被静默兜底

- **现象**:SSE 流只有 token/usage 帧,**route 帧永不出现**(前端轨迹条永远为空);表层无报错——`supervisor.route_node` 的 `except Exception: route = None` 把失败吞掉,静默回退 answer。
- **根因**:`langchain-openai 1.6.0` 的 `with_structured_output(Route)` 默认走 `response_format={"type":"json_schema"}`;DeepSeek 端点不支持该类型,返回 400 `This response_format type is unavailable now`(直接 invoke 复现:`OpenAIInvalidRequestError`)。侧面证据:模块 01 的 curl trace 同样没有 route 帧——**自切 DeepSeek 起,dispatch/ask/memory 路由一直没真正上线**。
- **解决**:显式 `with_structured_output(Route, method="function_calling")`(该端点的 tool-calling 通道实测可用);兜底 except 补 stderr 日志(静默正是本次长期不可见的根因);`tests/test_graph.py` 增回归测试锁死 method 必须显式传入;7 处测试假件签名加 `**kwargs` 兼容。
- **关联**:src/agent/supervisor.py::route_node、tests/test_graph.py;经验:**换 LLM 供应商后,`with_structured_output`/工具调用这类协议层能力必须真机冒烟;凡是走 `except: 兜底` 的路径都要留日志,否则线上退化不可见**。

## 6. 异步派发的"主动汇总"只配了 REPL:Web 侧既无触发通道,节点合成消息也不进 SSE(2026-09-18 已修复并真机验证)

- **现象**:用户报"子智能体任务完成后返回给主智能体,主智能体不会主动回答,而是要用户询问"——终端(REPL)里同一后端行为正常,Web 里必须再问一句才出汇总。伴随现象:Web 上派发轮只显示兜底文案"本轮没有产生文本输出(可能已直接执行动作,如写入记忆)",**"已派发 N 个后台任务"这句话从未出现过**。
- **根因**(两类叠加,缺一不完整):
  1. **触发/通道缺失**:`api/routers/chat.py` 建图用默认 `TaskManager(llm)`(`on_done=None`),API 进程里没有 `cli/repl.py::_auto_summary_worker` 的等价物;SSE 又是每请求一条,dispatch 轮 `Command(goto=END)` 即关流。后台结果只能躺在 `TaskManager._results` 里,直到下一次用户轮被 `route_node.drain_done()` 回收——于是"必须用户询问"。**同一个后端在两个入口行为不一致:围绕异步派发的编排(完成→唤醒→汇总)只实现了一份 REPL 专属的**。
  2. **合成消息不进流**:`run_turn` 的 `on_token` 白名单只有 `answer`/`ask` 两节点;dispatch 确认、memory 确认这类经 `Command.update["messages"]` 追加的**节点合成消息不是流式 token**,而 `_sse_run` 只对 `run_turn` 的返回值发 usage 帧、从不发内容帧 → Web 侧这些文本全部丢失(前端"无文本输出"兜底文案就是这么来的)。判据:一轮若**没有任何 answer/ask 流式 token**,其 final 正文必须整段补发。
- **解决**:① TaskManager 记**会话线程归属**并加**非消费 peek** `status(thread_id)`(`has_done` 会看不能拿、`drain_done` 会消费,都不是给轮询用的);② `POST /chat/summary` 以 `AUTO_NOTICE`(触发语上移到 `agent/service.py`)跑一轮,与 REPL watcher 同语义;③ 前端 `useTaskWatch` 3s 轮询 peek,`pending === 0 && done > 0` 且空闲时自动发起汇总(用户轮优先);④ `_sse_run` 零 token 轮补发 final 正文;⑤ 顺带把 `on_done` 从"每任务触发"改成"**全批完成才触发**"——原实现下 3 个任务先回来的那个会先触发一次汇总,汇总只覆盖半批。
- **关联**:src/api/routers/chat.py、agent/tasks.py、agent/service.py、agent/supervisor.py(route_node 接 LangGraph 注入的 config 取 thread_id)、dev/front/src/composables/useTaskWatch.ts;FE 开放项 `dev/front/docs/README.md`「开放项」/ `UI-DESIGN.md` §7.2 同步改"已落地"。经验:**双入口共用业务层时,"入口专属的编排逻辑"是行为分叉的隐藏点**——生命周期事件(任务完成/结果回收/自动汇总)要么沉到业务层,要么两个入口各写一份并在文档里登记语义对齐点;另:**SSE 白名单过滤 + 只转发流式 token,会顺手丢掉一切"节点更新式"的合成消息**,凡新增这类消息都要检查 API 出口。
