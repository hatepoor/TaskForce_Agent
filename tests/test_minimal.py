"""模块 01 冒烟测试:UsageTracker 单测(零 API 成本)。

图相关用例(无 checkpointer invoke / run_turn 流式)在 03 主图重构后
迁至 tests/test_graph.py(T4 全图接线测试);run_turn 流式断言待 T5
answer 节点真正调 LLM 后恢复。
"""


def test_usage_tracker_accumulates_and_costs():
    """UsageTracker:累加正确、None 兜底、计费公式正确。"""
    from settings.config import get_settings
    from settings.usage import UsageTracker

    class Msg:
        def __init__(self, meta):
            self.usage_metadata = meta

    tracker = UsageTracker(get_settings())
    tracker.record(Msg({"input_tokens": 100, "output_tokens": 200}))
    tracker.record(Msg({"input_tokens": 50, "output_tokens": None}))
    tracker.record(Msg(None))                              # 只告警一次,不计次

    assert tracker.calls == 2
    assert tracker.input_tokens == 150
    assert tracker.output_tokens == 200
    text = tracker.stats_text()
    assert "150" in text and "200" in text
