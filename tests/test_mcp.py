"""模块 08 单测:配置层读写(tmp_path 隔离)+ 连接冒烟/失败降级(本地 echo fixture)。"""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools.mcp.config import (
    HttpServer,
    MCPConfig,
    MCPConfigError,
    StdioServer,
    add_server,
    load_mcp_config,
    remove_server,
    save_mcp_config,
)


def test_add_and_load_roundtrip(tmp_path):
    """add_server 落盘后 load 回读:command/args/env 一致。"""
    p = tmp_path / "mcp_config.json"
    add_server("fs", StdioServer(command="python", args=["-m", "srv"], env={"A": "1"}), p)
    cfg = load_mcp_config(p)
    assert cfg.servers["fs"].command == "python"
    assert cfg.servers["fs"].args == ["-m", "srv"]
    assert cfg.servers["fs"].env == {"A": "1"}


def test_load_missing_file_returns_empty(tmp_path):
    """文件不存在(首次使用)视为空配置,不报错。"""
    assert load_mcp_config(tmp_path / "nope.json").servers == {}


def test_load_bad_json_raises(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(MCPConfigError, match="JSON"):
        load_mcp_config(p)


def test_load_bad_schema_raises(tmp_path):
    """schema 不符(缺 command)抛可读错误,不静默吞。"""
    p = tmp_path / "bad_schema.json"
    p.write_text('{"servers": {"fs": {"args": []}}}', encoding="utf-8")
    with pytest.raises(MCPConfigError, match="schema"):
        load_mcp_config(p)


def test_add_invalid_name_raises(tmp_path):
    with pytest.raises(MCPConfigError, match="不合法"):
        add_server("Bad Name", StdioServer(command="x"), tmp_path / "c.json")


def test_save_and_load_pure_model(tmp_path):
    p = tmp_path / "c.json"
    save_mcp_config(MCPConfig(servers={"a": StdioServer(command="cmd")}), p)
    assert load_mcp_config(p).servers["a"].command == "cmd"


def test_remove_server(tmp_path):
    p = tmp_path / "c.json"
    add_server("fs", StdioServer(command="x"), p)
    assert remove_server("fs", p) is True
    assert remove_server("fs", p) is False  # 再删不存在,返回 False 不抛


# ---------- T2:连接与工具发现(本地 echo stdio 服务器 fixture) ----------

from tools.mcp.client import MCPToolProvider  # noqa: E402

ECHO_SERVER = Path(__file__).parent / "echo_mcp_server.py"


DEAD_SERVER = ["-c", "import time; time.sleep(999)"]


def _provider_with(tmp_path, name, server, timeout=5.0):
    cfg_path = tmp_path / "mcp.json"
    add_server(name, server, cfg_path)
    return MCPToolProvider(load_mcp_config(cfg_path), timeout=timeout)


def test_list_tools_echo_smoke(tmp_path):
    """echo 服务器连接冒烟:发现 echo 工具,索引含 server/short_desc(本地 fixture,非外部依赖)。"""
    provider = _provider_with(
        tmp_path, "echo", StdioServer(command=sys.executable, args=[str(ECHO_SERVER)])
    )
    tools = provider.list_tools()
    assert [t["name"] for t in tools] == ["echo"]
    assert tools[0]["server"] == "echo"
    assert tools[0]["short_desc"]


def test_unreachable_server_degrades(tmp_path):
    """单服务器失败降级(核心验收):永不退出的子进程 -> 超时告警跳过,返回空列表不抛。"""
    provider = _provider_with(
        tmp_path, "dead", StdioServer(command=sys.executable, args=DEAD_SERVER), timeout=2.0,
    )
    assert provider.list_tools() == []


def test_two_servers_partial_failure(tmp_path):
    """一坏一好:坏服务器告警跳过,好服务器工具照常发现。"""
    cfg_path = tmp_path / "mcp.json"
    add_server("dead", StdioServer(command=sys.executable, args=DEAD_SERVER), cfg_path)
    add_server("echo", StdioServer(command=sys.executable, args=[str(ECHO_SERVER)]), cfg_path)
    provider = MCPToolProvider(load_mcp_config(cfg_path), timeout=2.0)
    tools = provider.list_tools()
    assert [t["name"] for t in tools] == ["echo"]
    assert tools[0]["server"] == "echo"


# ---------- 远程支持:streamable-http transport(本地起 http echo 服务器冒烟) ----------

ECHO_HTTP_URL = "http://127.0.0.1:8765/mcp"


@pytest.fixture
def echo_http_server():
    """后台起 streamable-http echo server,等端口就绪;测试结束杀进程。"""
    proc = subprocess.Popen(
        [sys.executable, str(ECHO_SERVER), "--http"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 15
        while time.time() < deadline:
            with socket.socket() as s:
                s.settimeout(0.5)
                try:
                    s.connect(("127.0.0.1", 8765))
                    break
                except OSError:
                    time.sleep(0.3)
        else:
            pytest.fail("echo http server 未在 15s 内就绪")
        yield
    finally:
        proc.kill()


def test_list_tools_http_smoke(tmp_path, echo_http_server):
    """远程(本地 http)MCP 冒烟:url 直连发现 echo 工具。"""
    provider = _provider_with(tmp_path, "echo-http", HttpServer(url=ECHO_HTTP_URL), timeout=8.0)
    tools = provider.list_tools()
    assert [t["name"] for t in tools] == ["echo"]
    assert tools[0]["server"] == "echo-http"


def test_http_unreachable_degrades(tmp_path):
    """远程 http 服务器不可达:超时告警跳过返回空,不抛(降级语义对 http 同样生效)。"""
    provider = _provider_with(
        tmp_path, "dead-http", HttpServer(url="http://127.0.0.1:9/mcp"), timeout=2.0
    )
    assert provider.list_tools() == []


# ---------- T3:两层描述(索引常驻 + 按需详情,共用一次发现) ----------


def test_tool_detail_full_schema(tmp_path):
    """detail:参数 schema 含 text 字段(缓存 BaseTool,不二次连接)。"""
    provider = _provider_with(
        tmp_path, "echo", StdioServer(command=sys.executable, args=[str(ECHO_SERVER)])
    )
    provider.list_tools()
    d = provider.get_tool_detail("echo")
    assert d["name"] == "echo"
    # BaseTool.args 是扁平参数映射 {参数名: schema},非完整 JSON Schema 外壳
    assert "text" in d["parameters"]


def test_tool_detail_unknown_raises(tmp_path):
    provider = _provider_with(
        tmp_path, "echo", StdioServer(command=sys.executable, args=[str(ECHO_SERVER)])
    )
    provider.list_tools()
    with pytest.raises(MCPConfigError, match="不在已发现索引"):
        provider.get_tool_detail("nope")


def test_get_langchain_tools_filters_missing(tmp_path):
    """按名单取可绑定工具对象;缺失的告警跳过(装配 executor 时不崩)。"""
    provider = _provider_with(
        tmp_path, "echo", StdioServer(command=sys.executable, args=[str(ECHO_SERVER)])
    )
    provider.list_tools()
    tools = provider.get_langchain_tools(["echo", "nope"])
    assert len(tools) == 1
    assert tools[0].name == "echo"
