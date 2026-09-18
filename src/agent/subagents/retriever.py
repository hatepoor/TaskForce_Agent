"""检索子智能体:持 kb_search 工具的 ReAct 检索循环(R-T3,ADR-0010)。

替换原三节点管线(rewrite→search→organize):查询改写由 LLM 多轮调 kb_search 涌现
(Agentic RAG);去重/截断内聚在工具内;finalize 从工具输出确定性重建 hits,并直接
解析 agent 最终消息为结论(不再发起第二次结构化 LLM 调用——实测 glm 对 QA 型任务
会以 content 自答而非调强制工具,with_structured_output 解析普通文本即崩)。

使用位置:
    - agent/build.py:build_graph() 中 build_retriever_graph(llm) 直挂 retriever 节点;
    - tests/test_retriever.py:检索子图行为测试。
"""

import json
import uuid

from langchain_core.messages import ToolMessage
from langgraph.graph.state import CompiledStateGraph

from agent.contracts import ResultSummary, SubgraphContract
from agent.subagents.react import ReactState, build_react_subgraph, extract_answer
from settings.loader import load_prompt
from tools.rag.kb_search import kb_search

MAX_ITERATIONS = 5  # 工具执行轮数上限(每轮≈2 super-steps;主图 recursion_limit 兜底)




def _collect_hits(messages: list) -> list[dict]:
    """从 kb_search 的 ToolMessage(JSON 数组)确定性重建 hits,跨调用按 (doc_id, seq) 去重。"""
    seen: set[tuple] = set()
    hits: list[dict] = []
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
            key = (h.get("doc_id"), h.get("seq"))
            if key not in seen:
                seen.add(key)
                hits.append(h)
    return hits


def build_retriever_graph(llm) -> CompiledStateGraph:
    """编译检索 ReAct 子图(共享键直挂,ADR-0009 方案 A)。"""
    system_prompt = load_prompt("base") + "\n\n" + load_prompt("subagents/retriever")

    def build_summary(state: ReactState) -> ResultSummary:
        """收尾:被上限掐断→partial;无命中→need_clarification(不调 LLM);
        正常→解析 agent 最终消息 + 确定性 hits(零额外 LLM 调用)。"""
        contract = SubgraphContract(**state["contract"])
        task_id = uuid.uuid4().hex[:8]
        if getattr(state["react_msgs"][-1], "tool_calls", None):
            # 模型仍想调工具却被轮数上限截停:诚实返回不完整结果
            return ResultSummary(
                agent="retriever",
                task_id=task_id,
                task=contract.task,
                status="partial",
                conclusion="检索轮数达上限,返回当前所得",
                warnings=["达到工具调用轮数上限,结果可能不完整"],
            )
        hits = _collect_hits(state["react_msgs"])
        if not hits:
            return ResultSummary(
                agent="retriever",
                task_id=task_id,
                task=contract.task,
                status="need_clarification",
                conclusion="知识库未检索到相关内容",
                needs_clarification=["知识库中没有与该任务相关的资料"],
            )
        conclusion, key_points = extract_answer(str(state["react_msgs"][-1].content))
        doc_ids = list(dict.fromkeys(h["doc_id"] for h in hits))
        return ResultSummary(
            agent="retriever",
            task_id=task_id,
            task=contract.task,
            status="success",
            conclusion=conclusion,
            key_points=key_points,
            data={"hits": hits},
            sources=doc_ids[:10],
        )

    return build_react_subgraph(
        llm=llm,
        tools=[kb_search],
        system_prompt=system_prompt,
        max_iterations=MAX_ITERATIONS,
        build_summary=build_summary,
    )
