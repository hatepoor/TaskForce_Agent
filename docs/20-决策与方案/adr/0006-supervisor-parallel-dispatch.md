---
status: accepted
---

# Supervisor 支持并行派发(Send API)

v2 初稿曾将 Send 并行分派放入 backlog(supervisor 每轮只派一个子任务),用户否决:若主智能体每次只能派一个子智能体,Supervisor 架构名存实亡,与单 agent 循环调工具无实质差异。因此 v1 即实现并行派发:supervisor 的路由输出为子任务列表,经 `Send(node, state)` 动态 fan-out 到各子智能体,子图各自在独立上下文执行,完成后将结果摘要经 reducer(`operator.add`)累积写回主图状态,LangGraph 的 fan-in 语义保证全部并行任务完成后才回到 supervisor 汇总。子智能体之间仍不互相调用,所有协作经主智能体。

并行执行不依赖 asyncio:LangGraph 同步运行时对同一超步的多个分支使用线程池并行执行,与 ADR-0005 的全同步架构相容;子智能体均为 IO-bound(LLM/Web 搜索/沙箱 HTTP 调用),线程级并行即可获得墙钟时间收益(≈最慢分支)。工程约束:并行节点不得共享单个 psycopg 连接(连接非线程安全,每路径独立取连接)。
