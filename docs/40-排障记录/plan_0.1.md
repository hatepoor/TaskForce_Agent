# plan_0.1:Plan-and-Execute — 问题与解决记录

> 时间:2026-09-24 | 真模型冒烟首轮暴露,修复含回归测试(tests/test_tasks.py、tests/test_plan_contract.py、tests/test_plan_confirm.py)。
> 方案与进度:`docs/20-决策与方案/modules/plan_0.1/`,ADR-0012。

## 1. 计划推进对账断:子图自造 task_id,后台不打标 → 计划卡死 running

- **现象**:真模型冒烟,s1 完成后进度快照仍是 `▶ s1`(running),后续步不解锁、失败不级联、永不收口;用户追问时 answer 答"计划没有在执行"。
- **根因**:三个子图的 finalize 各自 `uuid.uuid4().hex[:8]` **自造** task_id(`research.py:63`、`executor.py:119`、`retriever.py:66`——单子图直挂 Send 的年代无人消费该字段,坏值长期潜伏);`TaskManager._run` 正常路径拿到 summary 直接入库不打标(仅 except 分支填了)。drain 回来的 `ResultSummary.task_id` 与 submit 分配的 id 对不上,`Plan.mark_by_task` 永远 miss。
- **解决**:`tasks.py _run` 在 try 内对 summary `model_copy(update={"task_id": task_id})`,统一覆盖为 submit 分配的 id;`tests/test_tasks.py::test_run_backfills_task_id` 锁死。
- **关联**:`agent/tasks.py`、`agent/subagents/research.py` 等、`agent/contracts/plan.py`(`mark_by_task`)、plan_0.1 文档 03 §4。
- **教训**:集成测试的 fake(直接拿正确 task_id 喂 `complete()`)会绕过真实回填链路——**fake 要模拟"最脆的接缝",不是理想路径**;契约字段"是否有人消费"决定坏值能潜伏多久。

## 2. `need_clarification` 被映射为 failed → 级联杀掉补救步(语义缺陷)

- **现象**:s1 检索无果(need_clarification)按原映射记 failed,`cascade_skip` 跳过 s2"联网补充核实"——补救路径被计划自己放弃,用户观感即"一步失败全都失败"。
- **根因**:把"缺澄清"与"硬失败"混为一谈。级联的本意是防止下游对**根本没执行**的步空跑;need_clarification 是"执行了但缺输入",conclusion 本身就是缺口说明,下游(联网核实)完全可以接力。
- **解决**:`mark_by_task` 只有 `failed` 记 failed,success/partial/need_clarification 都记 done,digest 带缺口说明;级联语义收窄为"硬失败才级联"。
- **关联**:`agent/contracts/plan.py`(`mark_by_task`)、`tests/test_plan_contract.py`(映射用例)、plan_0.1 文档 01 §1.3。
- **教训**:结果状态 → 计划状态的映射,要按"下游还能不能走"来定,不是按"结果是否完美"。

## 3. 下游步契约拿不到前序产出 → 解锁了也算不出

- **现象**:即使 s3 被解锁,其契约 task 只有静态 detail,"计算差值"步拿不到 s1/s2 查到的数字。
- **根因**:子图只看契约四件套、没有对话历史;"detail 自包含"只保证下游**知道要什么**,不保证**拿到上文**——depends_on 解决了控制流,信息流没管。
- **解决**:`_step_contract` 把 depends_on 步的 `result_digest` 拼进任务文本(`(前序步骤结论:s1 结论:…)`);`tests/test_plan_confirm.py::test_step_contract_carries_prior_digest` 锁死。
- **关联**:`agent/planner.py`(`_step_contract`)、plan_0.1 文档 02 §3.3。
- **教训**:计划式多智能体里,信息流与控制流要分开设计——depends_on 只管控制流,前序结论要显式随契约传递。

## 4. answer 工具循环漏带 tool_calls 的 assistant 消息 → OpenAI 400(既有 bug 被时钟工具炸出)

- **现象**:REPL 问"现在是几点",answer 调 `get_current_time` 后第二次 invoke 即 400:`Messages with role 'tool' must be a response to a preceding message with 'tool_calls'`,整轮崩溃。
- **根因**:`_answer_with_memory` 回填工具结果时只追加 ToolMessage(`[*messages, *tool_msgs]`),漏了 `res` 本身(带 tool_calls 的 AIMessage)。该 bug 自 ADR-0011 引入记忆工具就存在,但 memory_search 极少被真模型调用;"现在是几点"是第一个必调工具的请求,首次走进循环即炸——**新工具不是引入者,是暴露者**。
- **解决**:`messages = [*messages, res, *tool_msgs]`(answer.py:119);`tests/test_memory_inject.py::test_answer_tool_loop_appends_assistant_before_toolmessage` 断言每个 ToolMessage 前紧邻同 tool_call_id 的 AIMessage。
- **关联**:`agent/answer.py`(`_answer_with_memory`)、`tools/tool/clock.py`、ADR-0011。
- **教训**:fake 模型不校验 OpenAI 协议,消息序列错了也能全绿——**协议类约束(消息结构、tool 消息依附关系)要在测试里显式断言序列结构**,不能只断言"某类消息出现过"。这是本模块第二个"fake 绕过真实约束"的盲区(坑 1 的 task_id 同型)。

## 5. answer 流式 Live 全量重绘:长内容超终端高度 → 滚屏堆叠

- **现象**:长 markdown 回答(几十行)流式渲染时,"标题+结论段"每帧重复、内容逐帧增长堆叠;短回答从未暴露。
- **根因**:rich Live(vertical_overflow="visible")以 12fps 对全量 buf 重绘;rich 源码中 visible **不裁剪内容**,光标回退按上一帧完整高度发光标上移——超过终端高度时被钳制在屏幕顶,滚入 scrollback 的历史行永远擦不掉 → 每帧全量重打一遍。短回答(单屏内)不触发,长回答必然。
- **解决**:弃 Live。演进两步:先打字机直写(无格式)→ 最终**块级增量渲染**(空行为块边界、``` 围栏内不断块;新完成的段落序列以 Markdown 静态打印一次,游标 `_renderedChars` 保证不重绘;未闭合尾块等闭合或 finish)。trade-off:尾块在闭合前不显示。
- **关联**:`src/cli/streaming.py`(`StreamRenderer._flushCompleteBlocks`)。
- **教训**:Live 重绘只适合"高度有界"的内容;长回答要用增量静态打印——每段只打一次,而不是反复擦写。

## 6. answer 工具循环的多轮 token 全进对话流 → 渲染缓冲拼接多份回答

- **现象**:与坑 5 叠加,重复内容更严重;根因独立(即使不超屏也存在)。
- **根因**:`make_llm` 的 `streaming=True` 使 `.invoke()` 也走流式;`_answer_with_memory` 最多 1+4 次 invoke,每轮是独立 run——graph.stream 的 messages 流对**每个 run 的每个 token** 发回调;service 白名单只按节点过滤,answer 所有轮的 token 都进渲染缓冲 → 模型拿到工具结果后重写作答,缓冲里是多份结构复现的回答。
- **解决**:service 白名单处对 `chunk.tool_calls` 非空的中间帧 `continue`(不进 on_token、不进 final);收尾轮无 tool_calls,正常显示。
- **关联**:`src/agent/service.py`(run_turn 白名单)、`src/agent/answer.py`(`_answer_with_memory`)。
- **教训**:节点内多次 LLM 调用 = messages 流里多个 run;流式消费方必须按"带 tool_calls 的中间帧"过滤,否则多轮输出在渲染层拼接。

## 7. rich Markdown 把段落内单换行折叠为空格 → 计划快照挤成一行

- **现象**:计划推进快照(多行 ☑/▶ 列表)显示为一行连排。
- **根因**:快照消息经 render_final → rich Markdown;CommonMark 段落内单 `\n` 是 softbreak → 渲染为空格;快照无空行、无列表标记 → 整体一个段落被压平。
- **解决**:`Plan.snapshot()` 改 Markdown 兼容格式(标题独立段 + 每步 `- ☑ …` 列表项——列表项是硬换行;digest 内换行压平)。
- **关联**:`src/agent/contracts/plan.py`(snapshot)、`src/cli/streaming.py`(render_final)。
- **教训**:多行纯文本快照不能直接走 Markdown 渲染——要么 Markdown 化(列表/空行分段),要么走 Text 渲染。

## 8. research finalize 只认 web_search 产出 → 纯 web_fetch 任务被误判"联网未检索到"

- **现象**:"读取并总结 URL"任务:模型正确调 web_fetch 抓到 8358 字正文(直接调用验证正常),finalize 却判 need_clarification("联网未检索到相关信息"),正文与模型总结全被丢弃。
- **根因**:`build_summary` 的"无结果"判定只看 `_collect_results`/`_sources_of`(仅解析 web_search 的 ToolMessage);web_fetch 的 ToolMessage(非 JSON)被跳过 → sources 空 → 硬判无结果。工具对、**收集器没跟上新工具**。
- **解决**:新增 `_collectFetches`(解析 "[网页正文 | url…" 成功条目,正文节选 2000 字进 `data["fetches"]`);"无结果"判定改为检索与抓取双空;fetch 的 url 并入 sources;`answer._render_evidence` 补 fetches 渲染分支(此前正文节选进 data 但 answer 看不到)。
- **关联**:`src/agent/subagents/research.py`(build_summary)、`src/agent/answer.py`(_render_evidence)、`src/tools/webfetch/fetch.py`。
- **教训**:子图 finalize 的"结果收集器"与工具清单是耦合的——**新增工具必须同步扩展收集器与状态判定**,否则工具成功、任务仍被判失败。

## 9. 子智能体收尾协议是散文,extract_answer 只认 JSON/100 字 fallback → 长总结被削成开头一句

- **现象**:answer 汇总"只回收了开头的结论片段"——research success,但总结只剩 100 字、key_points 为空。
- **根因**:research.md/executor.md 的收尾要求是"一段自然语言总结"(散文),而 `extract_answer` 优先解析严格 JSON,散文走 fallback(折叠空白截 100 字进 conclusion、key_points=[])。conclusion 的 100 字契约上限(03 冻结的"一句话结论")本身没错,错在**提示词与提取器脱节**——提取器早就"优先解析 JSON",提示词却让模型写散文。
- **解决**:两个收尾要求改为严格 JSON({"conclusion" ≤100 字、"key_points" ≤5 条可写长承载完整总结});配套坑 8 的 fetches 渲染。
- **关联**:`src/agent/subagents/react.py`(extract_answer)、`src/prompts/subagents/research.md`、`executor.md`、`src/agent/answer.py`。
- **教训**:提示词要求的输出形态必须与下游解析器对齐——两头各说各话时,fallback 会静默吞掉大部分内容且不报错。
