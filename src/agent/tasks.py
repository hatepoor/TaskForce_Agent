"""后台任务管理器(异步派发):dispatch 不再同步 Send,提交线程池跑子图。


- 三个子图是独立编译图,可在后台线程直接 invoke({"contract": ...}),
与主图共用同一 llm(OpenAI client 线程安全);子图实例懒构建,
不派发就不装配(避免 executor 的 MCP 发现冷启动)。
- 后台线程只写进程内任务表,绝不直接写主图 state(checkpointer 线程隔离);
结果由 supervisor 每轮 drain_done() 原子回收注入,answer 消费即清。
- 结果带会话线程归属:submit 时记账,drain/has_done 可按线程过滤(多线程不串)。
- on_done 只在**全批完成**时触发:逐个触发会让 watcher 拿着半批结果先汇总一次
  (3 任务时先汇总 retriever、再汇总 research),语义是"全批完成再汇总"。
- 并发上限 3(与原 max_parallel_subagents 对齐)。
"""
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from agent.contracts import ResultSummary, TaskContract
from agent.subagents.executor import build_executor_graph
from agent.subagents.research import build_research_graph
from agent.subagents.retriever import build_retriever_graph

MAX_WORKERS = 3

_BUILDERS = {
    "retriever": build_retriever_graph,
    "research": build_research_graph,
    "executor": build_executor_graph,
}

class TaskManager:
    """提交后台任务、原子回收结果;主图侧唯一入口,经 supervisor 注入。"""

    def __init__(self, llm, on_done=None):
        self._llm = llm
        self._on_done = on_done  # 全批完成回调(REPL 唤醒 watcher/前端轮询);须快且线程安全
        self._pool = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="task")
        self._subgraphs: dict[str, object] = {}
        self._results: dict[str, tuple[str, ResultSummary]] = {}  # task_id -> (thread_id, 摘要)
        self._pending: dict[str, int] = {}  # thread_id -> 未完成数(全批完成的判据)
        self._lock = threading.Lock()

    def submit(self,jobs:list[tuple[str,TaskContract]],thread_id:str="")->list[str]:
        """jobs: [(agent, 任务契约), ...] -> 返回 task_id 列表(提交即返回,不等待)。

        thread_id 记在每笔结果上,供 drain/has_done/status 按线程过滤;
        计数先整批加上再提交(逐笔加会让后提交的任务完成时把计数减成负数)。
        """
        task_ids = []
        with self._lock:
            self._pending[thread_id] = self._pending.get(thread_id, 0) + len(jobs)
        for agent, contract in jobs:
            task_id = uuid.uuid4().hex[:8]
            task_ids.append(task_id)
            self._pool.submit(self._run, task_id, agent, contract, thread_id)
        return task_ids

    def drain_done(self, thread_id: str | None = None) -> list[ResultSummary]:
        """原子取走全部已完成结果(消费即清,防重复注入)。

        thread_id 为 None 时取全部(无归属场景:单测/备胎);否则只取该线程的。
        """
        with self._lock:
            if thread_id is None:
                out = [s for _, s in self._results.values()]
                self._results.clear()
                return out
            out = []
            for t in [t for t, (tid, _) in self._results.items() if tid == thread_id]:
                out.append(self._results.pop(t)[1])
            return out

    def has_done(self, thread_id: str | None = None)->bool:
        """是否有已完成未消费的结果(REPL 轮询提示用,只查不消费);可按线程过滤。"""
        with self._lock:
            if thread_id is None:
                return bool(self._results)
            return any(tid == thread_id for tid, _ in self._results.values())

    def status(self, thread_id: str) -> dict:
        """非消费 peek:该线程 {pending: 未完成数, done: 已完成未消费数}(Web 轮询用)。

        与 drain_done 的差别是**不消费**:前端据 pending==0 且 done>0 决定发起自动汇总,
        结果仍留给主图在汇总轮里 drain。
        """
        with self._lock:
            done = sum(1 for tid, _ in self._results.values() if tid == thread_id)
            return {"pending": self._pending.get(thread_id, 0), "done": done}

    def _subgraph(self, agent: str):
        """懒构建子图:只装配实际派发过的子智能体。"""
        if agent not in self._subgraphs:
            self._subgraphs[agent] = _BUILDERS[agent](self._llm)
        return self._subgraphs[agent]

    def _run(self,task_id:str,agent:str,contract:TaskContract,thread_id:str="")->None:
        """后台线程执行体:子图 invoke;异常兜底为 failed 摘要,绝不炸线程。

        坑位:ResultSummary.agent 是 Literal(三子图名),unknown agent 直接进
        except 的构造会再次 ValidationError 被线程静默吞掉;故归一 + 截断结论。"""
        print(f"[task] {task_id} {agent} 开始: {contract.task[:40]}", file=sys.stderr)
        try:
            graph = self._subgraph(agent)
            final = graph.invoke({"contract": contract.model_dump()})
            summary = final["subagent_results"][0]
        except Exception as e:
            print(f"[task] {task_id} {agent} 异常: {e}", file=sys.stderr)
            safe_agent = agent if agent in _BUILDERS else "retriever"
            summary = ResultSummary(
                agent=safe_agent, task_id=task_id, task=contract.task,
                status="failed", conclusion=f"后台任务执行失败:{e}"[:100],
                warnings=["后台任务异常,请重试或查看日志"],
            )
        with self._lock:
            self._results[task_id] = (thread_id, summary)
            left = max(0, self._pending.get(thread_id, 0) - 1)
            self._pending[thread_id] = left
        print(f"[task] {task_id} {agent} 完成: {summary.status}", file=sys.stderr)
        # 全批完成才唤醒:半批唤醒会让汇总只覆盖先回来的那部分
        if left == 0 and self._on_done:
            try:
                self._on_done()
            except Exception:
                pass  # 回调失败不影响任务结果;快回调(如 Event.set)不应抛
