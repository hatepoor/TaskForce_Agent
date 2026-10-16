# 0012 - Plan-and-Execute(任务拆分规划执行)

- 状态:✅ 已接受(2026-09-24)
- 关联:ADR-0006(并行派发)、ADR-0008(HITL 主图挂起)、ADR-0009(多智能体重构)、ADR-0010(ReAct 子图)
- 方案与进度:`docs/20-决策与方案/modules/plan_0.1/`

## 背景

TaskForce 定位为企业级投资调研助手,复杂调研问题(「对比两家公司年报毛利率并给建议」)天然是多步依赖链:检索→计算→汇总。现有 supervisor 的一次性 dispatch(supervisor.py:108-131)只能并行派发**无依赖**任务,无法表达「步 2 需要步 1 的结果」;也没有显式的计划(todolist)供用户确认与跟踪。

## 决策

1. **计划生成用 LLM,计划推进用确定性代码**。planner 节点只在生成时调一次 `with_structured_output(PlanDraft)`;后续推进(对账/解锁/分批/收口)是 route_node 内的纯 Python 短路(`_advance_plan`),不走路由 LLM。理由:调度是确定性状态机,交给 LLM 会引入不可测性与幻觉改计划风险;短路同时省 token。

2. **HITL 拆双节点 `plan_draft → plan_confirm`**。`interrupt()` resume 后整个节点重跑,单节点方案会导致重跑时再调一次 LLM(温度 0.7,计划漂移)。plan_confirm 是纯确定性节点,重跑零副作用;首批派发在用户批准之后发生。挂起点清单由 ADR-0008 的 ask/memory 扩为 **ask/memory/plan_confirm**(全在主图,子图仍零 interrupt)——本文即 0008 的修订记录,不回改 0008 原文。

3. **step 对账零契约变更**。派发时把 `tasks.submit()` 返回的 task_id(与 jobs 顺序严格对应,tasks.py:36-49)回填 `PlanStep.task_id`,回收后与 `ResultSummary.task_id`(summary.py:22,字段已存在)匹配。被否的替代方案:给 ResultSummary 加 `step_id` 字段——多一处契约变更与 checkpoint 兼容面,且 task_id 本就是为对账而生的字段。

4. **plan 存 dict**。`AgentState.plan: dict | None` 存 `model_dump()`,同 last_route 先例(state.py:27 注释:避免 msgpack 自定义类型告警)。plan 仅 plan_draft/plan_confirm/supervisor 推进块单点写,子图不碰,无 reducer、整体覆盖。

5. **复用双通道与自动唤醒,不新造机制**。派发走 TaskManager.submit(方案 A);每批完成后的推进由既有通路驱动——REPL:on_done → Event → watcher 发 AUTO_NOTICE 新轮;API:前端轮询 `/chat/tasks` → `POST /chat/summary`。推进块以「最后一条消息带 PREFIX_SYSTEM_NOTICE 前缀」识别唤醒轮并短路跳过路由 LLM。

6. **同步 Send 备胎通道不支持 plan**。tasks 为 None(单测/无管理器)时 plan_confirm 直接 goto answer 附说明,不降级为同步 Send fan-out。理由:串行推进的每轮回收依赖 drain_done 账本,同步通道没有账本,硬凑会造出第二套语义。

## 被否方案

- **路由 LLM 逐轮推进计划**(每轮让 supervisor 看计划决定下一步):不可测、贵、LLM 可能擅自改计划;仅保留「用户轮先推进再路由」的混合点。
- **单节点 planner + interrupt**:见决策 2,interrupt 重入副作用。
- **计划状态存 TaskManager 侧**(图外账本):checkpointer 断线恢复后计划丢失,违背「会话线程可恢复」的既有承诺;plan 属会话状态,必须进 AgentState。
- **ResultSummary 加 step_id**:见决策 3。

## 后果

- 主图 7 → 9 节点(plan_draft/plan_confirm);契约新增 Plan 系四模型 + Route.next 加 "plan" + AgentState.plan(ROADMAP §7 已登记)。
- `prompts/planner.md` 新增、`supervisor.md` 更新 plan 分支。
- 每条复杂调研问题的 recursion 消耗约 13 轮(上限 40,充足)。
- 本期明确不做(遗留):API plan 事件帧、失败 replan、计划编辑、备胎通道支持。
