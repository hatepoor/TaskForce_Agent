import json
import uuid

from langchain_core.messages import ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent.contracts import ResultSummary, SubgraphContract
from agent.memory_ctx import load_agents_md
from agent.subagents.react import ReactState, build_react_subgraph, extract_answer
from settings.loader import load_prompt
from tools.tool.clock import get_current_time
from tools.webfetch.fetch import web_fetch
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


FETCH_EXCERPT_CHARS = 2000   # web_fetch 正文进 data 的节选上限(完整正文已供模型总结)
FETCHES_IN_DATA = 5          # data["fetches"] 条目上限


def _collectFetches(messages: list) -> list[dict]:
    """从 web_fetch 的 ToolMessage 确定性收集抓取正文(2026-09-25 冒烟修正)。

    成功条目 content 形如 "[网页正文 | {url} | {n} 字符]\\n<硬声明>\\n<web_content>\\n
    {text}\\n</web_content>";失败条目以 "[抓取失败]" 开头、其他工具输出不匹配前缀,
    一律跳过。正文节选进 data["fetches"] 供 answer 溯源——此前 finalize 只认
    web_search 的产出,只调 web_fetch 的任务会被误判"联网未检索到相关信息"。
    """
    out: list[dict] = []
    seen: set[str] = set()
    for m in messages:
        if not isinstance(m, ToolMessage):
            continue
        c = str(m.content)
        if not c.startswith("[网页正文 |"):
            continue
        head = c.split("\n", 1)[0]
        url = head.split(" | ")[1].strip() if " | " in head else ""
        text = ""
        if "<web_content>" in c and "</web_content>" in c:
            text = c.split("<web_content>", 1)[1].split("</web_content>", 1)[0].strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"url": url, "excerpt": text[:FETCH_EXCERPT_CHARS]})
    return out


def build_research_graph(llm) -> CompiledStateGraph:
    """编译调研 ReAct 子图(共享键直挂,ADR-0009 方案 A)。"""
    research_prompt = load_prompt("subagents/research", agents_md=load_agents_md())
    system_prompt = load_prompt("base") + "\n\n" + research_prompt

    def build_summary(state: ReactState) -> ResultSummary:
        """收尾:被上限掐断→partial;检索与抓取双空→need_clarification(不调 LLM);
        正常→解析最终消息 + 确定性检索条目/抓取节选/来源(零额外 LLM 调用)。"""
        contract = SubgraphContract(**state["contract"])
        task_id = uuid.uuid4().hex[:8]
        results = _collect_results(state["react_msgs"])
        fetches = _collectFetches(state["react_msgs"])
        sources = _sources_of(results)
        for f in fetches:
            if f["url"] not in sources:
                sources.append(f["url"])
        sources = sources[:SOURCES_LIMIT]
        if getattr(state["react_msgs"][-1], "tool_calls", None):
            # 模型仍想调工具却被轮数上限截停:诚实返回不完整结果
            data = {"results": results[:RESULTS_IN_DATA]}
            if fetches:
                data["fetches"] = fetches[:FETCHES_IN_DATA]
            return ResultSummary(
                agent="research",
                task_id=task_id,
                task=contract.task,
                status="partial",
                conclusion="调研轮数达上限,返回当前所得",
                warnings=["达到工具调用轮数上限,调研结果可能不完整"],
                data=data,
                sources=sources,
            )
        if not sources and not fetches:
            return ResultSummary(
                agent="research",
                task_id=task_id,
                task=contract.task,
                status="need_clarification",
                conclusion="联网未检索到相关信息",
                needs_clarification=["请提供更具体的检索方向或关键词"],
            )
        conclusion, keyPoints, report = extract_answer(str(state["react_msgs"][-1].content))
        data = {"results": results[:RESULTS_IN_DATA]}
        if fetches:
            data["fetches"] = fetches[:FETCHES_IN_DATA]
        return ResultSummary(
            agent="research",
            task_id=task_id,
            task=contract.task,
            status="success",
            conclusion=conclusion,
            key_points=keyPoints,
            data=data,
            sources=sources,
            report=report,
        )

    return build_react_subgraph(
        llm=llm,
        tools=[web_search, get_current_time, web_fetch],
        system_prompt=system_prompt,
        max_iterations=MAX_ITERATIONS,
        build_summary=build_summary,
    )
