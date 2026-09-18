"""桩子图:未落地子智能体(research/executor)的固定占位实现。

本文件作用:
    为尚未开发的子智能体提供最小可用子图——单节点收到任务契约后直接回一条
    "桩"标记的 ResultSummary,让主图的派发/回收/汇总链路可先行跑通;
    真实子图(09 research / 10 executor)落地后在 build.py 里替换挂载。

使用位置:
    - agent/build.py:build_graph() 中 research / executor 两个节点;
    - tests/test_graph.py:桩结果回收与重派防乒乓的测试。
"""
from typing import Literal, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.contracts import ResultSummary, SubgraphContract


class SubgraphState(TypedDict):
    """与主图 AgentState 共享的键:直挂时经同名通道自动读写(ADR-0009 方案 A)。"""
    contract: SubgraphContract
    subagent_results: list

def build_stub_graph(agent: Literal["retriever", "research", "executor"]) -> CompiledStateGraph:
    """返回桩子图:内部 1 个节点,收到契约后回固定 ResultSummary。

    不传 checkpointer(stateless):子图随主图持久化,子图自身不落库(ADR-0009 方案 A)。
    """
    def stub_node(state: SubgraphState)->dict:
        # Send payload 是 dict,到子图边界按 SubgraphContract 校验构造
        contract = SubgraphContract(**state["contract"])
        return {
            "subagent_results": [
                ResultSummary(
                    agent=agent,
                    task_id="stub-1",
                    task=contract.task,
                    status="success",
                    conclusion="(桩)任务已受理,未真实执行;真实能力在对应模块落地。",
                    warnings=["桩子图:未真实执行,结果为固定占位"],
                )
            ]
        }

    g = StateGraph(SubgraphState)
    g.add_node("stub", stub_node)
    g.add_edge(START, "stub")
    return g.compile()
