"""冒烟测试:配置加载与缺失报错(T7 骨架 + 模块 00 验收的一部分)。"""

import pytest


def test_settings_load():
    """有 .env 时应正常返回配置对象。"""
    from settings.config import get_settings

    s = get_settings()
    assert s.llm_model
    assert s.database_url


def test_assert_ready_missing(monkeypatch):
    """核心配置为空时应抛含变量清单的 RuntimeError。"""
    from settings import config

    s = config.Settings(
        llm_base_url="", llm_api_key="", llm_model="", database_url=""
    )
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        config.assert_ready(s)
