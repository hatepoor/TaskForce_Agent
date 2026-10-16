# Task 2: B2 会话元数据端点

> 模块: `01-后端契约改造`
> 前置 task: task1
> 模块依赖: 无(基于模块 11)
> 状态: ✅ 已完成

## 目标

新增会话元数据能力(最近活跃排序 + checkpoint 数),供前端会话列表展示与排序。

## 前置准备

- [ ] task1 已完成并通过验收
- [ ] 确认不修改 `list_session_ids()`(REPL `/list_session` 依赖其行为)

## 实现步骤

1. **`settings/db/checkpointer.py` 追加 `list_session_meta()`**(完整代码见 API-CONTRACT.md §2.1.5):
   - 文件: `src/settings/db/checkpointer.py`
   - 详情: 纯 SQL `SELECT thread_id, max(checkpoint_id), count(*) ... GROUP BY ... ORDER BY max(checkpoint_id) DESC LIMIT %s`,不反序列化 checkpoint
2. **`api/routers/chat.py` 追加 `GET /chat/threads/meta`**:
   - 文件: `src/api/routers/chat.py`
   - 详情: 调 `list_session_meta(checkpointer)`,包 `{"threads": [...]}` 返回
3. **Claude 补测试**:在 `tests/test_api_history.py` 或独立文件断言 meta 形状与排序

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `src/settings/db/checkpointer.py` | 修改(追加) | `list_session_meta` ~12 行 |
| `src/api/routers/chat.py` | 修改(追加) | meta 端点 ~6 行 |
| `tests/`(对应测试文件) | 新增/修改 | Claude 写 |

## 验收标准

- [ ] `GET /chat/threads/meta` 按最近 checkpoint 降序返回
- [ ] `list_session_ids()` 行为不变(REPL 会话列表回归正常)
- [ ] 全量回归通过

## 备注

`checkpoint_id` 是 UUIDv6 风格单调递增字符串,`max()` 即最近写入;若要真实时间戳需实测 `(checkpoint::json->>'ts')` 可行后再加,首版不做。
