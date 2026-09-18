"""长期记忆命令(模块 06):/memory list(全量倒序)| /memory delete <key>。"""

from rich.table import Table

from cli.context import ReplContext


def cmd_memory(args: str, ctx: ReplContext) -> None:
    """长期记忆管理:列表 / 删除。"""
    sub, _, rest = args.strip().partition(" ")
    console = ctx.console
    try:
        from settings.config import get_settings  # 局部导入:首次 /memory 才连库
        from settings.db.store import get_store

        store = get_store(get_settings().database_url)
        if sub == "list":
            items = store.search(("memory", "default"), query=None, limit=100)
            items = sorted(items, key=lambda it: it.value.get("created_at", ""), reverse=True)
            if not items:
                console.print("[dim](长期记忆为空)[/dim]")
                return
            table = Table(title=f"长期记忆({len(items)} 条)")
            table.add_column("key", style="dim")
            table.add_column("内容")
            table.add_column("来源")
            table.add_column("时间")
            for it in items:
                v = it.value
                table.add_row(it.key, v.get("content", ""), v.get("source", ""),
                              (v.get("created_at") or "")[:16])
            console.print(table)
        elif sub == "delete":
            key = rest.strip()
            store.delete(("memory", "default"), key)
            console.print(f"[green]已删除[/] {key}")
        else:
            console.print("用法:[bold]/memory[/] list | [bold]/memory[/] delete <key>")
    except Exception as e:
        console.print("[red]出错[/]", e)
