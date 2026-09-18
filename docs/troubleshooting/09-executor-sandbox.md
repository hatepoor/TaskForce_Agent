# 模块 09:执行智能体 + 沙箱 — 问题与解决记录

> 格式规范见 [README.md](README.md)。本文件登记模块 09(沙箱客户端 / executor 子图 / MCP 工具可见性)开发中的实踩坑位。

## 1. MCP 工具发现失败返回空列表:消费方把"已配置但连不上"误报成"未配置"

- **现象**:REPL 问"mcp 有哪些"→ 日志 `[mcp] 服务器 askecho-search 不可达,已跳过:TimeoutError`,answer 却答"当前没有配置任何外部工具(MCP)"。
- **根因**:`MCPToolProvider.list_tools()` 的降级契约是**单服务器失败返回空列表、永不抛异常**(08 设计);`mcp_meta()` 起初靠 `try/except` 捕获异常降级,但异常根本不会抛——拿到空列表后经 `render_mcp_meta([])` 渲染成"(未配置外部工具)",把"配置了但连不上"误报成"没有"。这是两个降级层叠出的语义黑洞:内部吞错 + 外部把空当无配置。
- **解决**:`mcp_meta()` 先判 `load_mcp_config().servers` 是否为空(真正未配置),再发现工具;发现结果为空但配置非空 → 返回"(已配置外部工具,但当前连接暂不可用)"。三态语义:未配置 / 已配置连不上 / 正常清单。
- **关联**:tools/mcp/client.py::mcp_meta/list_tools、经验:**吞异常的降级 API,消费方必须显式区分"空因为没数据"与"空因为出错";靠 try/except 兜"永远不抛"的函数是白兜**。

## 2. uvx 冷启动 + stdio 握手可超 30s:工具发现超时参数给足

- **现象**:`mcp_meta()` 用默认 10s 超时,连 askecho-search 报 `TimeoutError`;改 30s 仍偶发;改 60s 稳定。日志里服务器其实已打印 `Starting Web Search API MCP Server`、`Processing ListToolsRequest`——进程起来了,但 client 侧 stdio initialize 握手在超时窗口外。
- **根因**:`uvx --from git+...` 冷启动要先解析/克隆/构建依赖,进程拉起 + MCP 握手合计可能超过 30s;`CONNECT_TIMEOUT=10` 是面向"常驻进程"的假设,对按需冷启动的 uvx 型服务器不成立。
- **解决**:一次性发现场景(如 `mcp_meta()`,进程内 lru_cache 只跑一次)把超时给到 60s;交互式 `/mcp test` 保持 10s(用户可重试)不变。uvx 缓存热后启动回到 1-2s。
- **关联**:tools/mcp/client.py::mcp_meta/MCPToolProvider、经验:**stdout 型 MCP 服务器首次冷启动的握手延迟与常驻服务不是一个量级,一次性发现给足超时,交互探测保持短超时靠重试**。

## 3. 响应判断键与真实响应形状不符:沙箱被误报"不可达",误导主智能体与用户

- **现象**:`sandbox_health()` 实测返回 `{"status": "ok"}`,但 answer 的 `sandbox_meta()` 三态一直输出"(执行沙箱已配置,但当前连接不可达,执行类任务可能失败)";REPL 里主智能体据此回答"执行沙箱当前连接不可达,很可能导致任务失败"——把用户导向错误的排障方向。
- **根因**:`sandbox_meta()` 判断用 `sandbox_health().get("ok")`,但 `/health` 真实响应是 `{"status": "ok"}`,无 `ok` 键 → 恒为 False → 恒判"不可达"。同时单测 `test_sandbox_meta_three_states` 的 mock 用 `{"ok": True}` 构造,与真实响应形状不一致,测试全绿却没覆盖真实路径(测试盲区)。
- **解决**:判断改 `sandbox_health().get("status") != "ok"`;测试 mock 改为真实响应形状 `{"status": "ok"}` / `{"status": "error"}`。经验:**mock 外部响应的形状必须照抄真实契约,别凭字段名想当然——"mock 与真身不一致"会让断言全绿但真实验收失败**。
- **关联**:src/tools/sandbox/client.py::sandbox_meta/sandbox_health、tests/test_sandbox.py。
