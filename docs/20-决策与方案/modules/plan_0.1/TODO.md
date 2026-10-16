# plan_0.1 · TODO

> 分工:[你]=用户誊写(教学模式,业务代码亲手写),[我]=智能体编写(文档与测试)。
> 每完成一项勾选,并同步更新 00-总览.md §4 里程碑看板。

## 进度看板

| 里程碑 | 状态 |
|---|---|
| M1 契约层 | ✅ 完成(22 passed) |
| M2 提示词 | ✅ 完成 |
| M3 双节点 | ✅ 完成 |
| M4 调度推进与展示 | ✅ 完成 |
| M5 测试与回归 | 🔨 全量 467 passed / ruff 干净;剩真实冒烟 |

## M1 契约层 ✅ 完成(2026-09-24:22 passed / ruff 干净)

- [x] [我] ROADMAP §6 归属表 + §7 变更登记(2026-09-24)
- [x] [我] `tests/test_plan_contract.py` M1 验收测试(22 用例)
- [x] [你] `contracts/plan.py`(四模型 + validate_structure + to_plan + Plan 行为方法)
- [x] [你] `contracts/route.py` 加 `"plan"` / `contracts/__init__.py` 导出 / `state.py` 加 `plan`
- [x] [结论] checkpointer 白名单**无需注册**(plan 存 dict 走 msgpack 原生类型);含 plan 的断线恢复冒烟归入 M5

## M2 提示词 ✅ 完成

- [x] `prompts/planner.md` 新增(硬约束 6 条 + 投资调研正反例)
- [x] `prompts/supervisor.md` 更新 plan 分支(五种动作 + 拆分界线 + 计划互斥)

## M3 双节点 ✅ 完成(2026-09-24)

- [x] `contracts/interrupt_payload.py` 加 `plan_payload` + kind 扩展 + `contracts/__init__.py` 导出
- [x] `agent/planner.py`(双节点 + `_dispatch_ready`)/ `build.py` 挂载(9 节点)/ `supervisor.py` plan 分支 / `repl.py` `_resume_plan` / `chat.py` `POST /chat/plan`
- [x] [我] `tests/test_planner.py` + `tests/test_plan_confirm.py`(12 用例)
  - 坑:测试 fake 的 `with_structured_output` 要"消费即重置 schema",否则 answer 轮会把 PlanDraft 当回答返回(LangGraph 报 Unsupported message type)

## M4 调度推进与展示 ✅ 完成(2026-09-24:全量 467 passed)

- [x] `supervisor.py`:contracts import 扩展 + `_advance_plan` + route_node 两处接线(3a 唤醒轮短路 / 3b 用户轮并入)
- [x] REPL 快照展示零改动(快照嵌消息文本)
- [x] [我] `tests/test_plan_progress.py`(4 个整图用例:解锁/收口/级联/插话)
- 坑:3b 的 `update = {**update, **plan_extra}` 漏写会让用户轮推进不落 state(实测踩过);短路/收口轮 injected 必须随 update 写回(drain 消费即清,不写回对账结果就永久丢了)

## 冒烟修正(2026-09-24,真模型首轮暴露)✅ 已修复(全量 469 passed)

- **坑 1(对账断,bug)**:子图 finalize 不填 task_id(react.py 零命中;stub 写死 "stub-1"),`tasks._run` 正常路径拿到 summary 直接入库、没打标 → drain 回来 `ResultSummary.task_id` 为空,`mark_by_task` 永远 miss,计划卡死 running(快照 s1 一直 ▶)。修法:`_run` 在 try 内对 summary `model_copy(update={"task_id": task_id})`;`tests/test_tasks.py` 补 `test_run_backfills_task_id` 专测。教训:progress 测试的 fake `complete()` 用了正确 task_id,绕过了真实回填链路——集成 fake 要模拟最脆的接缝。
- **坑 2(语义缺陷)**:`need_clarification` 原映射为 failed → 级联杀掉补救步(s2"联网补充核实"正是为 s1 无果设计的)。修法:`mark_by_task` 只有 `failed` 记 failed,其余记 done——级联只防"下游对根本没执行的步空跑","缺澄清"带着缺口说明继续走。

## M5 测试与回归

- [ ] [我] tests/test_planner.py + test_plan_confirm.py + test_plan_progress.py
- [ ] [我] tests/test_graph.py + test_tasks.py 扩展
- [ ] [我] `uv run ruff check .` + `uv run pytest -q` 全量回归(基线 429)
- [ ] [你] CLI 冒烟 + HITL 恢复冒烟(04 §3)

## 收尾(代码全落地后)

- [ ] [我] AGENTS.md 第七节架构 big picture 补 plan_draft/plan_confirm(9 节点)
- [ ] [我] 00-总览 §4 看板收口为 ✅

## 遗留项(本期不做)

- API plan 事件帧(on_plan 回调 + SSE plan 帧,前端独立渲染)
- 失败步自动重试 / replan(planner 重新规划未完成部分)
- 计划编辑(resume 协议支持修改步骤后再执行)
- 同步 Send 备胎通道支持 plan
