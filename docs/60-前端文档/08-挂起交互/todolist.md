# 挂起交互 开发进度

> 编号: `08`
> 依赖模块: 07 + 01(task3)
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | ask 问询卡与恢复闭环 | ✅ | 模块07 |
| [task2](./task2.md) | memory 确认卡与 unknown 兜底 | ✅ | task1 |

## 进度日志

### 2026-09-16

- ⬜ task1~task2: 未开始

### 2026-09-17

- ✅ task1: `InterruptCard.vue`(按 kind 分派)+ `AskInterruptCard.vue`(问题 + 内联输入 + Enter/输入法 + 自动聚焦 + scrollIntoView);提交 → `resolvePending({status:'submitting', answer})` → 折叠为 `✓ 已补充回答 · "…"`;400 失效路径在 store 的 `failTurn` 收口(toast 原文 + 卡片标失效 + 刷新会话列表)
- ✅ task2: `MemoryConfirmCard.vue`(proposal 引用块 + 「忽略」默认焦点 + 「记入记忆」主按钮,双按钮都走 `/chat/confirm`);unknown 兜底卡(无恢复入口 + 「新开会话」出口)
- store 补强:`endTurn` 把 `submitting` 的挂起卡落定为 `resolved`,挂起态只在"还有 waiting 卡"时保留;`failTurn` 的 400 分支 toast + `loadThreads()`
- 验收证据:vue-tsc 零错误、build 通过、vitest 80/80(08 新增 5 条);headless 探针 21/21 于真实后端 + 真实模型
- 探针覆盖:ask 卡(出现/自动聚焦/空输入禁提交/Composer 禁用)→ 作答折叠 + 同一轮次续写 + 后端受理;B1 历史无 `[用户回答]:` 泄漏;memory 卡(proposal 原文/焦点在忽略/记入后 source=confirmed 且接口可查)→ 测试记忆用后删除;unknown 卡(注入 pinia store 实测);轨迹展开态与回底胶囊(07 遗留断言)一并实测
- 备注:临时探针与诊断脚本用后已删

## 相关事实(写给后续模块,排查沉淀)

- **「记住 X」不会出确认卡**:`agent/memory.py` 中用户明示「记住」是 **T3 显式直写**(`source=explicit`,不 interrupt);只有**自主提案**(用户没说要记、但透露了值得记的事实,如"我平时都用 uv 管理依赖")才 `interrupt({"proposal": ...})` 出确认卡。本模块 task2 验收原文写的「说'记住我喜欢用 uv' → 提案卡出现」**与后端实际语义不符**,探针已按自主提案措辞实测通过。
- 挂起轮**没有 usage 帧**是正常的(服务端就此打住);作答后若信息仍不足,后端会**再问一轮**(合法推进,不是 UI 卡死)。
- ask 的回答在后端合成为 `[用户回答]:xxx` 写入图状态,B1 端点会过滤,前端历史里不应出现该前缀(探针已断言)。
- memory 的 `source` 语义:explicit = 用户明示直写;confirmed = 自主提案 + 用户确认。模块 10(记忆页)的徽标要按这两个值区分。