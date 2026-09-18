# 开发问题与解决记录(troubleshooting)

> 沉淀开发中**实际遇到的** bug、坑位与解决方法,避免重复踩坑。与 `adr/` 的区别:ADR 记录**决策**,这里记录**故障与修复**。

## 使用规则

1. **按模块组织**:每个模块一个 `<NN-模块名>.md`(与 `docs/dev/NN-xxx` 对应);跨模块通用问题(环境/工具链)放 `common.md`。
2. **记录时机**:问题解决并验证通过后记录,不记"猜想"。
3. **记录格式**(每条):
   - **现象**:看到了什么(报错原文/错误行为)
   - **根因**:为什么
   - **解决**:怎么修的(含关键代码位置)
   - **关联**:文件 / ADR / ROADMAP §7
4. **与 DEV.md 坑表的关系**:DEV 的"常见坑与规避"是**预防性提示**;踩坑实录在这里。若某坑具普遍性,回填对应 DEV.md 坑表。

## 索引

| 文件 | 覆盖内容 |
|---|---|
| [common.md](common.md) | 线程池 except 内二次异常被静默吞、LangGraph recursion_limit 必须 ≥1、**节点内改 state 不写回主图(严重,异步回收失效根因)**、**带参 psycopg SQL 中字面 % 未转义(无参同型 SQL 不报,迷惑性强)**、**with_structured_output 默认 json_schema 被 DeepSeek 拒绝致路由静默兜底(route 帧永不发出)**、**异步派发的主动汇总只配了 REPL:Web 侧无触发通道 + 节点合成消息不进 SSE(双入口行为分叉,已修复并真机验证)**(跨模块通用 6 条) |
| [03-graph-skeleton.md](03-graph-skeleton.md) | Send fan-out 写法、共享键直挂、reducer 清空、路由乒乓、结构化输出泄漏等;**子结果双截断 + data/sources 未渲染 → 主智能体拿不到子智能体产出(异步派发下必然,已修复并真模型验证)**(模块 03 实踩 13 条) |
| [04-rag.md](04-rag.md) | 内容级判重、维度断言污染、Windows 换行翻译、schema 隔离、智谱 embedding 64 条/请求上限等(模块 04 实踩 5 条) |
| [06-memory-hitl.md](06-memory-hitl.md) | HNSW 2000 维上限(智谱 2048 维改 flat)、PostgresStore embed 批量契约、interrupt 问题双重打印、ask HumanMessage 误启 Live 致盲打、memory 结构化 JSON 流式泄漏等(模块 06 实踩 5 条) |
| [08-mcp.md](08-mcp.md) | BaseTool.args 扁平参数映射(非完整 JSON Schema)、langchain-mcp-adapters 全 async API 的 asyncio.run 桥接与 wait_for 超时(模块 08 实踩 2 条) |
| [09-executor-sandbox.md](09-executor-sandbox.md) | 吞异常 API 的"空=无配置"语义误报、uvx 冷启动握手超 30s 需给足一次性发现超时、**响应判断键与真实形状不符致沙箱误报不可达**(模块 09 实踩 3 条) |
| [11-api.md](11-api.md) | Annotated 联合别名无 .model_validate 需 TypeAdapter、函数内局部 import 绕过 monkeypatch、usage_metadata.total_tokens 必填、bytes 字面量禁非 ASCII、FastAPI File() 触发 B008、**沙箱判断键误用致 /health 误报(09 同型复发)**(模块 11 实踩 6 条) |
