"""模型配置覆盖单测:.taskforce 覆盖表读写/合并/掩码 + /models/config 两端点(不连 DB/LLM)。"""

import json

from fastapi.testclient import TestClient

import api.routers.model_settings as ms
from api.main import app
from settings.model_overrides import (
    is_http_url,
    is_masked,
    load_overrides,
    mask,
    merge_overrides,
    save_overrides,
)

# ---------- 覆盖表本身(settings/model_overrides.py) ----------

def test_load_overrides_missing_broken_and_dirty(tmp_path):
    """缺失/损坏/非 dict 一律空表;非法键与空值剔除(配置读不出来不该让进程起不来)。"""
    assert load_overrides(tmp_path / "nope.json") == {}
    p = tmp_path / "model_config.json"
    p.write_text("{不是 JSON", encoding="utf-8")
    assert load_overrides(p) == {}
    p.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
    assert load_overrides(p) == {}
    p.write_text(
        json.dumps({"llm_model": "m1", "unknown_field": "x", "llm_api_key": ""}),
        encoding="utf-8",
    )
    assert load_overrides(p) == {"llm_model": "m1"}


def test_save_then_load_roundtrip(tmp_path):
    """保存后可原样读回;清表落空对象。"""
    p = tmp_path / "model_config.json"
    save_overrides({"llm_base_url": "https://x.example/v1", "llm_model": "m1"}, p)
    assert load_overrides(p) == {"llm_base_url": "https://x.example/v1", "llm_model": "m1"}
    save_overrides({}, p)
    assert load_overrides(p) == {}


def test_merge_overrides_clear_keep_and_trim():
    """缺项/None=不动;空串=清除覆盖(回落 .env);密钥掩码=保持不动;值去空白写入。"""
    cur = {"llm_api_key": "sk-real", "llm_model": "m1"}
    out = merge_overrides(cur, {
        "llm_model": "",                      # 清除
        "llm_api_key": mask("sk-real"),       # 掩码占位 → 原值保持
        "embedding_model": "  emb-1  ",       # 归一
        "embedding_api_key": None,            # 未提交 → 不动
        "unknown_field": "x",                 # 非法键忽略
    })
    assert out == {"llm_api_key": "sk-real", "embedding_model": "emb-1"}


def test_mask_and_is_masked():
    assert mask("") == ""
    assert mask("short") == "*****"                      # 短值全掩
    m = mask("sk-abcdefgh12345678")
    assert m.startswith("sk-a") and m.endswith("5678") and "****" in m
    assert is_masked(m) is True
    assert is_masked("") is True                         # 空值不是真实密钥
    assert is_masked("sk-real-key") is False


def test_is_http_url():
    assert is_http_url("http://127.0.0.1:8000/v1") is True
    assert is_http_url("https://api.example.com/v1") is True
    assert is_http_url("api.example.com") is False
    assert is_http_url("https://") is False


# ---------- 端点(/models/config) ----------

_ENV_DEFAULTS = {
    "llm_base_url": "https://env.example/v1",
    "llm_api_key": "sk-env-12345678",
    "llm_model": "env-model",
    "embedding_base_url": "",
    "embedding_api_key": "",
    "embedding_model": "",
}


def _patch(monkeypatch, saved=None, applied=None, env=None):
    """替换路由依赖:effective_config(.env+覆盖表)/applied_overrides(启动快照)/读写。"""
    state = {"saved": dict(saved or {}), "applied": dict(applied or {})}
    env_values = dict(_ENV_DEFAULTS if env is None else env)

    def fake_effective():
        merged = dict(env_values)
        merged.update(state["saved"])
        return merged

    def fake_save(values, path=None):
        state["saved"] = {k: v for k, v in values.items() if v != ""}
        return dict(state["saved"])

    monkeypatch.setattr(ms, "effective_config", fake_effective)
    monkeypatch.setattr(ms, "applied_overrides", lambda: dict(state["applied"]))
    monkeypatch.setattr(ms, "load_overrides", lambda path=None: dict(state["saved"]))
    monkeypatch.setattr(ms, "save_overrides", fake_save)
    return TestClient(app), state


def test_get_config_masks_keys_and_flags_restart(monkeypatch):
    """GET:表单口径是"保存并重启后"的值;密钥只回掩码;盘上与启动快照不一致 → 提示重启。"""
    client, _ = _patch(monkeypatch, saved={"llm_model": "new-model"}, applied={})
    body = client.get("/models/config").json()
    assert body["config"]["llm_model"] == "new-model"          # 覆盖表的值(重启后生效)
    assert body["config"]["llm_base_url"] == "https://env.example/v1"  # 未覆盖项走 .env
    assert body["config"]["llm_api_key"] == mask("sk-env-12345678")
    assert "sk-env-12345678" not in json.dumps(body)           # 原文绝不外泄
    assert body["overridden"] == ["llm_model"]
    assert body["restart_required"] is True


def test_get_config_no_restart_when_in_sync(monkeypatch):
    """盘上与启动快照一致:不提示重启。"""
    client, _ = _patch(monkeypatch, saved={"llm_model": "m1"}, applied={"llm_model": "m1"})
    body = client.get("/models/config").json()
    assert body["restart_required"] is False
    assert body["overridden"] == ["llm_model"]


def test_put_partial_only_touches_given_fields(monkeypatch):
    """缺项不动:改一项只发一项,其余覆盖保持原样(前端表单的提交口径)。"""
    client, state = _patch(
        monkeypatch, saved={"llm_model": "old", "embedding_model": "emb-old"}
    )
    body = client.put("/models/config", json={"llm_model": "new"}).json()
    assert state["saved"] == {"llm_model": "new", "embedding_model": "emb-old"}
    assert set(body["overridden"]) == {"llm_model", "embedding_model"}


def test_put_empty_string_clears_only_that_field(monkeypatch):
    """空串 = 清除该项覆盖(回落 .env),不影响其它已保存的覆盖。"""
    client, state = _patch(
        monkeypatch, saved={"llm_model": "m1", "llm_base_url": "https://x.example/v1"}
    )
    client.put("/models/config", json={"llm_model": ""})
    assert state["saved"] == {"llm_base_url": "https://x.example/v1"}


def test_put_keeps_masked_key(monkeypatch):
    """密钥掩码回传 = 保持不动(前端拿不到原文,原样提交不该把真 key 冲掉)。"""
    client, state = _patch(monkeypatch, saved={"llm_api_key": "sk-real"})
    client.put("/models/config", json={"llm_api_key": mask("sk-real")})
    assert state["saved"] == {"llm_api_key": "sk-real"}


def test_put_rejects_bad_base_url_without_saving(monkeypatch):
    """base_url 非 http(s) → 400,且不落盘。"""
    client, state = _patch(monkeypatch)
    r = client.put("/models/config", json={"llm_base_url": "api.example.com"})
    assert r.status_code == 400
    assert "http" in r.json()["detail"]
    assert state["saved"] == {}


def test_put_empty_body_is_noop(monkeypatch):
    """空对象提交:不报错也不改动(全可选的契约)。"""
    client, state = _patch(monkeypatch, saved={"llm_model": "m1"})
    assert client.put("/models/config", json={}).status_code == 200
    assert state["saved"] == {"llm_model": "m1"}
