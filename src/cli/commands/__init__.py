"""斜杠命令注册表:按域拆分文件,此处统一组装。

新增命令:在对应域文件里写 cmd_x(args, ctx),再在 build_commands 注册一行;
后续模块的命令(/mcp 等)照此办理,不再往 repl.py 堆实现。
"""

from cli.commands.knowledge import cmd_kb
from cli.commands.mcp import cmd_mcp
from cli.commands.memory import cmd_memory
from cli.commands.session import (
    cmd_help,
    cmd_list_session,
    cmd_new,
    cmd_quit,
    cmd_resume,
    cmd_stats,
)
from cli.commands.skills import cmd_skills
from cli.context import ReplContext


def build_commands(ctx: ReplContext) -> dict:
    """返回 命令名 -> handler(args, ctx) 注册表。"""
    return {
        "/new": cmd_new,
        "/resume": cmd_resume,
        "/list_session": cmd_list_session,
        "/stats": cmd_stats,
        "/help": cmd_help,
        "/quit": cmd_quit,
        "/kb": cmd_kb,          # 知识库管理(05)
        "/memory": cmd_memory,  # 长期记忆管理(06)
        "/skills": cmd_skills,  # 技能管理(07)
        "/mcp": cmd_mcp,        # MCP 服务器管理(08)
    }
