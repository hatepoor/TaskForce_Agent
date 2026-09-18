"""MCP 服务器命令(模块 08):/mcp list | add | test | remove。

配置源是 mcp_config.json(tools/mcp/config.py),命令只是它的便捷入口;
连通状态逐服务器单独测(单服务器失败不影响其他,降级语义与 client 一致)。
"""

from rich.table import Table

from cli.context import ReplContext
from tools.mcp.config import (
    HttpServer,
    MCPConfig,
    StdioServer,
    add_server,
    load_mcp_config,
    remove_server,
)


def _server_desc(s) -> str:
    """单服务器的一行描述(列表/测试展示用)。"""
    if s.transport == "stdio":
        return f"stdio: {s.command} {' '.join(s.args)}"
    return f"http: {s.url}"


def _probe(name: str, s, timeout: float = 5.0) -> list[dict]:
    """单服务器连通探测:发现工具索引(失败返回空,不抛)。"""
    from tools.mcp.client import MCPToolProvider

    return MCPToolProvider(MCPConfig(servers={name: s}), timeout=timeout).list_tools()


def cmd_mcp(args: str, ctx: ReplContext) -> None:
    """MCP 服务器管理。"""
    sub, _, rest = args.strip().partition(" ")
    console = ctx.console
    try:
        if sub == "list":
            _mcp_list(console)
        elif sub == "add":
            _mcp_add(console, rest)
        elif sub == "test":
            _mcp_test(console, rest.strip())
        elif sub == "remove":
            name = rest.strip()
            if remove_server(name):
                console.print(f"[green]已删除[/] {name}")
            else:
                console.print(f"[yellow]{name} 未配置[/yellow]")
        else:
            console.print(
                "用法:[bold]/mcp list[/] | [bold]/mcp add[/] <name> stdio <command> [args...]"
                " | [bold]/mcp add[/] <name> http <url> | [bold]/mcp test[/] <name>"
                " | [bold]/mcp remove[/] <name>"
            )
    except Exception as e:
        console.print("[red]出错[/]", e)


def _mcp_list(console) -> None:
    cfg = load_mcp_config()
    if not cfg.servers:
        console.print("[dim](未配置 MCP 服务器,/mcp add 添加)[/dim]")
        return
    for name, s in cfg.servers.items():
        tools = _probe(name, s)
        desc = _server_desc(s)
        if tools:
            console.print(f"[green]●[/] [bold]{name}[/bold]({desc}) — {len(tools)} 个工具")
            for t in tools:
                console.print(f"    [dim]{t['name']}: {t['short_desc']}[/dim]")
        else:
            console.print(f"[red]●[/] [bold]{name}[/bold]({desc}) — 不可达或无工具")


def _mcp_add(console, rest: str) -> None:
    name, _, rest2 = rest.strip().partition(" ")
    kind, _, rest3 = rest2.strip().partition(" ")
    if kind == "stdio":
        parts = rest3.split()
        if not name or not parts:
            console.print("用法:[bold]/mcp add[/] <name> stdio <command> [args...]"
                          "(路径含空格请直接编辑 mcp_config.json)")
            return
        add_server(name, StdioServer(command=parts[0], args=parts[1:]))
    elif kind == "http":
        if not name or not rest3.strip():
            console.print("用法:[bold]/mcp add[/] <name> http <url>")
            return
        add_server(name, HttpServer(url=rest3.strip()))
    else:
        console.print("用法:[bold]/mcp add[/] <name> stdio <command> [args...]"
                      " | [bold]/mcp add[/] <name> http <url>")
        return
    console.print(f"[green]已添加[/] {name}({kind}),/mcp test {name} 验证连通")


def _mcp_test(console, name: str) -> None:
    cfg = load_mcp_config()
    if name not in cfg.servers:
        console.print(f"[yellow]{name} 未配置[/yellow]")
        return
    tools = _probe(name, cfg.servers[name], timeout=10.0)
    if not tools:
        console.print(f"[red]{name} 不可达或无工具[/red]")
        return
    table = Table(title=f"{name} 工具索引({len(tools)} 个)")
    table.add_column("name", style="bold")
    table.add_column("short_desc")
    for t in tools:
        table.add_row(t["name"], t["short_desc"])
    console.print(table)
