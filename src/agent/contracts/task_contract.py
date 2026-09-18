"""任务契约四件套:Send 派发给子图的唯一输入(03 冻结)。

本文件作用:
    定义主图派发任务给子智能体时携带的最小信息包(TaskContract)——
    子智能体只看得到这四样,实现"子智能体独立上下文"(不读主图 messages)。

使用位置:
    - agent/supervisor.py:build_contract() 把路由任务装配成 TaskContract 随 Send 发出;
    - agent/contracts/subgraph.py:SubgraphContract 继承它作为子图边界校验 schema;
    - settings/db/checkpointer.py:_ALLOWED_CONTRACTS(允许从 checkpoint 反序列化)。
"""

from pydantic import BaseModel, Field


class TaskContract(BaseModel):
    """子智能体只看得到这四样,看不到主图 messages。"""

    task: str = Field(
        description="自包含任务描述:目标+输入+输出要求+成功标准"
    )

    user_utterance: str = Field(
        description="用户原话(意图锚点,防重构失真)"
    )

    input_data: dict = Field(
        default_factory=dict,
        description="结构化输入:路径/查询词/候选来源等"
    )

    output_schema_hint: str = Field(
        default="",
        description="结果摘要模板与长度约束提示"
    )
