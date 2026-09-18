# Task 3: B3 interrupt 信封与恢复端点类型校验

> 模块: `01-后端契约改造`
> 前置 task: task2
> 模块依赖: 无(基于模块 11)
> 状态: ✅ 已完成

## 目标

SSE `interrupt` 帧改为 `{kind, text}` 自描述信封;两个恢复端点校验挂起类型,类型不符返 400,消灭"把 `true` 当答案写进对话"的静默污染路径。

## 前置准备

- [ ] task2 已完成并通过验收
- [ ] **已在 `docs/dev/ROADMAP.md §7` 登记帧形状变更(数组 → 对象信封)**
- [ ] 通读 [API-CONTRACT.md §3.3](../../API-CONTRACT.md) 与 `_interrupt_envelope` / `_require_interrupt` 参考实现

## 实现步骤

1. **`api/routers/chat.py` 新增 `_interrupt_envelope(updates) -> dict`**:
   - 文件: `src/api/routers/chat.py`
   - 详情: `"proposal" in first` → `{"kind": "memory", "text": ...}`;`"question" in first` → ask;否则 unknown 兜底
2. **`_sse_run` 的 `on_interrupt` 回调改用信封**(一行):
   - 文件: `src/api/routers/chat.py`
   - 详情: `emit("interrupt", _interrupt_envelope(updates))`
3. **新增 `_require_interrupt(graph, config, expect)` 并替换两个恢复端点的挂起检查**:
   - 文件: `src/api/routers/chat.py`
   - 详情: 无挂起 → 400 原文案;类型不符 → 400 `挂起类型不匹配:期望 {expect},实际 {actual}`;`/chat/confirm` 期望 memory,`/chat/answer` 期望 ask
4. **Claude 更新/补测试**:SSE interrupt 帧形状断言 + 类型不符 400 + REPl 回归不受影响

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `src/api/routers/chat.py` | 修改 | 信封 + 校验 ~25 行,用户誊写 |
| `tests/`(chat 相关测试) | 修改 | Claude 写 |

## 验收标准

- [ ] 触发 ask 挂起,SSE 帧为 `{"interrupt": {"kind": "ask", "text": "..."}}`
- [ ] 触发 memory 挂起,帧为 `{"interrupt": {"kind": "memory", "text": "..."}}`
- [ ] 往 `/chat/confirm` 传 ask 挂起会话 → 400 且 detail 含"挂起类型不匹配"
- [ ] REPL `/confirm yes|no` 行为回归正常(不经过 `_sse_run`,应零影响)
- [ ] 全量回归通过

## 备注

**这是本模块最重要的 task**:现状判错不报错且污染数据。CLI REPL 走自己的回调不经过 `_sse_run`,理论零影响,但仍需回归验证。
