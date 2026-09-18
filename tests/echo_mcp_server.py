"""极简 MCP echo 服务器:连接冒烟测试 fixture(模块 08 用)。

用法:
    python tests/echo_mcp_server.py           # stdio transport
    python tests/echo_mcp_server.py --http    # streamable-http transport(127.0.0.1:8765/mcp)
"""

import sys

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("echo")


@mcp.tool()
def echo(text: str) -> str:
    """原样返回输入文本。"""
    return f"echo: {text}"


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.settings.port = 8765
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
