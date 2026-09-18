"""子图边界输入校验 schema:Send payload 的 contract 经它进入子图共享键(ADR-0009 §4)。

本文件作用:
    SubgraphContract 与 TaskContract 字段一致,语义上专指"子图接收到的输入"——
    子图节点用它做边界校验,后续子图要收额外字段只改这里(父类保持冻结)。

使用位置:
    - agent/subagents/react.py:ReactState.contract 的类型 + agent/finalize 节点校验;
    - agent/subagents/stub.py、agent/subagents/retriever.py:子图边界构造契约。
"""

from agent.contracts.task_contract import TaskContract


class SubgraphContract(TaskContract):
    """与 TaskContract 字段一致,语义上代表"子图接收的输入"。

    build_contract() 产出 TaskContract 后 model_dump() 随 Send 发出,
    到子图边界时以 SubgraphContract 校验;字段一致故校验天然通过。
    后续子图要收额外字段只改这里(TaskContract 保持冻结)。
    """
