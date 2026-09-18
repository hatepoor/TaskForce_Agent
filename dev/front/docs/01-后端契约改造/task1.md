# Task 1: B1 历史消息回填端点

> 模块: `01-后端契约改造`
> 前置 task: 无
> 模块依赖: 无(基于模块 11)
> 状态: ✅ 已完成

## 目标

新增 `GET /chat/threads/{thread_id}/messages` 只读端点,使前端切换/刷新会话后能回填历史消息与挂起态。

## 前置准备

- [ ] 模块 11 的 chat router 可跑(`uv run uvicorn api.main:app`)
- [ ] 已在 `docs/dev/ROADMAP.md §7` 登记新端点
- [ ] 通读 [API-CONTRACT.md §2.1.6](../../API-CONTRACT.md) 的响应契约

## 实现步骤

1. **`api/routers/chat.py` 追加端点**(完整代码见 API-CONTRACT.md §四 B1):
   - 文件: `src/api/routers/chat.py`
   - 详情: `graph.get_state(config)` 读 `values["messages"]`;HumanMessage 过滤 `[用户回答]:` 与 `子智能体结果已回收` 前缀;AIMessage 跳过空 content;`state.interrupts` 格式化为与 SSE 信封同形的 `pending_interrupt`
2. **Claude 编写测试** `tests/test_api_history.py`:
   - 文件: `tests/test_api_history.py`
   - 详情: fake model 造两轮对话 + 一次 ask 挂起,断言消息序列、内部消息过滤、`pending_interrupt` 形状;无挂起时为 `null`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `src/api/routers/chat.py` | 修改(追加) | 新端点 ~30 行,用户誊写 |
| `tests/test_api_history.py` | 新增 | Claude 写 |

## 验收标准

- [x] `uv run pytest tests/test_api_history.py -q` 通过
- [ ] curl 实测:`GET /chat/threads/{id}/messages` 返回过滤后的两轮消息(用户可选,暂缓)
- [ ] 有挂起的会话返回非 null `pending_interrupt`,形状 `{kind, text}`
- [ ] `uv run pytest -q` 全量回归无破坏(用户暂缓,task3 完成后一并跑)

## 备注

内部消息过滤规则与 `agent/memory.py` 的 `_last_user_text()` 同源,勿引入第二套规则。
