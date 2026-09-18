# 08-MCP 模块开发文档:MCP 接入

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`tools/mcp/`
> 一句话:做完本模块,能配置本机 MCP 服务器(stdio),工具以"索引常驻 + 按需拉详情"的方式就绪,单服务器挂了不阻塞主流程。(支线:仅依赖 01)

## 1. 目标与范围

- **做什么**:`mcp_config.json` 配置管理;`langchain-mcp-adapters` 加载 stdio 服务器工具;**两层描述机制**(short_desc 常驻索引 ≤2k token,`get_tool_detail(name)` 按需拉全量 schema);连接超时与单服务器失败降级(告警跳过);`/mcp add|list|test|remove` 命令。
- **范围外**:远程 MCP(SSE/HTTP transport)不做(backlog);工具的实际消费在 09 装配进 executor。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [01-minimal-agent](../01-minimal-agent/DEV.md) | REPL 命令注册表、日志设施 |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `tools/mcp/config.py` | mcp_config.json 读写(服务器名 -> command/args/env) |
| `tools/mcp/client.py` | `MCPToolProvider`:`list_tools()`(索引)/ `get_tool_detail(name)` / `get_langchain_tools(names)`(装配给 executor) |
| `cli/repl.py`(改) | `/mcp` 命令组 |
| `tests/test_mcp.py` | 配置读写单测 + 用一个本地 echo 型 stdio 服务器(测试 fixture,如极简 python MCP server)做连接冒烟 |

## 4. 分步任务清单

### T1:配置层
- [ ] `mcp_config.json` schema:`{"servers": {"name": {"command": "...", "args": [...], "env": {...}}}}`;增删改查函数;Windows 注意 command 写绝对路径(如 `uv`/`python` 的完整路径),显式传 env。
- 验收:配置读写单测全绿。

### T2:连接与工具发现
- [ ] pyproject 加 `langchain-mcp-adapters`、`mcp`;`list_tools()`:MultiServerMCPAdapter 逐服务器连接(单服务器超时 10s),失败告警并跳过该服务器;成功则取工具名 + description 截断到 ~30 字作索引。
- 验收:配置一个真实可用服务器(如官方 filesystem server 或自写 echo server),`/mcp test <name>` 列出工具。

### T3:两层描述
- [ ] `get_tool_detail(name)`:返回该工具完整 schema(参数/描述);索引总量超 3k token 时告警(为 09 的白名单降级留信号)。
- 验收:索引/详情两级输出格式正确;`get_langchain_tools(names)` 返回可绑定给 LLM 的工具对象。

### T4:/mcp 命令组 + 降级演示
- [ ] `/mcp list`(配置+连通状态)、`/mcp add`、`/mcp remove`、`/mcp test <name>`。
- 验收:故意停掉某服务器 -> `/mcp list` 标记不可达但命令不崩;主流程(此时还没有 executor)不受影响。

## 5. 验收标准(整模块)

- [ ] `/mcp test` 对真实 stdio 服务器列出工具清单;
- [ ] 单服务器失败:告警 + 降级,进程不挂(核心验收,ADR 见 DESIGN §5);
- [ ] 索引 token 受控(<2k,10 个工具内);
- [ ] `uv run pytest -q` 全绿(连接测试未配置时 skip)。

## 6. 常见坑与规避

| 坑 | 规避 |
|---|---|
| stdio 进程挂死卡住主流程 | 连接/调用都带超时;失败降级为告警(MCP 接入的头号坑) |
| Windows 下 npx/python 路径带空格、PATH 不继承 | 配置写绝对路径;显式传 env |
| 工具描述超长撑爆提示词 | 两层描述 + 截断(本模块核心交付) |
| `python` 与 `py` 混淆 | 配置里命令统一绝对路径 |
| `BaseTool.args` 是扁平参数映射非完整 JSON Schema | detail 层直接透传 `tool.args`,按"参数名->schema"读(详见 troubleshooting/08 #1) |
| adapters 全 async 与全同步架构冲突 | 桥接收敛在 client.py:`asyncio.run` + `wait_for` 超时,节点代码保持纯同步(详见 troubleshooting/08 #2) |

## 7. 契约接口

**本模块定义**:
```python
class MCPToolProvider:
    def list_tools(self) -> list[dict]: ...            # [{server, name, short_desc}]
    def get_tool_detail(self, name: str) -> dict: ...  # 完整 schema
    def get_langchain_tools(self, names: list[str]) -> list: ...
```

**本模块消费**:`get_settings`(00)、REPL 命令注册表(01)。
