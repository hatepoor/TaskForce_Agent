"""ask 节点:问询(第一个 interrupt,T4,ADR-0008 单一挂起点)。

supervisor 路由 ask 时,本节点 interrupt({"question": ...}) 挂起;CLI/API 打印问题,
用户自由文本输入即回答,以 Command(resume=text) 恢复;本节点把答案作为 user message
追加,沿 ask -> supervisor 边继续路由(答案参与后续决策)。

使用位置:
    - agent/build.py:build_graph() 挂 ask 节点(边 ask -> supervisor);
    - cli/repl.py / api:经 run_turn 的 on_interrupt 处理挂起;
    - tests/test_ask.py:挂起/恢复往返(fake model)。
"""
from langchain_core.messages import HumanMessage
from langgraph.types import interrupt

from agent.state import AgentState


def ask_node(state:AgentState)->dict:
    """问询：interrupt 挂起提问：resume 后答案进入消息流，回supervisor继续"""
    question=(state.get("last_route") or {}).get("question") or "请补充必要的信息"
    answer=interrupt({"question":question})
    return {
        "messages":[HumanMessage(content=f"[用户回答]:{answer}")]
    }
