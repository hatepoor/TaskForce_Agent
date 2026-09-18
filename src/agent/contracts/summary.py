"""结果摘要契约:子智能体回传给主图的唯一结构化输出(03 冻结)。

本文件作用:
    定义 ResultSummary——子图 finalize 节点把执行结果收敛成的定长摘要,
    supervisor/answer 按字段决策,而不是解析长文本。

使用位置:
    - agent/subagents/react.py / retriever.py / stub.py:finalize 收尾时构造;
    - agent/answer.py:_render_results 渲染成文本注入 answer 节点;
    - agent/state.py:subagent_results 通道里存的就是本类型;
    - settings/db/checkpointer.py:_ALLOWED_CONTRACTS(允许从 checkpoint 反序列化)。
"""
from typing import Literal

from pydantic import BaseModel, Field


class ResultSummary(BaseModel):
    """定长约束让 supervisor 按字段决策,而非解析长文本。"""

    agent: Literal["retriever", "research", "executor"]
    task_id: str = Field(
        description="派发时分配的唯一 id"
    )
    task: str = Field(
        description="任务描述回显(supervisor 生成的 task 长度不可控,不设上限,"
        "否则超长任务在子图边界触发 ValidationError 崩掉整轮)"
    )

    status: Literal["success", "partial", "need_clarification", "failed"]

    conclusion: str = Field(
        max_length=100,
        description="一句话直接结论"
    )

    key_points: list[str] = Field(
        default_factory=list,
        description="要点,≤5 条"
    )

    data: dict = Field(
        default_factory=dict,
        description="各智能体约定的结构化数据"
    )

    sources: list[str] = Field(
        default_factory=list,
        description="id/url,≤10 条"
    )

    needs_clarification: list[str] = Field(
        default_factory=list,
        description="缺失项"
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="副作用与风险提示"
    )
