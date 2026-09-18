"""MCP 服务器管理路由(模块 11 T3):配置 CRUD + 连通性测试。

复用 08 的 config(load/add/remove)与 client(list_tools 探测);
test 端点对单服务器隔离探测(连接失败降级为 ok=False,不抛)。
"""
from fastapi import APIRouter, HTTPException
from pydantic import TypeAdapter

from tools.mcp.client import MCPToolProvider
from tools.mcp.config import (
    MCPConfig,
    MCPServerConfig,
    add_server,
    load_mcp_config,
    remove_server,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])

# Annotated 联合别名无 .model_validate,须用 TypeAdapter 解析 discriminator
_CONFIG_ADAPTER = TypeAdapter(MCPServerConfig)


@router.get("/servers")
def list_servers():
    cfg = load_mcp_config()
    return {"servers": {name: s.model_dump(exclude_none=True) for name, s in cfg.servers.items()}}


@router.post("/servers")
def create_server(name: str, config: dict):
    """新增服务器:name 为唯一键,config 为 StdioServer/HttpServer 配置(discriminator 解析)。"""
    try:
        server = _CONFIG_ADAPTER.validate_python(config)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"配置无效:{e}") from e
    add_server(name, server)
    return {"ok": True, "name": name}


@router.delete("/servers/{name}")
def delete_server(name: str):
    removed = remove_server(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"服务器 {name} 不存在")
    return {"ok": True, "name": name}


@router.post("/servers/{name}/test")
def test_server(name: str):
    """单服务器连通性探测:能发现工具即通;失败返回 ok=False(复用降级契约)。"""
    cfg = load_mcp_config()
    server = cfg.servers.get(name)
    if server is None:
        raise HTTPException(status_code=404, detail=f"服务器 {name} 不存在")
    single = MCPConfig(servers={name: server})
    found = MCPToolProvider(config=single, timeout=10).list_tools()
    return {"ok": bool(found), "tools": found, "name": name}
