# Task 4: B4+B5 SSE 真流式、error 帧与锁收尾

> 模块: `01-后端契约改造`
> 前置 task: task3
> 模块依赖: 无(基于模块 11)
> 状态: ✅ 已完成

## 目标

SSE 改为边跑边推(worker 线程 + Queue,不违反全同步红线);异常发 `error` 帧;`GraphRecursionError` 打标记;补齐三处锁与竞态。**应在模块 07(对话流)开工前完成。**

## 前置准备

- [ ] task3 已完成并通过验收
- [ ] 通读 [API-CONTRACT.md §3.3 error / §四 B4](../../API-CONTRACT.md) 的 worker 参考实现
- [ ] `agent/service.py` 的 `GraphRecursionError` 分支已定位

## 实现步骤

1. **重写 `_sse_run.gen()`**(完整代码见 API-CONTRACT.md §四 B4):
   - 文件: `src/api/routers/chat.py`
   - 详情: `emit` 改投 `queue.Queue`;`worker` 线程跑 `run_turn`(daemon=True);异常 `except Exception` 发 error 帧后置 DONE;`gen()` 主循环 `q.get()` 逐条 yield
2. **`agent/service.py` 打 recursion 标记**:
   - 文件: `src/agent/service.py`
   - 详情: `GraphRecursionError` 分支返回的 AIMessage 加 `additional_kwargs={"taskforce_error": "recursion_limit"}`;模块 01 文档记一笔返回值语义扩展
3. **error 帧发送逻辑**:
   - 文件: `src/api/routers/chat.py`
   - 详情: worker 内判断 `final.additional_kwargs.get("taskforce_error")` → `{"error": {"message": ..., "code": ...}}`;否则发 usage 帧(条件加 `err is None`)
4. **B5 锁收尾**:
   - 文件: `src/api/routers/chat.py` / `src/settings/usage.py`
   - 详情: `_get_app()` 加 `threading.Lock`;`UsageTracker.record()` 加锁
5. **Claude 补测试**:worker 异常路径发 error 帧后正常关流;usage 帧在异常轮不出现

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `src/api/routers/chat.py` | 修改 | `_sse_run` 重写 ~45 行 |
| `src/agent/service.py` | 修改 | 一处 return 加标记 |
| `src/settings/usage.py` | 修改 | record 加锁两行 |
| `tests/`(chat 相关测试) | 修改 | Claude 写 |

## 验收标准

- [x] curl -N 实测:token 帧**逐条到达**(首字节延迟 ≪ 整轮耗时,不再攒完一次吐)
- [x] 构造图内异常(如临时 raise)→ 流内出现 error 帧后正常关流
- [x] 触发 recursion limit → error 帧 `code: "recursion_limit"`
- [x] 快速连点两次请求不会 build 两次图(锁生效)
- [x] REPL 行为回归正常;全量回归通过

## 备注

风险点:① 客户端 abort 后 worker 仍跑完(daemon,单用户可接受,docstring 写明);② checkpointer 是 ConnectionPool 线程安全,但需实测子智能体并行分支;③ 这些坑位解决后按流程询问用户是否沉淀 `docs/troubleshooting/`。
