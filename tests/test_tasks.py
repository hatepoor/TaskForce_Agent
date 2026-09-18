"""异步派发 TaskManager 单测(方案 A):提交/回收/异常兜底/懒构建/线程归属,真线程池 + fake llm。"""

import threading
import time

from langchain_core.messages import AIMessage

from agent.contracts import TaskContract
from agent.tasks import TaskManager


class _Llm:
    """fake ChatModel:bind_tools 返回自身,invoke 直接收尾(子图 finalize 不调工具)。"""

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return AIMessage("子图收尾")


def _contract(task="调研 X"):
    return TaskContract(task=task, user_utterance="调研下 X?", input_data={}, output_schema_hint="")


def _drain_wait(tm, timeout=5.0):
    """轮询 drain_done 直到非空(后台线程异步完成,不能假设时序)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = tm.drain_done()
        if out:
            return out
        time.sleep(0.05)
    return []


def _wait_has_done(tm, timeout=5.0):
    """轮询 has_done 直到 True(任务完成标志,REPL 提示的数据源)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if tm.has_done():
            return True
        time.sleep(0.05)
    return False


def _wait_batch_done(tm, thread_id, n, timeout=5.0):
    """轮询 status 直到该线程全批完成(pending 归零且 done 达到 n)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = tm.status(thread_id)
        if st["pending"] == 0 and st["done"] == n:
            return st
        time.sleep(0.05)
    return tm.status(thread_id)


def test_submit_drains_result():
    """提交 research 任务:后台完成,回收得到 research 的 ResultSummary(非 failed)。"""
    tm = TaskManager(_Llm())
    ids = tm.submit([("research", _contract())])
    assert len(ids) == 1
    out = _drain_wait(tm)
    assert len(out) == 1
    assert out[0].agent == "research"
    assert out[0].status != "failed"  # fake 模型无 tool_calls → need_clarification 等正常态


def test_drain_consumes_once():
    """drain 消费即清:第二次 drain 为空,不重复注入。"""
    tm = TaskManager(_Llm())
    tm.submit([("research", _contract())])
    assert _drain_wait(tm)
    assert tm.drain_done() == []


def test_unknown_agent_fails_gracefully():
    """未知子智能体:_run 兜底为 failed 摘要,不炸线程。"""
    tm = TaskManager(_Llm())
    tm.submit([("ghost", _contract())])
    out = _drain_wait(tm)
    assert out and out[0].status == "failed"


def test_has_done_flag():
    """has_done:提交后为 False,完成后 True(只查不消费),drain 消费后置 False。"""
    tm = TaskManager(_Llm())
    assert tm.has_done() is False
    tm.submit([("research", _contract())])
    assert _wait_has_done(tm) is True
    assert tm.has_done() is True  # 只查不消费
    tm.drain_done()
    assert tm.has_done() is False


def test_on_done_callback_fired():
    """on_done 回调:全批完成时被触发(REPL watcher 的唤醒源),异常不外泄。"""
    called = threading.Event()
    tm = TaskManager(_Llm(), on_done=called.set)
    tm.submit([("research", _contract())])
    assert called.wait(timeout=5)  # 完成即触发,不依赖 drain


def test_on_done_fires_once_per_batch():
    """全批触发:一次提交 2 个任务只在全部完成后触发一次(逐个触发会先汇总半批)。"""
    calls: list[int] = []
    lock = threading.Lock()

    def on_done():
        with lock:
            calls.append(1)

    tm = TaskManager(_Llm(), on_done=on_done)
    tm.submit([("retriever", _contract()), ("research", _contract())], thread_id="sess-batch")
    assert _wait_batch_done(tm, "sess-batch", 2)["done"] == 2
    time.sleep(0.1)  # 留出可能的重复触发窗口
    assert len(calls) == 1


def test_status_is_non_consuming():
    """status 是 peek:查多次不消费,结果仍留给后续 drain(Web 轮询靠它,不能被偷走)。"""
    tm = TaskManager(_Llm())
    tm.submit([("research", _contract())], thread_id="sess-p")
    assert _wait_batch_done(tm, "sess-p", 1)["done"] == 1
    assert tm.status("sess-p")["done"] == 1  # 查第二次仍是 1
    assert tm.status("sess-p")["pending"] == 0
    assert len(tm.drain_done("sess-p")) == 1
    assert tm.status("sess-p") == {"pending": 0, "done": 0}


def test_thread_scoped_status_and_drain():
    """线程归属:status/has_done/drain_done 按线程过滤,两个会话的后台结果不互相串。"""
    tm = TaskManager(_Llm())
    tm.submit([("retriever", _contract())], thread_id="sess-a")
    tm.submit([("research", _contract())], thread_id="sess-b")
    _wait_batch_done(tm, "sess-a", 1)
    _wait_batch_done(tm, "sess-b", 1)
    assert tm.status("sess-a") == {"pending": 0, "done": 1}
    assert tm.status("sess-c") == {"pending": 0, "done": 0}  # 没派发过的会话:全零

    out = tm.drain_done("sess-a")
    assert len(out) == 1 and out[0].agent == "retriever"
    assert tm.status("sess-a")["done"] == 0
    assert tm.status("sess-b")["done"] == 1  # B 的结果不被 A 的 drain 带走
    assert tm.has_done("sess-a") is False
    assert tm.has_done("sess-b") is True
    assert tm.has_done() is True  # 无归属查询:看全局


def test_lazy_subgraph_build():
    """懒构建:未 submit 前不装配任何子图(避免无谓 MCP 冷启动);按需只建用到的。"""
    tm = TaskManager(_Llm())
    assert tm._subgraphs == {}
    tm.submit([("retriever", _contract())])
    _drain_wait(tm)
    assert set(tm._subgraphs) == {"retriever"}
