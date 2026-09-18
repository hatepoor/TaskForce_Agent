"""结构化路由契约:supervisor 的 LLM 输出形状(03 冻结)。

本文件作用:
    定义 supervisor 结构化路由的输出 schema——Route(下一跳决策)与 Task(单条派发任务),
    supervisor 用它做 with_structured_output 的目标类型,强制 LLM 输出可校验的 JSON。

使用位置:
    - agent/supervisor.py:route_node 中 with_structured_output(Route) 解析路由决策;
    - cli/repl.py:_print_route 把 last_route(dict)还原为 Route 打印路由轨迹;
    - settings/db/checkpointer.py:_ALLOWED_CONTRACTS(允许从 checkpoint 反序列化);
    - tests/test_graph.py:路由行为测试。
"""
from typing import Literal

from pydantic import BaseModel, Field


class Task(BaseModel):
    """单条派发任务"""
    agent: Literal["retriever", "research", "executor"]

    task: str = Field(
        description="自包含任务描述:目标+输入+输出要求"
    )
    reason: str = Field(
        description="为何派给该智能体(供 REPL 轨迹显示)"
    )


class Route(BaseModel):
    """supervisor 路由决策。"""

    next: Literal["answer", "ask", "memory", "dispatch"]
    question: str | None = (
        Field(
            default=None,
            description="next=ask时的问询内容"
            )
    )

    tasks: list[Task] | None = (
        Field(
            default=None,
            description="next=dispatch时的任务列表"
            )
    )
