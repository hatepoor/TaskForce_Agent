"""知识库命令:/kb upload <文件路径> | /kb list | /kb delete <doc_id>。"""

from pathlib import Path

from rich.table import Table

from cli.context import ReplContext


def cmd_kb(args: str, ctx: ReplContext) -> None:
    """知识库管理(06 前的 05 遗产):上传/列表/删除。"""
    sub, _, rest = args.strip().partition(" ")
    console = ctx.console
    try:
        from tools.rag.store import RAGStore  # 局部导入:首次 /kb 才连库

        kb = RAGStore()
        if sub == "upload":
            # 用户习惯给路径包引号(防空格):剥掉首尾引号再建 Path,否则后缀名带引号匹配失败
            path = Path(rest.strip().strip("\"'"))
            doc_id, created = kb.upload(path, path.name)
            if created:
                console.print(f"[green]已上传[/] {path.name} → doc_id={doc_id}")
            else:
                console.print(f"[yellow]内容重复[/yellow],已复用已有文档(doc_id={doc_id})")
        elif sub == "list":
            docs = kb.list_docs()
            if not docs:
                console.print("[dim](知识库为空)[/dim]")
                return
            table = Table(title=f"知识库({len(docs)} 个文档)")
            table.add_column("doc_id", style="dim")
            table.add_column("文件名")
            table.add_column("块数", justify="right")
            table.add_column("上传时间")
            for d in docs:
                table.add_row(d["doc_id"], d["filename"], str(d["chunks"]),
                              f"{d['created_at']:%Y-%m-%d %H:%M}")
            console.print(table)
        elif sub == "delete":
            kb.delete(rest.strip())
            console.print(f"[green]已删除[/] {rest.strip()}")
        else:
            console.print("用法:[bold]/kb[/] upload <文件路径> | [bold]/kb[/] list"
                          " | [bold]/kb[/] delete <doc_id>")
    except Exception as e:
        console.print("[red]出错[/]", e)
