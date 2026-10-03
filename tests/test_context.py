"""agent_opt_0.1 M5(P4 上下文分层)单测:assembleView / locateWatermark / overBudget / maybeCompact。

方案:docs/new_module/agent_opt_0.1/05-上下文分层.md §二/§四;fake LLM 惯例同 test_react_report。
锁三条核心不变量:①digest 冻结 + 水位不动 + append-only ⇒ assembleView 输出前缀稳定
(缓存零损失);②存储层 messages 永不删改;③compact 只在超预算时发生,失败降级不抛错。
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent.context import (
    DIGEST_HEADER,
    assembleView,
    locateWatermark,
    maybeCompact,
    overBudget,
)


def _msg(content, mid=None):
    return HumanMessage(content=content, id=mid)


def _digest(digest="旧摘要", upto=None):
    return {"digest": digest, "uptoId": upto}


# ---------- overBudget ----------


def test_over_budget_boundaries():
    """预算边界:低于不超、等于不超(> 才算超)、超出为真。"""
    msgs = [_msg("12345")]
    assert overBudget(msgs, 6) is False
    assert overBudget(msgs, 5) is False
    assert overBudget(msgs, 4) is True


# ---------- locateWatermark ----------


def test_locate_watermark_hit_and_miss():
    """命中返回下标;未命中 / 空 id 返回 -1(调用方降级全量直塞)。"""
    msgs = [_msg("a", "m1"), _msg("b", "m2"), _msg("c", "m3")]
    assert locateWatermark(msgs, "m2") == 1
    assert locateWatermark(msgs, "不存在") == -1
    assert locateWatermark(msgs, "") == -1


# ---------- assembleView ----------


def test_assemble_view_empty_digest_equals_status_quo():
    """digest 缺省:退化为现状 = 固定 system + 全量消息(活跃段对象原样)。"""
    msgs = [_msg("a", "m1"), _msg("b", "m2")]
    view = assembleView("SYS", {}, msgs, longMsgLimit=100)
    assert len(view) == 3
    assert isinstance(view[0], SystemMessage) and view[0].content == "SYS"
    assert view[1] is msgs[0] and view[2] is msgs[1]


def test_assemble_view_digest_then_active():
    """水位在中间:视图 = system + 摘要消息(带前缀) + 水位后原始消息。"""
    msgs = [_msg("旧1", "m1"), _msg("旧2", "m2"), _msg("新", "m3")]
    view = assembleView("SYS", _digest("旧文摘要", "m2"), msgs, longMsgLimit=100)
    assert len(view) == 3
    assert view[1].content == DIGEST_HEADER + "旧文摘要"
    assert view[2] is msgs[2]  # 活跃段原样,不改写


def test_assemble_view_watermark_miss_degrades_full():
    """uptoId 定位失败:不注入 digest,全量直塞(= 现状,05 §七降级语义)。"""
    msgs = [_msg("a", "m1"), _msg("b", "m2")]
    view = assembleView("SYS", _digest("孤儿摘要", "gone"), msgs, longMsgLimit=100)
    assert len(view) == 3
    assert all("孤儿摘要" not in str(m.content) for m in view)
    assert view[1] is msgs[0] and view[2] is msgs[1]


def test_assemble_view_deterministic_for_cache():
    """缓存不变量:同一输入两次拼装输出逐字节相同(digest 冻结 + append-only)。"""
    msgs = [_msg("旧" * 50, "m1"), _msg("新" * 30, "m2")]
    d = _digest("摘要正文" * 10, "m1")
    v1 = assembleView("SYS", d, msgs, longMsgLimit=100)
    v2 = assembleView("SYS", d, msgs, longMsgLimit=100)
    assert [m.content for m in v1] == [m.content for m in v2]


def test_assemble_view_truncates_long_msg_deterministically():
    """单条超长:视图内确定性截断(固定省略标记);原文对象与 id 不动。"""
    big = _msg("长" * 200, "m1")
    msgs = [big, _msg("b", "m2")]
    view = assembleView("SYS", {}, msgs, longMsgLimit=50)
    assert view[1].content == "长" * 50 + "…[截断,原文 200 字符]"
    assert view[1].id == "m1" and view[1] is not big
    assert big.content == "长" * 200  # 存储层原文不动
    # 确定性:同一输入再拼一次,截断文本相同(缓存安全)
    assert assembleView("SYS", {}, msgs, longMsgLimit=50)[1].content == view[1].content


# ---------- maybeCompact ----------


class FakeLLM:
    """记录 prompt;按脚本返回正文或抛异常(compact 失败降级用)。"""

    def __init__(self, content=None, exc=None):
        self.content = content
        self.exc = exc
        self.prompts: list[str] = []

    def invoke(self, messages):
        self.prompts.append(str(messages))
        if self.exc:
            raise self.exc
        return AIMessage(content=self.content or "")


def _fake_prompt(monkeypatch, captured):
    """打桩 load_prompt(compact.md 未誊写前即可测);槽位名不符会在取值时 KeyError。"""

    def fakeLoad(name, **slots):
        captured["name"] = name
        captured["slots"] = slots
        return f"摘要指令|{slots['digest']}|{slots['transcript']}|{slots['target']}"

    monkeypatch.setattr("agent.context.load_prompt", fakeLoad)


def _state_msgs():
    return [_msg("旧" * 30, "m1"), _msg("新" * 30, "m2")]


def test_maybe_compact_under_budget_no_llm():
    """未超预算:确定性检查直接返回 None,零 LLM 调用。"""
    llm = FakeLLM()
    assert maybeCompact(
            _state_msgs(), {}, llm, budget=10_000, target=100,
        ) is None
    assert llm.prompts == []


def test_maybe_compact_over_budget_summarizes(monkeypatch):
    """超预算:恰调一次摘要 LLM,prompt 带旧 digest 与活跃段;水位推进到末条 id。"""
    captured: dict = {}
    _fake_prompt(monkeypatch, captured)
    llm = FakeLLM(content="新摘要正文")
    out = maybeCompact(
            _state_msgs(),
            _digest("旧摘要", "m1"),
            llm,
            budget=10,
            target=2000,
        )
    assert out == {"digest": "新摘要正文", "uptoId": "m2"}
    assert len(llm.prompts) == 1
    assert captured["name"] == "compact"
    assert captured["slots"]["digest"] == "旧摘要"
    assert "新" * 30 in captured["slots"]["transcript"]
    assert captured["slots"]["target"] == "2000"


def test_maybe_compact_llm_failure_degrades(monkeypatch):
    """摘要 LLM 异常:返回 None 降级(调用方保留旧 digest),不抛错。"""
    _fake_prompt(monkeypatch, {})
    llm = FakeLLM(exc=RuntimeError("摘要服务超时"))
    assert maybeCompact(_state_msgs(), {}, llm, budget=10, target=100) is None


def test_maybe_compact_empty_output_degrades(monkeypatch):
    """摘要产出空串:视为失败,返回 None(不写回空 digest)。"""
    _fake_prompt(monkeypatch, {})
    assert maybeCompact(_state_msgs(), {}, FakeLLM(content="  "), budget=10, target=100) is None


def test_maybe_compact_last_msg_without_id_aborts(monkeypatch):
    """活跃段末条消息无 id:水位会失效,放弃 compact 返回 None(避免每轮重摘)。"""
    _fake_prompt(monkeypatch, {})
    llm = FakeLLM(content="摘要")
    assert maybeCompact([_msg("长" * 100)], {}, llm, budget=10, target=100) is None
    assert llm.prompts == []
