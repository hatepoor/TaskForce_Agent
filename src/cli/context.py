"""REPL 共享上下文:命令与主循环共用的依赖容器。

从 repl.py 拆出(原子化):装配一次、全程共享;thread_id 是唯一可变状态
(cmd_new/cmd_resume 修改),graph_config 每轮由当前 thread_id 派生。
"""

from dataclasses import dataclass

from rich.console import Console

from settings.config import Settings
from settings.session import SessionStore
from settings.usage import UsageTracker


@dataclass
class ReplContext:
    """图/checkpointer/会话存储/用量跟踪 + 当前 thread_id。"""

    console: Console
    settings: Settings
    graph: object            # build_graph 编译产物,避免引入 langgraph 类型依赖
    checkpointer: object     # PostgresSaver,另供 /list_session 查询
    sessions: SessionStore
    usage: UsageTracker
    tasks: object = None  # TaskManager(异步派发),REPL 轮询任务完成提示
    thread_id: str = ""

    @property
    def graph_config(self) -> dict:
        """本轮图执行 config:recursion_limit 兜底(ADR-0009)+ 当前会话线程。
        预算:最坏子图 super-steps(executor 12 轮 ×2 + 主图 3 ≈ 27)超过初值 25,
        上调 40;并行 fan-out 取最长分支,不叠加。"""
        return {"recursion_limit": 40, "configurable": {"thread_id": self.thread_id}}
