# 模块 08:MCP 接入 — 问题与解决记录

> 格式规范见 [README.md](README.md)。本文件登记模块 08(MCP 配置/连接/两层描述)开发中的实踩坑位。

## 1. BaseTool.args 是扁平参数映射,不是完整 JSON Schema

- **现象**:T3 两层描述单测断言 `"text" in detail["parameters"].get("properties", {})` 失败——`parameters` 实际是 `{'text': {'title': 'Text', 'type': 'string'}}`,`properties` 取出来是空 `{}`。
- **根因**:langchain `BaseTool.args` 属性返回的是**扁平的参数名 -> schema 映射**,不是带 `properties`/`type` 外壳的完整 JSON Schema 对象;两者长得很像但层级不同。
- **解决**:`get_tool_detail` 直接透传 `tool.args`,消费方按"参数名 -> schema"读取;测试断言改为 `"text" in detail["parameters"]`。
- **关联**:tools/mcp/client.py::get_tool_detail、经验:**BaseTool.args = 扁平参数映射;要完整 JSON Schema 得自己从 args_schema.model_json_schema() 组**。

## 2. langchain-mcp-adapters 全 async API:全同步项目用 asyncio.run 桥接

- **现象**(设计约束而非报错):项目全同步纪律(ADR-0009 前提),而 langchain-mcp-adapters 0.3.2 的 `MultiServerMCPClient.get_tools()` 只有 async 版本,无同步 API。
- **根因**:MCP 生态(asyncmcp)是 async-first,stdio/http transport 的会话管理全部基于 asyncio。
- **解决**:同步侧桥接——`asyncio.run(asyncio.wait_for(client.get_tools(server_name=name), timeout))`,一次性 event loop 跑短生命周期请求,不把 async 渗入图节点;`wait_for` 硬超时同时解决"stdio 子进程挂死卡主流程"的头号坑(08-DEV §6),`timeout` 做成构造参数供测试传短值。
- **关联**:tools/mcp/client.py::list_tools、ADR-0009(全同步)、经验:**同步项目接 async 生态,桥接层收敛在一个模块(此处 client.py),节点代码保持纯同步;桥接必带 wait_for 超时**。
