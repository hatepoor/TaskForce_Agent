"""agent_opt_0.1 M1(成稿回传)单测:extract_answer 三元组 / validate_report / finalize 一次重试。

覆盖 answer 成稿优先渲染;方案:docs/new_module/agent_opt_0.1/01-成稿回传.md §三/§五/§六/§七。
fake model 模式沿用 test_retriever / test_research 的脚本化惯例;
ScriptLLM 的脚本帧序:第 1 帧给 agent 首帧,第 2 帧才是 finalize 的重试调用。
"""

import json

from langchain_core.messages import AIMessage

from agent.answer import REPORT_MAX_CHARS, _render_results
from agent.contracts import ResultSummary, SubgraphContract
from agent.subagents.react import (
    REPORT_MIN_CHARS,
    RETRY_PROMPT,
    build_react_subgraph,
    extract_answer,
    validate_report,
)

# ---------- extract_answer:二元组 → 三元组(§三) ----------


def test_extract_answer_json_with_report():
    """JSON 带 report:原样带回不截断(截断是 answer 注入侧的职责)。"""
    report = "成稿正文段落。" * 100
    text = json.dumps(
            {"conclusion": "结论", "key_points": ["a", "b"], "report": report},
            ensure_ascii=False,
        )
    assert extract_answer(text) == ("结论", ["a", "b"], report)


def test_extract_answer_json_without_report():
    """旧协议 JSON(无 report 字段):report 退空串,answer 侧回退 evidence 渲染。"""
    assert extract_answer('{"conclusion": "B", "key_points": ["k"]}') == ("B", ["k"], "")


def test_extract_answer_non_json_fallback():
    """非 JSON:折叠空白截 200,report 空串(兜底 markdown 伪 schema 等形态)。"""
    assert extract_answer("普通散文回答。") == ("普通散文回答。", [], "")
    assert extract_answer("") == ("(无文本输出)", [], "")


def test_extract_answer_conclusion_truncated_200():
    """conclusion 200 字上限(P0:100→200,契约/代码/提示词三处同步)。"""
    assert len(extract_answer("长" * 300)[0]) == 200


# ---------- validate_report 四分支(§五) ----------


def test_validate_report_ok():
    good = "完整的调研成稿,包含结论、依据与来源,展开论述篇幅足够,不是要点清单。" * 3
    assert validate_report(good, ["要点一"]) is None


def test_validate_report_missing_or_short():
    """缺失 / 过短(<REPORT_MIN_CHARS):同一原因。"""
    assert validate_report("", []) == "report 缺失或过短"
    assert validate_report("字" * (REPORT_MIN_CHARS - 1), []) == "report 缺失或过短"


def test_validate_report_lazy_copy_of_key_points():
    """照抄 key_points 交差:折叠全部空白后一致 → 不合格(样本须先过长检查)。"""
    kp = ["要点一" * 40, "要点二" * 40]
    report = "要点一" * 40 + "要点二" * 40  # 折叠空白后与 key_points 拼接一致
    assert validate_report(report, kp) == "report 不得照抄 key_points,必须展开成完整成稿"


# ---------- finalize:校验 + 恰好一次重试(§五) ----------


def _contract():
    return SubgraphContract(task="查X", user_utterance="查下 X").model_dump()


def _summary(status="success", report="", data=None, agent="retriever"):
    return ResultSummary(
            agent=agent,
            task_id="t1",
            task="查X",
            status=status,
            conclusion="c",
            key_points=["a"],
            data=data or {},
            report=report,
        )


class ScriptLLM:
    """记录每次 invoke 的输入;bind_tools 后按脚本返回,脚本耗尽返回固定散文。

    帧序约定:第 1 帧 = agent 首帧(seed),第 2 帧 = finalize 的重试调用;
    帧序写反时重试拿到的是耗尽兜底,断言必然失真(review 实测过的坑)。"""

    def __init__(self, rounds):
        self._rounds = list(rounds)
        self._i = 0
        self.inputs: list[list] = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.inputs.append(list(messages))
        if self._i < len(self._rounds):
            m = self._rounds[self._i]
            self._i += 1
            return m
        return AIMessage("兜底散文收尾")


_GOOD_REPORT = "完整成稿:结论、依据、来源齐全,展开论述的正文,篇幅远超校验下限,不是要点照抄。" * 3


def _graph(llm, summary):
    """build_summary 由测试直接注入固定 ResultSummary,精确控制 finalize 入口形状。"""
    return build_react_subgraph(
            llm=llm,
            tools=[],
            system_prompt="P",
            max_iterations=1,
            build_summary=lambda state: summary,
        )


def test_finalize_retry_once_and_update():
    """success + report 不合格:恰好一次重试且重试消息以重试指令结尾;合格 → 三字段更新。"""
    llm = ScriptLLM(rounds=[
            AIMessage("agent 首帧散文收尾"),  # 帧 1:被 agent_node 消费
            AIMessage(json.dumps(
                    {"conclusion": "重试结论", "key_points": ["b"], "report": _GOOD_REPORT},
                    ensure_ascii=False,
                )),  # 帧 2:被 finalize 重试消费
        ])
    final = _graph(llm, _summary(report="短")).invoke({"contract": _contract()})
    (s,) = final["subagent_results"]
    assert s.report == _GOOD_REPORT
    assert s.conclusion == "重试结论"
    assert s.key_points == ["b"]
    assert len(llm.inputs) == 2  # agent 首帧 + finalize 重试,恰好一次
    assert llm.inputs[-1][-1].content == RETRY_PROMPT.format(reason="report 缺失或过短")


def test_finalize_retry_still_bad_degrades():
    """重试仍不合格:清空成稿降级(status 仍 success),且无第二次重试。"""
    llm = ScriptLLM(rounds=[
            AIMessage("agent 首帧散文收尾"),
            AIMessage("重试还是散文"),
        ])
    final = _graph(llm, _summary(report="短")).invoke({"contract": _contract()})
    (s,) = final["subagent_results"]
    assert s.status == "success"
    assert s.report == ""
    assert len(llm.inputs) == 2


def test_finalize_good_report_no_retry():
    """首次成稿合格:零额外 LLM 调用(正常路径零开销)。"""
    llm = ScriptLLM(rounds=[])
    final = _graph(llm, _summary(report=_GOOD_REPORT)).invoke({"contract": _contract()})
    (s,) = final["subagent_results"]
    assert s.report == _GOOD_REPORT
    assert len(llm.inputs) == 1


def test_finalize_partial_and_clarification_no_retry():
    """partial / need_clarification 没有成稿可言:不校验不重试。"""
    for status in ("partial", "need_clarification"):
        llm = ScriptLLM(rounds=[])
        final = _graph(llm, _summary(status=status)).invoke({"contract": _contract()})
        (s,) = final["subagent_results"]
        assert s.status == status
        assert s.report == ""
        assert len(llm.inputs) == 1  # 只有 agent 首帧


# ---------- answer:_render_results 成稿优先(§六) ----------

_EVIDENCE_DATA = {"results": [{"title": "T", "url": "https://u", "snippet": "S"}]}


def test_render_report_first():
    """成稿优先:有 report 注入"成稿:"原文,不再走 evidence 渲染。"""
    out = _render_results([_summary(report="正文成稿", data=_EVIDENCE_DATA, agent="research")],
                          with_evidence=True)
    assert "成稿:" in out and "正文成稿" in out
    assert "依据:" not in out


def test_render_report_truncated_to_max():
    """成稿总长闸门:超 REPORT_MAX_CHARS 截断(多任务轮防消息流膨胀)。"""
    out = _render_results(
            [_summary(report="字" * (REPORT_MAX_CHARS + 100), data=_EVIDENCE_DATA,
                      agent="research")],
            with_evidence=True,
        )
    assert "字" * REPORT_MAX_CHARS in out
    assert "字" * (REPORT_MAX_CHARS + 1) not in out


def test_render_fallback_evidence_without_report():
    """无 report(旧协议/降级):回退 evidence 渲染,行为与改造前一致。"""
    out = _render_results([_summary(data=_EVIDENCE_DATA, agent="research")], with_evidence=True)
    assert "依据:" in out and "成稿:" not in out
