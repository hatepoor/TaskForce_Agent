"""CLI REPL 入口:uv run python -m cli.repl

本文件作用:
    终端交互骨架——装配依赖到 ReplContext 后只剩三件事:斜杠命令分发
    (实现拆在 cli/commands/,按域一个文件)、流式渲染(拆在 cli/streaming.py)、
    主循环(挂起检测:memory 确认与 ask 问询两类 interrupt 的恢复交互)。
    FastAPI(api/)是另一入口,与本文件共用同一套业务层。

使用位置:
    命令行直接运行;依赖 agent/build、agent/service、settings/*。
"""
import sys
import threading
import uuid
import warnings

sys.stdout.reconfigure(encoding="utf-8")
# with_structured_output 在流式模型上的已知序列化告警(功能无影响),REPL 端降噪
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

from rich.console import Console
from rich.panel import Panel

from agent.build import build_graph, make_llm
from agent.service import AUTO_NOTICE, run_turn
from agent.tasks import TaskManager
from cli.commands import build_commands
from cli.context import ReplContext
from cli.streaming import StreamRenderer
from settings.config import get_settings
from settings.db.checkpointer import get_checkpointer
from settings.session import SessionStore
from settings.usage import UsageTracker


def _resume_confirm(ctx: ReplContext, renderer: StreamRenderer,
                    turn_lock: threading.Lock, value: dict) -> bool:
    """memory 确认挂起:显示提案,拦截输入直到 /confirm yes|no,再恢复执行。

    返回 False 表示用户 EOF/中断退出 REPL。与 ask 挂起不同,此处拦截一切
    非确认输入(含其他斜杠命令),保证单一挂起点语义(ADR-0008)。
    """
    console = ctx.console
    console.print(f"[yellow]智能体想记住:[/yellow] {value.get('proposal', '')}")
    console.print("[dim]请用 /confirm yes 或 /confirm no(其他输入将被拦截)[/dim]")
    while True:
        try:
            c = console.input("[bold green]确认?[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye bye[/]")
            return False
        if c.startswith("/confirm"):
            arg = c.partition(" ")[2].strip().lower()
            if arg in ("yes", "y", "no", "n"):
                break
            console.print("[dim]参数只支持 yes|no[/dim]")
            continue
        console.print("[yellow]有记忆确认待处理,请先 /confirm yes|no[/yellow]")
    # renderer/usage 与 watcher 自动汇总轮互斥:全程持锁(new_turn 到 finish 原子)
    with turn_lock:
        renderer.new_turn()
        renderer.start_status("模型正在处理确认结果…")
        try:
            final = run_turn(ctx.graph, ctx.graph_config, resume=arg in ("yes", "y"),
                             on_token=renderer.on_token, on_route=renderer.on_route)
        finally:
            # 与其他分支同款清理:挂起/异常路径都必须收掉 Live 与 Spinner(06 #4)
            renderer.finish()
        if final:
            ctx.usage.record(final)
    return True


def _resume_ask(ctx: ReplContext, renderer: StreamRenderer, commands: dict,
                turn_lock: threading.Lock, value: dict) -> bool:
    """ask 问询挂起:打印问题,自由文本输入即回答;返回 False 表示退出 REPL。"""
    console = ctx.console
    console.print(f"[bold yellow]Agent 提问 ›[/bold yellow] {value.get('question', '')}")
    try:
        answer = console.input("[bold green]你的回答 ›[/bold green] ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]bye bye[/]")
        return False
    if not answer:
        return True
    if answer.startswith("/"):   # 挂起时仍可用斜杠命令(如 /quit)
        name, _, args = answer.partition(" ")
        handler = commands.get(name)
        if handler:
            handler(args, ctx)
        return True
    with turn_lock:
        renderer.new_turn()
        renderer.start_status("模型正在思考中…")
        try:
            final = run_turn(ctx.graph, ctx.graph_config, resume=answer,
                             on_token=renderer.on_token, on_route=renderer.on_route)
        finally:
            # 挂起返回 None 时也必须收掉 Live/Spinner,否则吞终端回显(盲打,06 #4)
            renderer.finish()
        if final:
            ctx.usage.record(final)
    return True


def _auto_summary_worker(ctx: ReplContext, renderer: StreamRenderer,
                         wake: threading.Event, turn_lock: threading.Lock) -> None:
    """后台监视(daemon):任务完成即主动汇总,无需用户询问。

    优先级语义靠锁天然实现:用户轮(普通提问/挂起恢复)进行中时,本线程阻塞
    等锁——答完用户立刻汇总;用户空闲(input 等待不持锁)时立即接管输出。
    唤醒来自 TaskManager 的 on_done 回调(wake.set),零轮询。
    """
    while True:
        wake.wait()
        wake.clear()
        if not (ctx.tasks and ctx.tasks.has_done(ctx.thread_id)):
            continue
        with turn_lock:
            # 清掉当前输入提示行:用户已敲未提交的字符仍在内核输入缓冲,回车照常提交
            ctx.console.file.write("\r\x1b[2K")
            renderer.new_turn()
            renderer.start_status("后台任务已完成,正在汇总…")
            try:
                final = run_turn(ctx.graph, ctx.graph_config, AUTO_NOTICE,
                                 on_token=renderer.on_token, on_route=renderer.on_route)
            finally:
                streamed = renderer.finish()
            if final is not None:
                ctx.usage.record(final)
                if not streamed:
                    renderer.render_final(final.content or "")
            # 重印输入提示符(end 不换行),用户可继续打字
            ctx.console.print("[bold green]用户 ›[/bold green] ", end="")


def main() -> None:
    settings = get_settings()
    # 初始化图(挂 checkpointer,会话状态持久化到 PG);checkpointer 另供 /list_session 查询
    checkpointer = get_checkpointer(settings.database_url)
    turn_lock = threading.Lock()  # 用户轮与自动汇总轮互斥(优先级:用户询问优先)
    wake = threading.Event()      # 任务完成事件(TaskManager.on_done 唤醒 watcher)
    llm = make_llm(settings)
    tasks = TaskManager(llm, on_done=wake.set)  # 异步派发:完成即唤醒主动汇总
    graph = build_graph(llm, checkpointer, tasks=tasks)
    sessions = SessionStore()
    usage = UsageTracker(settings)
    # 每次启动开新会话(2026-09-04 用户决议,替代 02 的"重启自动接上");
    # 旧会话不丢,可用 /resume <id> 恢复,/list_session 列出全部
    previous = sessions.current_thread_id
    thread_id = f"sess-{uuid.uuid4().hex[:8]}"
    sessions.set_current(thread_id)

    console = Console()
    console.print(Panel.fit(
        f"[bold cyan]TaskForce REPL[/] · Agent 工作台\n"
        f"新会话 [green]{thread_id}[/green] | /help 查看命令",
        border_style="cyan",
        subtitle=f"上次会话 {previous}",
    ))

    ctx = ReplContext(console=console, settings=settings, graph=graph,
                      checkpointer=checkpointer, sessions=sessions, usage=usage,
                      tasks=tasks, thread_id=thread_id)
    renderer = StreamRenderer(console)
    commands = build_commands(ctx)
    # 后台监视:任务完成即主动汇总(daemon,REPL 退出即终止)
    threading.Thread(target=_auto_summary_worker,
                     args=(ctx, renderer, wake, turn_lock), daemon=True).start()

    # ---- 主循环 ----
    while True:
        config = ctx.graph_config

        # 挂起态检测——上一轮 interrupt 挂起时,本轮先处理旧挂起,不收新问题
        snapshot = graph.get_state(config)
        pending = getattr(snapshot, "interrupts", None)
        if pending:
            value = pending[0].value if isinstance(pending[0].value, dict) else {}
            ok = (_resume_confirm(ctx, renderer, turn_lock, value) if "proposal" in value
                  else _resume_ask(ctx, renderer, commands, turn_lock, value))
            if not ok:
                return
            continue

        try:
            text = console.input("[bold green]用户 ›[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye bye[/]")
            break
        if not text:
            continue

        if text.startswith("/"):
            name, _, args = text.partition(" ")
            handler = commands.get(name)
            if handler is None:
                console.print(f"[red]未知命令 {name}[/red],[dim]/help 查看[/dim]")
            else:
                handler(args, ctx)
            continue

        if turn_lock.locked():  # watcher 正在自动汇总:排队等待,给用户一句提示
            console.print("[dim](后台汇总进行中,完成后处理你的问题…)[/dim]")
        # renderer/usage 与 watcher 自动汇总轮互斥:全程持锁(new_turn 到 finish 原子)
        with turn_lock:
            renderer.new_turn()
            renderer.start_status("模型正在思考中…")  # 回车即转圈,直到首条路由/首个 token
            try:
                final = run_turn(graph, config, text,
                                 on_token=renderer.on_token, on_route=renderer.on_route,
                                 on_interrupt=renderer.on_interrupt)
            finally:
                # 无论正常/异常,都要把 Spinner 和 Live 干净收掉;返回值即 streamed 标志
                streamed = renderer.finish()
            if final is None:
                # 本轮 interrupt 挂起:问题已由主循环挂起检测打印,下一轮用户回答即 resume
                continue
            usage.record(final)  # 累计本回合 usage(rich 改版时曾遗漏,/stats 一直为 0)
            if not streamed:
                # 未走流式渲染(ask/memory 桩节点、兜底消息):整段 Markdown 渲染一次
                renderer.render_final(final.content or "")


if __name__ == "__main__":
    main()
