# agent_opt_0.1 · TODO(进度唯一口径)

> 状态标记:✅ 完成 / 🔨 进行中 / ❓ 未开始 / 🔴 有问题(写明阻塞)。
> 分工纪律:业务代码用户按方案文档清单誊写;`tests/` 与文档由智能体负责。
> 基线(2026-09-28):后端 479 passed / 前端 185 passed;P1 删除 test_retriever 后后端总数会下降,以回归绿为准,不追数字。

## 里程碑看板

| 里程碑 | 内容 | 状态 |
|---|---|---|
| M0 | 契约变更登记(ROADMAP §7:ResultSummary.report 字段 + conclusion 上限 100→200) | ❓ |
| M1 | 成稿回传,覆盖 research/executor/**retriever** 三子图(01-成稿回传.md) | 🔨 代码与单测完成(2026-10-03,496 passed),效果冒烟待跑 |
| M2 | ~~retriever 并入 answer~~ | ❌ **已否决**(2026-09-28 用户裁决:retriever 保持独立子智能体;见 02 文档横幅) |
| M3 | 路由确定性短路(03-路由确定性短路.md) | ❓ |
| M4 | 冒烟验收 + 效果前后对比记录 | ❓ |
| M5 | 上下文分层(P4,05-上下文分层.md) | 🔨 代码与单测完成(2026-10-03,496 passed),命中率冒烟待跑 |

## M1 成稿回传(P0)

- [x] M0:ROADMAP §7 登记 report 字段(先登记后改码)(2026-10-03 已登记)
- [x] `contracts/summary.py`:ResultSummary 加 `report: str = ""`(01 §二);conclusion max_length 100→200(01 §二)
- [x] `subagents/react.py`:extract_answer → 三元组,提取 `obj.get("report")`,conclusion/fallback 截 200(01 §三)
- [x] `subagents/react.py`:validate_report + finalize_node 代码校验与一次重试(01 §五)
- [x] `subagents/research.py` / `executor.py` / `retriever.py`:三处解包联动,success 分支带 report(01 §三)
- [x] `prompts/subagents/research.md` / `executor.md`:收尾 JSON 加 report 字段 + 两条说明,结论 ≤200 字(01 §四)
- [x] `prompts/subagents/retriever.md`:收尾协议切严格 JSON + report,结论 ≤200 字(01 §四;retriever 保持独立子智能体,KB 问答成稿由本协议覆盖)
- [x] `answer.py`:REPORT_MAX_CHARS=6000 + _render_results 成稿优先分支(01 §六)
- [x] 智能体:extract_answer 三分支 / validate_report 四分支 / finalize 重试恰一次与降级 / 三子图收尾落 report(含 retriever 旧收尾 fallback 兼容)/ answer 消费与回退 用例(01 §七)(tests/test_react_report.py + 三子图测试同步)
- [x] 验收(单测):全量 pytest 绿 + ruff 干净(2026-10-03:496 passed / 9 skipped)
- [ ] 验收(冒烟):URL 调研冒烟汇总引用正文细节;KB 问答冒烟直接引成稿;多任务轮观察 3×6000 上下文表现(01 §八)

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

## M5 上下文分层(P4)

> 实施排 M1/M3(即 P0/P2)之后;方案全文见 05-上下文分层.md,契约已登记 ROADMAP §7(2026-10-03)。

- [x] `agent/state.py`:AgentState 加 `contextDigest: dict`(05 §三)
- [x] `agent/context.py` 新建:assembleView / locateWatermark / _truncateLongMsg / overBudget / maybeCompact(05 §二/§四)(M5a)
- [x] `supervisor.py`:拼装行替换为 assembleView,只消费不触发 compact(05 §2.2)(M5a)
- [x] `answer.py`:拼装行替换为 assembleView(05 §2.2)(M5a)
- [x] `settings/config.py`:context_budget_chars / digest_target_chars / long_msg_limit 三配置项(05 §四)(M5a)
- [x] 智能体:tests/test_context.py 新建(assembleView 拼装/确定性/降级 + maybeCompact 边界/失败降级)(05 §四)(M5a)
- [x] M5a 验收:`uv run pytest tests/test_context.py -q`;digest 为空时全图行为与现状等价(05 §五)
- [x] `prompts/compact.md`:增量摘要提示词 `$digest`/`$transcript`/`$target`(05 §2.4)(M5b)
- [x] `answer.py` 入口:超预算 compact 检查 → 摘要 LLM → 写回 contextDigest;异常降级保留旧 digest(05 §2.4)(M5b)
- [x] `settings/usage.py`:stats_text 补缓存命中率输出(05 §四)(M5b)
- [x] 智能体:maybeCompact 触发边界/定稿不重摘/水位推进/失败降级 用例(落点 tests/test_context.py)(05 §五)(M5b)
- [x] M5b 验收:全量 pytest 绿 + `uv run ruff check .`(2026-10-03:496 passed / 9 skipped)(05 §五)
- [ ] M5c 冒烟:20 轮长会话,命中率除 compact 触发轮外与基线持平;新坑先问再沉淀(05 §五)

## 坑表(实施中新增)
