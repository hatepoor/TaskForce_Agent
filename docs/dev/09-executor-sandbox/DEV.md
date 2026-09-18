# 09-Executor-Sandbox 模块开发文档:执行智能体 + 沙箱接入

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`agent/subagents/executor.py`、`tools/sandbox/client.py`
> 一句话:把执行桩换成真子图--ReAct 工具循环(Skills 全文 / MCP 工具 / 远程沙箱 execute_python),"写脚本统计 CSV"这类任务真正跑起来。

## 1. 目标与范围

- **做什么**:executor 子图(独立 state:contract/messages/summary,ReAct 循环:LLM 决策 -> ToolNode -> 循环直至无工具调用);工具装配:内置文件工具 read_file/write_file/list_files(本模块,操作沙箱工作区)+ `load_skill`(07)+ `get_tool_detail`(08)+ MCP 工具(08)+ `execute_python`(本模块);沙箱客户端(HTTP,带 session_id、超时、输出截断、未配置降级);工具索引注入(≤2k);结果摘要(必含 warnings:改过文件/跑过命令)。
- **范围外**:沙箱服务本身(用户自建);联网白名单(backlog);本机文件读写(Agent 不直接写本机,一切经沙箱)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [03-graph-skeleton](../03-graph-skeleton/DEV.md) | TaskContract/ResultSummary/Send 挂载 |
| [07-skills](../07-skills/DEV.md) | `SkillRegistry.load_skill` |
| [08-mcp](../08-mcp/DEV.md) | `MCPToolProvider`(索引/详情/langchain 工具) |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `tools/sandbox/client.py` | `execute_python(code, session_id, timeout)` -> `{stdout, stderr, exit_code, files}`;未配置 SANDBOX_URL 返回可读错误(不抛异常崩图) |
| `agent/subagents/executor.py` | ReAct 编译子图(复用 R 的 build_react_subgraph 骨架,ADR-0010;共享键直挂,ADR-0009);系统提示词按 PROMPT-DESIGN §2.3"执行专员" |
| `agent/build.py`(微调) | executor 节点直挂真子图 |
| `tools/tool/files.py` | [09] 内置文件工具:read_file / write_file / list_files(操作沙箱工作区) |
| `prompts/subagents/executor.md` | [09] ReAct 决策 / 摘要两段 |
| `tests/test_executor.py` | fake model + fake 工具的循环单测;沙箱冒烟(skip 未配置) |

## 4. 分步任务清单

### T1:沙箱客户端
- [ ] 按 .env 的 `SANDBOX_URL/API_KEY`(Bearer)封装 POST 调用;`session_id` 取当前 thread_id;超时(60s);stdout/stderr 截断(10k 字符);**先读用户沙箱的真实接口文档对齐入参出参**(协议以实际为准,ADR-0007);未配置时返回结构化错误信息供 LLM 自行说明。
- 验收:配置后冒烟测试 `execute_python("print(1+1)")` 返回 stdout "2";未配置时返回错误说明、不抛异常。

### T2:executor 子图骨架(ReAct 循环)
- [ ] `ExecutorState(contract/messages/summary)`;agent 节点:LLM + 绑定工具(read_file/write_file/list_files(tools/tool 内置,操作沙箱工作区)+ load_skill/get_tool_detail/execute_python + MCP 工具);条件边:有 tool_calls -> tools 节点 -> 回 agent;无 -> summarize 节点;上限(如 12 次工具调用)防死循环;系统提示词 = `load_prompt("base")` + `load_prompt("subagents/executor")`。
- 验收:fake model 脚本化"先调一次工具再完成"的单测:轨迹含两轮 agent + 一次 tools + summarize。

### T3:结果摘要与 warnings
- [ ] summarize 节点:LLM 按 ResultSummary 输出,**warnings 强制列出**执行侧效应(哪些文件被写、跑了什么命令);工具返回一律截断后进入 messages。
- 验收:fake 单测断言 warnings 字段;沙箱真跑一次"创建 a.txt 并写入 hello"确认 files 返回。

### T4:主图挂载 + 端到端
- [ ] build.py 挂真子图;工具索引(short_desc)进 executor 系统提示词;test_graph 回归全绿。
- 验收:真模型 REPL:"写一段 Python 统计这份 CSV 的总销售额"(先 /kb upload 一份小 CSV 或在契约里给路径)-> dispatch -> executor -> 沙箱执行 -> 回答含真实计算结果。

## 5. 验收标准(整模块)

- [ ] 端到端演示:CSV 统计任务全链路(REPL 派发 -> 沙箱执行 -> 结果回传 -> 汇总);
- [ ] 未配置沙箱:executor 明确告知不可用,图不崩;
- [ ] `uv run pytest -q` 全绿(沙箱冒烟未配置自动 skip);
- [ ] 工具索引 token 受控(<2k)。

## 6. 核心概念速查

- **ReAct 循环**:LLM 输出 tool_calls -> ToolNode 执行 -> 结果回 messages -> 再决策;LangGraph 标准模式。
- **两层工具注入**:索引常驻 + `get_tool_detail` 按需(PROMPT-DESIGN §2.4)。
- **Skill 脚本纪律**:附带脚本一律经 execute_python 走沙箱,绝不本机直跑(ADR-0007)。

## 7. 常见坑与规避

| 坑 | 规避 |
|---|---|
| 沙箱接口对不上 | T1 先联调协议再写子图;错误信息结构化返回给 LLM |
| 工具调用死循环 | 12 次上限 + partial 状态诚实返回 |
| 大 stdout 撑爆上下文 | 10k 截断 + warnings 提示截断发生 |
| MCP 工具与内置工具重名 | 绑定时加前缀 `mcp_<server>_<tool>` |
| 每轮重建 MCP 连接慢 | provider 进程级缓存连接(工具会话复用) |

## 8. 契约接口

**本模块定义**:
```python
# tools/sandbox/client.py
def execute_python(code: str, session_id: str, timeout: int = 60) -> dict: ...
```

**本模块消费**:`TaskContract`/`ResultSummary`(03)、`SkillRegistry`(07)、`MCPToolProvider`(08)。
