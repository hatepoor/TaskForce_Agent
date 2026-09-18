"""memory 节点:显式写入(用户说"记住X"直写,无 interrupt,T3)/ 确认写入(T5,interrupt)。

T3 范围:用户显式要求记住 -> supervisor 路由 memory -> 本节点经 load_prompt("memory")
让 LLM 把用户原话压缩成一句话原子事实 -> 复用 store_memory 工具直写(ADR-0011 写入闭环),
不 interrupt;content 提炼为空时跳过写入并如实告知。
T5 将在此基础上加自主提案的确认写入(interrupt + /confirm yes|no)。

注:LLM 调用用普通 invoke + JSON 解析,而非 with_structured_output——make_llm 开启
streaming,结构化输出的 JSON 会作为流式 chunk 经 messages 流泄漏到终端(实测坑,
troubleshooting/06 #5);普通 invoke 还能拿到 usage_metadata 供 /stats 打点。

使用位置:
    - agent/build.py:build_graph() 挂 memory 节点;
    - tests/test_memory_node.py:显式写入行为测试(fake model + monkeypatch _default_store)。
"""
import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError

from agent.memory_ctx import store_memory
from agent.state import AgentState
from settings.loader import load_prompt


class MemoryProposal(BaseModel):
    """LLM 压缩出的记忆提案:一句话原子事实 + 来源标记(explicit/confirmed)。"""

    content: str = ""
    source: str = "explicit"


def _last_user_text(state: AgentState) -> str:
    """取最后一条真实用户消息(显式写入的输入),跳过"子智能体结果已回收"等内部消息。"""
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage) and not m.content.startswith("子智能体结果已回收"):
            return m.content or ""
    return ""


def _parse_memory_proposal(text: str) -> MemoryProposal:
    """解析模型 JSON 输出为 MemoryProposal;容错剥 markdown 围栏,失败返回空提案。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = "\n".join(line for line in t.splitlines() if not line.strip().startswith("```"))
    try:
        return MemoryProposal(**json.loads(t))
    except (json.JSONDecodeError, ValidationError, TypeError):
        return MemoryProposal()


def _propose(llm, user_text: str) -> tuple[MemoryProposal, dict | None]:
    """调 LLM 压缩用户原话为记忆提案,返回 (提案, usage_metadata)。"""
    res = llm.invoke(
        [
            SystemMessage(content=load_prompt("memory")),
            HumanMessage(content=user_text),
        ]
    )
    return _parse_memory_proposal(res.content), res.usage_metadata


def memory_node(state: AgentState, llm) -> dict:
    """记忆写入双分支(ADR-0008 单一挂起点):
    显式(用户说"记住X")→ 直接写,source=explicit,不 interrupt(T3);
    自主提案(用户透露值得记的事实)→ interrupt({"proposal": ...}) 挂起等确认,
    /confirm yes → 写入 source=confirmed;/confirm no → 跳过(T5)。
    """
    user_text = _last_user_text(state)
    if "记住" in user_text:
        proposal, usage = _propose(llm, user_text)
        content = (proposal.content or "").strip()
        if not content:
            return {"messages": [AIMessage(content="未提炼出值得记住的信息，未写入记忆")]}
        store_memory.invoke({"content": content, "source": proposal.source or "explicit"})
        return {"messages": [AIMessage(content=f"已记住:{content}", usage_metadata=usage)]}

    proposal, usage = _propose(llm, user_text)
    content = (proposal.content or "").strip()
    if not content:
        return {"messages": [AIMessage(content="本轮没有值得记住的信息")]}
    approved = interrupt({"proposal": content})
    if approved:
        store_memory.invoke({"content": content, "source": "confirmed"})
        return {"messages": [AIMessage(content=f"已记住:{content}", usage_metadata=usage)]}
    return {"messages": [AIMessage(content="好的,这条没有记入长期记忆。", usage_metadata=usage)]}
