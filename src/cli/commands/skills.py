"""技能命令(模块 07):/skills 列出已注册技能(name/description/目录)。"""

from rich.table import Table

from cli.context import ReplContext


def cmd_skills(args: str, ctx: ReplContext) -> None:
    """技能管理:展示 SkillRegistry 扫描出的元数据(与 supervisor 注入内容同源)。"""
    console = ctx.console
    try:
        from tools.skills.loader import SkillRegistry  # 局部导入:首次 /skills 才扫描

        metas = SkillRegistry().list_metadata()
        if not metas:
            console.print("[dim](当前无已注册技能,将 SKILL.md 放入 skills/<name>/ 目录)[/dim]")
            return
        table = Table(title=f"已注册技能({len(metas)} 个)")
        table.add_column("name", style="bold")
        table.add_column("description")
        table.add_column("目录", style="dim")
        for m in metas:
            table.add_row(m["name"], m["description"], m["dir"])
        console.print(table)
    except Exception as e:
        console.print("[red]出错[/]", e)
