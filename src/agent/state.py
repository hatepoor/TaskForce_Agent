"""主图共享状态 AgentState 与 subagent_results 的 reducer。

本文件作用:
    定义主图三个通道——messages(对话历史,add_messages 合并)、
    last_route(路由决策快照)、subagent_results(子图结果合并,带 RESET 哨兵清空);
    子图经同名共享键直挂读写(ADR-0009 方案 A)。

使用位置:
    - agent/build.py:StateGraph(state_schema=AgentState);
    - agent/supervisor.py / answer.py / service.py:节点读写与类型标注;
    - agent/subagents/stub.py:SubgraphState 与本状态的共享键对齐。
"""
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

RESET="__reset__"

def _add_or_reset(left: list, right: list) -> list:
    """subagent_results 的 reducer:常规增量合并;首元素为哨兵时整体重置。"""
    if right and right[0] == RESET:
        return list(right[1:])
    return (left or []) + (right or [])

class AgentState(TypedDict):
    messages:Annotated[list,add_messages]
    last_route:dict  # 路由决策 model_dump(存 dict 避免 msgpack 自定义类型告警)
    subagent_results:Annotated[list,_add_or_reset]


