"""interrupt 载荷与合成消息前缀契约单测(c5):识别单点、旧形状兼容、前缀字面值锁定。"""

from agent.contracts import (
    PREFIX_SUBAGENT_RESULT,
    PREFIX_SYSTEM_NOTICE,
    PREFIX_USER_ANSWER,
    SYNTHETIC_USER_PREFIXES,
    ask_payload,
    classify_interrupt,
    memory_payload,
    plan_payload,
)
from agent.service import AUTO_NOTICE


def test_payload_builders_self_describe_kind():
    """生产者按契约构造:载荷自带 kind,入口无需按键名猜。"""
    assert ask_payload("哪一年?") == {"kind": "ask", "text": "哪一年?"}
    assert memory_payload("用户偏好 uv") == {"kind": "memory", "text": "用户偏好 uv"}


def test_classify_new_shape_kind_wins():
    assert classify_interrupt({"kind": "ask", "text": "q"}) == ("ask", "q")
    assert classify_interrupt({"kind": "memory", "text": "p"}) == ("memory", "p")


def test_classify_legacy_key_shape_compat():
    """存量检查点的 question/proposal 键名形状照常识别(不迁移旧数据)。"""
    assert classify_interrupt({"question": "旧问题"}) == ("ask", "旧问题")
    assert classify_interrupt({"proposal": "旧提案"}) == ("memory", "旧提案")


def test_classify_unknown_and_non_dict_not_silent():
    """未知形状/非 dict 给 unknown,调用方显式兜底而不是猜。"""
    kind, _ = classify_interrupt({"something": 1})
    assert kind == "unknown"
    assert classify_interrupt(None)[0] == "unknown"
    assert classify_interrupt({}) == ("unknown", "{}")


def test_interrupt_text_normalizes_escaped_newlines():
    """实测坑:模型把换行写成字面量 \\n,卡片会原样显示;载荷读写两侧都要还原。"""
    assert ask_payload("第一行\\n第二行")["text"] == "第一行\n第二行"
    assert memory_payload("a\\r\\nb")["text"] == "a\nb"
    assert plan_payload("s1\\ts2")["text"] == "s1\ts2"
    assert classify_interrupt({"kind": "ask", "text": "第一行\\n第二行"}) == (
        "ask",
        "第一行\n第二行",
    )
    assert classify_interrupt({"question": "旧\\n问题"}) == ("ask", "旧\n问题")
    # 已有真实换行的文本不能被二次破坏
    assert classify_interrupt({"kind": "ask", "text": "第一行\n第二行"}) == (
        "ask",
        "第一行\n第二行",
    )


def test_prefix_literals_locked():
    """前缀字面值与提示词/存量消息绑定,改值等于打断历史口径 —— 锁死。"""
    assert PREFIX_USER_ANSWER == "[用户回答]:"
    assert PREFIX_SUBAGENT_RESULT == "子智能体结果已回收"
    assert PREFIX_SYSTEM_NOTICE == "(系统通知)"
    assert set(SYNTHETIC_USER_PREFIXES) == {
        PREFIX_USER_ANSWER, PREFIX_SUBAGENT_RESULT, PREFIX_SYSTEM_NOTICE,
    }
    assert AUTO_NOTICE.startswith(PREFIX_SYSTEM_NOTICE)  # 触发语由前缀常量拼出
