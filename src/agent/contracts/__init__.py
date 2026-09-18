"""共享契约对外唯一定处:其他包一律 from agent.contracts import ...

本文件作用:
    契约包的统一出口,把四个契约 schema 聚合到包顶层,收敛 import 路径
    (契约代码本体在 route.py / task_contract.py / summary.py / subgraph.py)。

使用位置:
    - agent/(supervisor/build/answer/state)、agent/subagents/*、cli/repl.py、tests/*
      均从本文件 import Route / Task / TaskContract / ResultSummary / SubgraphContract。
"""

from agent.contracts.route import Route, Task
from agent.contracts.subgraph import SubgraphContract
from agent.contracts.summary import ResultSummary
from agent.contracts.task_contract import TaskContract

__all__ = ["Route", "Task", "TaskContract", "ResultSummary", "SubgraphContract"]
