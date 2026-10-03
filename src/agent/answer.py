"""answer 节点:汇总子智能体结果生成最终回答,消费后哨兵清空 subagent_results(T5)。

本文件作用:
    answer 节点读取 subagent_results,把各子图回传的 ResultSummary 渲染为
    固定三键格式文本注入消息流,再由 LLM 汇总作答;答毕返回 [RESET] 触发
    reducer 重置,防止上一轮结果泄漏到下一轮。

使用位置:
    - agent/build.py:build_graph() 挂 answer 节点;
    - agent/supervisor.py:route_node 复用 _render_results 渲染回收结果提示。
"""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.context import assembleView, maybeCompact
from agent.contracts import ResultSummary
from agent.memory_ctx import MEMORY_TOOLS, load_agents_md
from agent.state import RESET, AgentState
from settings.config import get_settings
from settings.loader import load_prompt
from tools.mcp.client import mcp_meta
from tools.sandbox.client import sandbox_meta
from tools.skills.loader import _skills_meta
from tools.tool.clock import get_current_time

MEMORY_LOOP_MAX = 4  # answer 侧记忆工具循环轮数上限(防失控,同子图双层策略)
# answer 的全部工具:记忆(memory-as-tool)+ 时钟(LLM 无实时时钟,时效判断必需)
ANSWER_TOOLS = [*MEMORY_TOOLS, get_current_time]

# 子结果"依据"渲染预算:子智能体验到的正文必须能进 answer 的上下文,
# 但不能无界(检索片段 × 多任务会撑爆提示词)。supervisor 侧不走这段(只做路由决策)。
EVIDENCE_ITEMS_MAX = 4  # 每条结果最多渲染几条依据
EVIDENCE_ITEM_CHARS = 250  # 单条依据正文上限
EVIDENCE_TOTAL_CHARS = 1200  # 单条结果"依据"整块上限(硬闸门)
SOURCES_MAX = 5  # 来源条数上限
# 成稿注入上限:完整成稿也要有界(多任务轮防止消息流膨胀);6000 字 ≈ 一篇完整调研报告
REPORT_MAX_CHARS = 6000


def _brief(value, limit: int = EVIDENCE_ITEM_CHARS) -> str:
    """折叠空白 + 截断:依据只给模型看关键片段,不做原文拼接。"""
    return " ".join(str(value or "").split())[:limit]


def _render_evidence(r: ResultSummary) -> list[str]:
    """把 data / sources 渲染成"依据 / 来源"两段(固定三键格式的按需扩展)。

    支持两种已约定的形状:retriever 的 `hits`(filename/seq/content)、
    research 的 `results`(title/url/snippet);其它形状退化为标量 key=value。
    背景:异步派发下 ResultSummary 是子结果回主图的唯一通道,只渲染结论会让
    正文丢失(见 troubleshooting/03-graph-skeleton.md §14)。
    """
    data = r.data if isinstance(r.data, dict) else {}
    items: list[str] = []

    hits = data.get("hits")
    results = data.get("results")
    fetches = data.get("fetches")
    if isinstance(hits, list):
        for h in hits[:EVIDENCE_ITEMS_MAX]:
            if not isinstance(h, dict):
                continue
            name = h.get("filename") or h.get("doc_id") or "?"
            items.append(f"《{name}》#{h.get('seq', '?')}:{_brief(h.get('content'))}")
    if isinstance(results, list):
        for h in results[:EVIDENCE_ITEMS_MAX]:
            if not isinstance(h, dict):
                continue
            items.append(
                f"{_brief(h.get('title'), 80)}({h.get('url', '')}):{_brief(h.get('snippet'))}"
            )
    if isinstance(fetches, list):
        # web_fetch 抓取正文节选(2026-09-25):无此分支时正文进 data 但 answer 看不到,
        # 汇总只能基于 100 字 conclusion——"只回收了开头片段"的根因之一
        for f in fetches[:EVIDENCE_ITEMS_MAX]:
            if not isinstance(f, dict):
                continue
            items.append(f"网页正文({_brief(f.get('url'), 80)}):{_brief(f.get('excerpt'), 600)}")
    if not items:
        for k, v in data.items():
            if isinstance(v, (str, int, float)):
                items.append(f"{k}={_brief(v)}")
            if len(items) >= EVIDENCE_ITEMS_MAX:
                break

    lines: list[str] = []
    if items:
        block = "\n".join(f"    - {it}" for it in items)
        lines.append("  依据:\n" + block[:EVIDENCE_TOTAL_CHARS])
    if r.sources:
        lines.append("  来源:" + " ".join(str(s) for s in r.sources[:SOURCES_MAX]))
    return lines


def _render_results(results: list[ResultSummary], with_evidence: bool = False) -> str:
    """docs/design/PROMPT-DESIGN §1.3:子结果渲染为固定三键格式,不原文拼接。

    with_evidence=True 追加"依据/来源"正文——**只有 answer 汇总时需要**;
    supervisor 的回收提示保持精简(路由只看决策字段,不必把检索正文塞进每轮路由)。
    """
    lines = []
    for i, r in enumerate(results, 1):
        clarification = "、".join(r.needs_clarification) if r.needs_clarification else "-"
        warnings = "、".join(r.warnings) if r.warnings else "-"
        lines.append(
            f"[{i}] agent={r.agent} | 任务:{r.task} | 结果:{r.conclusion}"
            f" {' '.join(r.key_points)} | 澄清:{clarification} | 执行提示:{warnings}"
        )
        if with_evidence:
            report = (r.report or "").strip()
            if report:
                # 成稿优先(P0):双重截断只对"碎片 evidence"有意义,成稿是模型基于
                # 完整上下文写好的成品,原样注入;只做总长闸门防多任务轮膨胀
                lines.append("  成稿:")
                lines.append(report[:REPORT_MAX_CHARS])
            else:
                lines.extend(_render_evidence(r))
    return "\n".join(lines)


def _answer_with_memory(llm, messages) -> AIMessage:
    """answer 侧记忆工具循环(ADR-0011):主智能体可调 memory_search/store_memory,
    结果以 ToolMessage 进本轮消息流;无 tool_calls 即收尾。工具消息不写回主图 state
    (按需查询,不污染后续轮次的固定 system 前缀)。"""
    llm_with_tools = llm.bind_tools(ANSWER_TOOLS)
    res = llm_with_tools.invoke(messages)
    for _ in range(MEMORY_LOOP_MAX):
        if not getattr(res, "tool_calls", None):
            break
        tool_msgs = []
        for call in res.tool_calls:
            tool = next((t for t in ANSWER_TOOLS if t.name == call["name"]), None)
            content = (
                f"未知工具:{call['name']}"
                if tool is None
                else str(tool.invoke(call["args"]))
            )
            tool_msgs.append(ToolMessage(content=content, tool_call_id=call["id"]))
        messages = [*messages, res, *tool_msgs]  # tool 消息必须跟随带 tool_calls 的 assistant 消息
        res = llm_with_tools.invoke(messages)
    return res


def answer_node(state: AgentState, llm) -> dict:
    """读 subagent_results 汇总作答,随后 RESET 哨兵清空。

    系统提示词含 agents.md 固定段(ADR-0011:不注入记忆);用户本人问题由
    记忆工具(memory_search/store_memory)按需查询,结果进消息流不进 system。
    清空不能返回空列表:operator.add 加 [] 不改原值;必须返回 [RESET]
    触发 _add_or_reset 的重置分支。
    """
    results = state.get("subagent_results") or []
    rendered = _render_results(results, with_evidence=True)
    system = load_prompt(
        "answer", skills_meta=_skills_meta(), mcp_meta=mcp_meta(),
        sandbox_meta=sandbox_meta(), agents_md=load_agents_md()
    )
    # ---- P4 上下文分层:先 compact(唯一触发点与写回点)再拼装视图(05 §2.2/§2.4) ----
    cfg = get_settings()
    digestState = state.get("contextDigest") or {}
    newDigest = maybeCompact(
            state["messages"], digestState, llm,
            cfg.context_budget_chars, cfg.digest_target_chars,
        )
    if newDigest is not None:
        digestState = newDigest
    messages = assembleView(system, digestState, state["messages"], cfg.long_msg_limit)
    if rendered:
        messages.append(HumanMessage(content=rendered))  # 子结果进消息流,不进系统提示词
    res = _answer_with_memory(llm, messages)
    result = {"messages": [res], "subagent_results": [RESET]}
    if newDigest is not None:
        result["contextDigest"] = newDigest  # 单点写(05 §六红线)
    return result
