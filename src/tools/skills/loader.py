"""
Skill 注册表:扫描 skills/*/SKILL.md,渐进式加载元数据与全文。

本模块只做"扫描、解析与提供数据":list_metadata() 供主智能体提示词的
$skills_meta 插槽(常驻元数据,不塞全文);load_skill() 供执行智能体按需读全文。
Skill 脚本的实际执行在沙箱(09 装配),本模块不运行任何 Skill 代码。

约定(07-DEV §3):每个 skill 一个子目录,内含 SKILL.md;文件以 --- 开头的
yaml frontmatter 声明 name(唯一标识,^[a-z0-9-]+$)/description(一句话)。
"""

import re
import sys
from functools import lru_cache
from pathlib import Path

import yaml

_NAME_RE=re.compile(r'^[a-z0-9-]+$')
DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "skills"

class SkillError(ValueError):
    """skill 注册表可读错误，重名，加载不存在的skills等"""


def _parse_frontmatter(text: str) -> dict:
    """解析 --- 包裹的 yaml frontmatter;缺/坏返回空 dict(调用方告警跳过)。"""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        print(f"[skills] frontmatter yaml 解析失败:{e}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}

class SkillRegistry:
    def __init__(self, root: Path | str | None = None):
        self.root = Path(root) if root else DEFAULT_ROOT

    def list_metadata(self) -> list[dict]:
        """
        扫描并返回 [{name, description, dir}]。

        单个 skill 解析失败只告警跳过(不阻塞启动);name 重复视为数据错误抛 SkillError。
        """
        metas: list[dict] = []
        seen: dict[str, Path] = {}
        for d in sorted(p for p in self.root.iterdir() if p.is_dir()):
            meta = self._parse_skill_dir(d)
            if meta is None:
                continue
            if meta["name"] in seen:
                raise SkillError(f"skill 重名:{meta['name']}({seen[meta['name']]} 与 {d})")
            seen[meta["name"]] = d
            metas.append(meta)
        return metas

    def load_skill(self, name: str) -> str:
        """返回 skill 全文;不存在抛 SkillError。"""
        f = self.root / name / "SKILL.md"
        if not f.is_file():
            raise SkillError(f"skill 不存在:{name}")
        return f.read_text(encoding="utf-8")

    def _parse_skill_dir(self, d: Path) -> dict | None:
        f = d / "SKILL.md"
        if not f.is_file():
            print(f"[skills] 跳过 {d.name}:缺少 SKILL.md", file=sys.stderr)
            return None
        meta = _parse_frontmatter(f.read_text(encoding="utf-8"))
        name = meta.get("name")
        if not name or not isinstance(name, str):
            print(f"[skills] 跳过 {d.name}:frontmatter 缺 name", file=sys.stderr)
            return None
        if not _NAME_RE.match(name):
            print(f"[skills] 跳过 {d.name}:name 不合法 {name!r}(须 ^[a-z0-9-]+$)", file=sys.stderr)
            return None
        return {
            "name": name,
            "description": str(meta.get("description", "")).strip(),
            "dir": str(d),
        }


def render_skills_meta(metas: list[dict]) -> str:
    """元数据列表 -> 提示词片段(每行 name: description)。纯函数,便于单测。"""
    if not metas:
        return "(当前无已注册技能)"
    return "\n".join(f"- {m['name']}: {m['description']}" for m in metas)


@lru_cache(maxsize=1)
def _skills_meta() -> str:
    """默认目录的技能元数据(进程内缓存一次,静态内容 ADR-0011;目录变化重启刷新)。

    失败降级:目录缺失/重名 SkillError 等只告警返回占位文本,不阻塞路由。
    放在本模块而非 agent 包:supervisor 与 answer 两侧都要注入,agent 内
    supervisor<->answer 互相 import 会成环,技能域函数归技能域模块。
    """
    try:
        return render_skills_meta(SkillRegistry().list_metadata())
    except Exception as e:
        print(f"[skills] 元数据加载失败:{e}", file=sys.stderr)
        return "(技能系统暂不可用)"


if __name__ == "__main__":
    # 独立检查入口:python -m tools.skills.loader(Windows GBK 控制台先转 UTF-8)
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    for m in SkillRegistry().list_metadata():
        print(f"{m['name']}: {m['description']}  ({m['dir']})")
