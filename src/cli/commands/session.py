"""会话与系统类命令:/new /resume /list_session /stats /help /quit。

签名统一 cmd(args, ctx);ctx.thread_id 是唯一可变状态(/new /resume 修改)。
"""

import uuid

from rich.table import Table

from cli.context import ReplContext


def cmd_new(args: str, ctx: ReplContext) -> None:
    """开新会话:生成新 thread_id 并持久化。"""
    ctx.thread_id = f"sess-{uuid.uuid4().hex[:8]}"
    ctx.sessions.set_current(ctx.thread_id)
    ctx.console.print(f"[green]已切换到新会话 {ctx.thread_id}[/green](旧会话可用 /resume 回去)")


def cmd_resume(args: str, ctx: ReplContext) -> None:
    """切回指定会话:/resume sess-xxxx(缺参则保持当前)。"""
    tid = args.strip() or ctx.thread_id
    ctx.thread_id = tid
    ctx.sessions.set_current(tid)
    ctx.console.print(f"当前会话:[green]{tid}[/green]")


def cmd_stats(args: str, ctx: ReplContext) -> None:
    """打印本进程累计 token 用量与估算费用(rich 表格)。"""
    tracker = ctx.usage
    total = tracker.input_tokens + tracker.output_tokens
    t = Table(show_header=False, box=None)
    t.add_column(style="dim", no_wrap=True)
    t.add_column(justify="right")
    t.add_row("调用次数", f"{tracker.calls} 次")
    t.add_row("输入 token", str(tracker.input_tokens))
    t.add_row("输出 token", str(tracker.output_tokens))
    t.add_row("合计", f"{total} tok")
    ctx.console.print(t)


def cmd_list_session(args: str, ctx: ReplContext) -> None:
    """列出全部会话 id(当前会话打 *),配合 /resume <id> 切换恢复。"""
    from settings.db.checkpointer import list_session_ids  # 局部导入:首次调用才连库

    ids = list_session_ids(ctx.checkpointer)
    if not ids:
        ctx.console.print("[dim](尚无历史会话)[/dim]")
        return
    for tid in ids:
        mark = "  [cyan]*当前[/cyan]" if tid == ctx.thread_id else ""
        ctx.console.print(f"{tid}{mark}")
    ctx.console.print("[dim](/resume <id> 可切换恢复指定会话)[/dim]")


def cmd_help(args: str, ctx: ReplContext) -> None:
    """列出全部命令。"""
    ctx.console.print(
        "命令:[bold]/new[/] 开新会话 | [bold]/resume[/] <id> 切会话"
        " | [bold]/list_session[/] 列出会话 | [bold]/kb[/] 知识库"
        " | [bold]/memory[/] 长期记忆 | [bold]/skills[/] 技能 | [bold]/stats[/] 用量"
        " | [bold]/quit[/] 退出"
    )


def cmd_quit(args: str, ctx: ReplContext) -> None:
    """打印用量并退出。"""
    ctx.console.print(ctx.usage.stats_text())
    ctx.console.print("[dim]bye bye[/]")
    raise SystemExit(0)
