# plan_0.1 — Plan-and-Execute 方案

> 一句话: 复杂调研先计划后执行(ADR-0012):planner 结构化输出计划 → `plan_confirm` interrupt 经用户确认 → 按依赖分批派发 → supervisor 确定性推进。
> 体系: modules · plan_0.1 · 模块索引
> 状态: 🟢 已完成并落地(里程碑 M1~M4,冒烟通过)

| 分篇 | 一句话 |
|---|---|
| [00-总览](00-总览.md) | 一页纸:目标 / 范围 / 里程碑 |
| [01-契约与状态](01-契约与状态.md) | 全部契约变更(PlanDraft / PlanStep 等) |
| [02-规划与确认节点](02-规划与确认节点.md) | plan_draft / plan_confirm 双节点设计(resume 重跑不漂移) |
| [03-调度推进与展示](03-调度推进与展示.md) | supervisor 确定性推进逻辑与 REPL / Web 展示 |
| [04-测试计划](04-测试计划.md) | 测试约定与 fake 模式 |
| [TODO](TODO.md) | 进度看板(唯一口径) |
