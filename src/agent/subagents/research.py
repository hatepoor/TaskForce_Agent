import json
import uuid

from langchain_core.messages import ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent.contracts import ResultSummary, SubgraphContract
from agent.memory_ctx import load_agents_md
from agent.subagents.react import ReactState, build_react_subgraph, extract_answer
from settings.loader import load_prompt
from tools.websearch.search import web_search

MAX_ITERATIONS = 8  # 工具执行轮数上限(主图 recursion_limit 兜底)
RESULTS_IN_DATA = 8  # 回传答案侧的检索条目上限(渲染侧还会再收一次)
SOURCES_LIMIT = 10  # 来源 URL 上限


def _collect_results(messages: list) -> list[dict]:
    """从 web_search 的 ToolMessage(JSON 数组)确定性收集检索条目,跨调用按 url/title 去重。

    条目带 title/url/snippet:进 `ResultSummary.data["results"]`,answer 汇总时据此作答
    (只回传 100 字结论会让正文丢失,troubleshooting/03 §14)。
    """
    seen: set[str] = set()
    out: list[dict] = []
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        try:
            items = json.loads(m.content)
        except (json.JSONDecodeError, TypeError):
            continue  # 工具错误提示等非 JSON 文本,跳过
        if not isinstance(items, list):
            continue
        for h in items:
            if not isinstance(h, dict):
                continue
            url = str(h.get("url") or "").strip()
            key = url or str(h.get("title") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(
                {"title": h.get("title") or "", "url": url, "snippet": h.get("snippet") or ""}
            )
    return out


def _sources_of(results: list[dict]) -> list[str]:
    """有 URL 的条目取 url 作来源(保序去重已由 _collect_results 完成)。"""
    return [r["url"] for r in results if r["url"]][:SOURCES_LIMIT]


def build_research_graph(llm) -> CompiledStateGraph:
    """编译调研 ReAct 子图(共享键直挂,ADR-0009 方案 A)。"""
    research_prompt = load_prompt("subagents/research", agents_md=load_agents_md())
    system_prompt = load_prompt("base") + "\n\n" + research_prompt

    def build_summary(state: ReactState) -> ResultSummary:
        """收尾:被上限掐断→partial;无检索来源→need_clarification(不调 LLM);
        正常→解析最终消息 + 确定性检索条目/来源(零额外 LLM 调用)。"""
        contract = SubgraphContract(**state["contract"])
        task_id = uuid.uuid4().hex[:8]
        results = _collect_results(state["react_msgs"])
        sources = _sources_of(results)
        if getattr(state["react_msgs"][-1], "tool_calls", None):
            # 模型仍想调工具却被轮数上限截停:诚实返回不完整结果
            return ResultSummary(
                agent="research",
                task_id=task_id,
                task=contract.task,
                status="partial",
                conclusion="调研轮数达上限,返回当前所得",
                warnings=["达到工具调用轮数上限,调研结果可能不完整"],
                data={"results": results[:RESULTS_IN_DATA]},
                sources=sources,
            )
        if not sources:
            return ResultSummary(
                agent="research",
                task_id=task_id,
                task=contract.task,
                status="need_clarification",
                conclusion="联网未检索到相关信息",
                needs_clarification=["请提供更具体的检索方向或关键词"],
            )
        conclusion, key_points = extract_answer(str(state["react_msgs"][-1].content))
        return ResultSummary(
            agent="research",
            task_id=task_id,
            task=contract.task,
            status="success",
            conclusion=conclusion,
            key_points=key_points,
            data={"results": results[:RESULTS_IN_DATA]},
            sources=sources,
        )

    return build_react_subgraph(
        llm=llm,
        tools=[web_search],
        system_prompt=system_prompt,
        max_iterations=MAX_ITERATIONS,
        build_summary=build_summary,
    )
