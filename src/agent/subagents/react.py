"""ReAct 循环共享骨架(R-T2,ADR-0010):三子智能体统一的手写 ReAct 实现。

形态:START → agent(bind_tools) → [有 tool_calls 且未达上限 → tools → agent] → finalize → END。

- 防失控双层:子图自数 iteration(每执行一轮工具 +1),超限经条件边优雅收尾;
  主图 recursion_limit 仅作全局兜底(ADR-0009 §2B v3 补注)。
- 红线(ADR-0010 + 实测补充):循环必须留在编译子图内部;私有消息键必须用 add_messages
  reducer,且**不得命名为 messages**——直挂模式下父子图同键名即共享通道,子图消息会
  并进主图 messages 历史(实证:supervisor/answer 会看到 ToolMessage)。
- 工具节点手写(等价 prebuilt ToolNode):单次调用异常兜底为错误 ToolMessage 不炸图,
  且显式做 iteration 计数;tool_call 的 id 与 ToolMessage.tool_call_id 必须配对。

使用位置:
    - agent/subagents/retriever.py:装配 kb_search 工具(05 模块,已落地);
    - 09 research / 10 executor 子智能体按同一骨架复用(差异仅工具集/轮数上限/收尾函数);
    - tests/test_graph.py、tests/test_retriever.py:ReAct 行为测试。
"""

import json
from collections.abc import Callable
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from agent.contracts import ResultSummary, SubgraphContract

CONTEXT_BUDGET_CHARS = 16_000  # 子图私有消息字符预算(中文≈1 字/token),超限注入收尾提示(T3 闸门)
WRAPUP_HINT = "注意:上下文已接近预算上限,请基于现有信息尽快收尾,不要再发起新的工具调用。"


class ReactState(TypedDict):
    """ReAct 子图 state:共享键(直挂)+ 私有键(主图不可见)。"""

    contract: SubgraphContract  # 共享键:Send payload 直达
    subagent_results: list  # 共享键:写回主图 reducer 合并
    # 私有键:ReAct 循环消息(键名勿用 messages,原因见文件头红线)
    react_msgs: Annotated[list, add_messages]
    iteration: int  # 私有键:已执行的工具轮数


def contract_message(contract: SubgraphContract) -> str:
    """契约四件套拼成给子智能体 LLM 的用户消息。"""
    parts = [f"任务:{contract.task}", f"用户原话:{contract.user_utterance}"]
    if contract.input_data:
        parts.append(f"结构化输入:{json.dumps(contract.input_data, ensure_ascii=False)}")
    if contract.output_schema_hint:
        parts.append(f"输出要求:{contract.output_schema_hint}")
    return "\n".join(parts)

def _msgs_over_budget(messages: list) -> bool:
    """私有消息总字符数是否越过预算(上下文膨胀闸门,PROMPT-DESIGN §2.5-3)。"""
    return sum(len(getattr(m, "content", "") or "") for m in messages) > CONTEXT_BUDGET_CHARS


def extract_answer(text: str) -> tuple[str, list[str]]:
    """从 agent 最终消息提取(结论, 要点):优先解析模型自发的摘要 JSON,失败则折叠
    空白后截断原文(提示词已要求自然语言收尾,此处兜底 markdown 伪 schema 等形态)。"""
    fallback = " ".join((text or "").split())[:100] or "(无文本输出)"
    s = text.strip()
    if s.startswith("```"):  # 剥 markdown 围栏
        s = s[3:].lstrip()
        if s[:4].lower() == "json":
            s = s[4:]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
        s = s.strip()
    try:
        obj = json.loads(s)
    except ValueError:
        return fallback, []
    if isinstance(obj, dict) and isinstance(obj.get("conclusion"), str):
        key_points = [str(k) for k in obj.get("key_points", []) if str(k).strip()][:5]
        return obj["conclusion"][:100], key_points
    return fallback, []

def build_react_subgraph(
    llm,
    tools: list,
    system_prompt: str,
    max_iterations: int,
    build_summary: Callable[[dict], ResultSummary],
) -> CompiledStateGraph:
    """编译通用 ReAct 子图;05/09/10 复用,差异仅工具集/轮数上限/收尾函数。

    build_summary(state) 由各子智能体提供:读取消息历史产出 ResultSummary,
    需自行处理"被上限掐断 / 无结果 / 正常"三种分支。
    """
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: ReactState) -> dict:
        """模型节点:首帧把任务契约渲染为系统+用户消息,之后按完整消息历史续推。

        上下文膨胀闸门(T3):私有消息超字符预算时注入一次"尽快收尾"提示,
        让模型基于现有信息收尾而非继续调工具(与硬上限互补,§2.5-3/4)。
        """
        if not state.get("react_msgs"):
            contract = SubgraphContract(**state["contract"])
            seed = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=contract_message(contract)),
            ]
            return {"react_msgs": seed + [llm_with_tools.invoke(seed)]}
        msgs = state["react_msgs"]
        hint = None
        if _msgs_over_budget(msgs) and not any(
            getattr(m, "content", "") == WRAPUP_HINT for m in msgs
        ):
            hint = SystemMessage(content=WRAPUP_HINT)
            msgs = [*msgs, hint]
        res = llm_with_tools.invoke(msgs)
        if hint is not None:
            # 提示一并写回 state:add_messages 按 id 去重,后续帧 guard 才能识别"已注入过"
            return {"react_msgs": [hint, res]}
        return {"react_msgs": [res]}

    def tools_node(state: ReactState) -> dict:
        """工具节点:执行本轮全部 tool_calls,结果回填 ToolMessage;轮数 +1。"""
        tool_messages: list[ToolMessage] = []
        for call in state["react_msgs"][-1].tool_calls:
            tool = next((t for t in tools if t.name == call["name"]), None)
            if tool is None:
                content = f"未知工具:{call['name']}"
            else:
                try:
                    content = str(tool.invoke(call["args"]))
                except Exception as e:  # 单次失败不炸图,错误文本交给模型自行决策
                    content = f"工具执行出错:{e}"
            tool_messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
        return {"react_msgs": tool_messages, "iteration": state.get("iteration", 0) + 1}

    def route(state: ReactState) -> Literal["tools", "finalize"]:
        """条件边:还有工具调用且未达轮数上限 → tools;否则收尾。"""
        has_calls = bool(getattr(state["react_msgs"][-1], "tool_calls", None))
        if has_calls and state.get("iteration", 0) < max_iterations:
            return "tools"
        return "finalize"

    def finalize_node(state: ReactState) -> dict:
        """收尾:由调用方提供的 build_summary 把消息历史收敛为 ResultSummary。"""
        return {"subagent_results": [build_summary(state)]}

    g = StateGraph(ReactState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()
