# adr — 架构决策记录

> 一句话: 0001~0012 条架构决策(含被否决项), **勿"修复"有意为之的设计**。
> 体系: 决策与方案 · adr
> 注意: 编号被 src 代码注释引用(如 ADR-0008/0012), **文件不可改名**。

| 编号 | 决策 |
|---|---|
| [0001](0001-langgraph-only-no-deep-agents.md) | 只用 LangGraph+LangChain, 不用 deep agents |
| [0002](0002-memory-write-requires-user-consent.md) | 记忆写入需用户确认 |
| [0003](0003-multi-user-from-v1.md) | v1 即多用户(已被 ADR-0005 取代) |
| [0004](0004-local-deployment-skills-mcp-on-filesystem.md) | Skill/MCP 存本地文件系统 |
| [0005](0005-scope-reduction-for-job-hunting.md) | 范围收缩为单用户实习项目 |
| [0006](0006-supervisor-parallel-dispatch.md) | Supervisor 支持并行派发 |
| [0007](0007-lightweight-execution-sandbox.md) | 接入自建远程 Docker 沙箱 |
| [0008](0008-unified-hitl-at-main-graph.md) | HITL 统一在主图层(单一挂起点) |
| [0009](0009-multiagent-refactor.md) | 多智能体架构修正 |
| [0010](0010-react-subagents.md) | 子智能体统一 ReAct 执行模式 |
| [0011](0011-static-prompt-memory-tools.md) | 固定 system + 记忆工具化 |
| [0012](0012-plan-and-execute.md) | Plan-and-Execute |
