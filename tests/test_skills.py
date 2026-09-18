"""模块 07 T1 单测:SkillRegistry 扫描/解析/加载(临时目录 fixture,不依赖真实 skills/)。"""

from pathlib import Path

import pytest

from tools.skills.loader import SkillError, SkillRegistry, render_skills_meta

GOOD = "---\nname: hello-world\ndescription: 演示技能\n---\n\n正文指令\n"


def _make_skill(root, name, md_text):
    d = root / name
    d.mkdir()
    (d / "SKILL.md").write_text(md_text, encoding="utf-8")


@pytest.fixture
def registry(tmp_path):
    return SkillRegistry(root=tmp_path)


def test_list_metadata_normal(registry, tmp_path):
    """正常两个 skill:按目录名排序返回 name/description/dir。"""
    _make_skill(tmp_path, "hello-world", GOOD)
    _make_skill(tmp_path, "code-run", "---\nname: code-run\ndescription: 运行代码\n---\n正文\n")
    metas = registry.list_metadata()
    assert [m["name"] for m in metas] == ["code-run", "hello-world"]
    assert metas[0]["description"] == "运行代码"
    assert Path(metas[0]["dir"]) == tmp_path / "code-run"


def test_missing_frontmatter_skipped(registry, tmp_path):
    """缺 frontmatter:告警跳过不阻塞,返回空列表。"""
    _make_skill(tmp_path, "no-front", "没有 frontmatter 的正文")
    assert registry.list_metadata() == []


def test_duplicate_name_raises(registry, tmp_path):
    """两个目录同名 name:抛可读错误(数据错误而非跳过)。"""
    _make_skill(tmp_path, "a", "---\nname: dup\ndescription: 1\n---\n")
    _make_skill(tmp_path, "b", "---\nname: dup\ndescription: 2\n---\n")
    with pytest.raises(SkillError, match="重名"):
        registry.list_metadata()


def test_invalid_name_skipped(registry, tmp_path):
    """name 含非法字符(空格/中文):告警跳过。"""
    _make_skill(tmp_path, "bad-name", "---\nname: 你好 world\ndescription: x\n---\n")
    assert registry.list_metadata() == []


def test_load_skill_full_text(registry, tmp_path):
    _make_skill(tmp_path, "hello-world", GOOD)
    assert registry.load_skill("hello-world") == GOOD


def test_load_skill_missing_raises(registry):
    with pytest.raises(SkillError, match="不存在"):
        registry.load_skill("nope")


# ---------- T2:元数据渲染进 supervisor 提示词 ----------


def test_render_skills_meta_normal():
    metas = [{"name": "hello-world", "description": "演示技能", "dir": "x"}]
    assert render_skills_meta(metas) == "- hello-world: 演示技能"


def test_render_skills_meta_empty():
    assert render_skills_meta([]) == "(当前无已注册技能)"


def test_skills_meta_cached(monkeypatch):
    """_skills_meta 进程内缓存(ADR-0011 静态内容):多次调用只扫一次目录。"""
    from tools.skills import loader as sk

    sk._skills_meta.cache_clear()

    class FakeRegistry:
        def __init__(self, root=None):
            pass

        def list_metadata(self):
            calls.append(1)
            return [{"name": "s1", "description": "d", "dir": "x"}]

    calls: list[int] = []
    monkeypatch.setattr(sk, "SkillRegistry", FakeRegistry)
    assert sk._skills_meta() == "- s1: d"
    assert sk._skills_meta() == "- s1: d"
    assert len(calls) == 1
    sk._skills_meta.cache_clear()


def test_skills_meta_degrades_on_error(monkeypatch):
    """目录错误(如重名 SkillError)降级返回占位文本,不阻塞路由。"""
    from tools.skills import loader as sk

    sk._skills_meta.cache_clear()

    def boom(*a, **k):
        raise SkillError("skill 重名:dup")

    monkeypatch.setattr(sk, "SkillRegistry", boom)
    assert sk._skills_meta() == "(技能系统暂不可用)"
    sk._skills_meta.cache_clear()
