# agent_opt_0.1 · TODO(进度唯一口径)

> 状态标记:✅ 完成 / 🔨 进行中 / ❓ 未开始 / 🔴 有问题(写明阻塞)。
> 分工纪律:业务代码用户按方案文档清单誊写;`tests/` 与文档由智能体负责。
> 基线(2026-09-28):后端 479 passed / 前端 185 passed;P1 删除 test_retriever 后后端总数会下降,以回归绿为准,不追数字。

## 里程碑看板

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 契约变更登记(ROADMAP §7:ResultSummary.report 字段 + conclusion 上限 100→200) | ❓ |
| M1 | 成稿回传,覆盖 research/executor/**retriever** 三子图(01-成稿回传.md) | ❓ |
| M2 | ~~retriever 并入 answer~~ | ❌ **已否决**(2026-09-28 用户裁决:retriever 保持独立子智能体;见 02 文档横幅) |
| M3 | 路由确定性短路(03-路由确定性短路.md) | ❓ |
| M4 | 冒烟验收 + 效果前后对比记录 | ❓ |

## M1 成稿回传(P0)

- [ ] M0:ROADMAP §7 登记 report 字段(先登记后改码)
- [ ] `contracts/summary.py`:ResultSummary 加 `report: str = ""`(01 §二);conclusion max_length 100→200(01 §二)
- [ ] `subagents/react.py`:extract_answer → 三元组,提取 `obj.get("report")`,conclusion/fallback 截 200(01 §三)
- [ ] `subagents/react.py`:validate_report + finalize_node 代码校验与一次重试(01 §五)
- [ ] `subagents/research.py` / `executor.py` / `retriever.py`:三处解包联动,success 分支带 report(01 §三)
- [ ] `prompts/subagents/research.md` / `executor.md`:收尾 JSON 加 report 字段 + 两条说明,结论 ≤200 字(01 §四)
- [ ] `prompts/subagents/retriever.md`:收尾协议切严格 JSON + report,结论 ≤200 字(01 §四;retriever 保持独立子智能体,KB 问答成稿由本协议覆盖)
- [ ] `answer.py`:REPORT_MAX_CHARS=6000 + _render_results 成稿优先分支(01 §六)
- [ ] 智能体:extract_answer 三分支 / validate_report 四分支 / finalize 重试恰一次与降级 / 三子图收尾落 report(含 retriever 旧收尾 fallback 兼容)/ answer 消费与回退 用例(01 §七)
- [ ] 验收:全量 pytest 绿;URL 调研冒烟汇总引用正文细节;KB 问答冒烟直接引成稿;多任务轮观察 3×6000 上下文表现(01 §八)

## M2 retriever 并入 answer(P1)——已否决

2026-09-28 用户裁决:retriever 保持独立子智能体,不并入 answer。本里程碑不执行,02 文档仅存档。

## M3 路由确定性短路(P2)

- [ ] `supervisor.py`:唤醒轮短路 + URL 短路(03 §二)
- [ ] `prompts/supervisor.md`:删规则 12,规则 5 限定唤醒轮,编号顺移(03 §三)
- [ ] 智能体:唤醒轮/用户轮/URL/三种闸门 用例(03 §四)
- [ ] 验收:汇总轮与 URL 轮零路由 LLM 调用(03 §五)

## M4 冒烟与效果记录

- [ ] 三道固定冒烟题的前后对比(答案引用量/延迟/调用次数)记录到本目录(沉淀文件名:`04-效果对比.md`,先入 docs/index.md 再建)
- [ ] P3(模型分档)去留结论补回 00-优化报告 §四
- [ ] 具普遍性的坑经用户确认后沉淀 `docs/troubleshooting/agent_opt_0.1.md`

## 坑表(实施中新增)
