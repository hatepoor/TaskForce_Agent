"""B1 历史消息回填端点单测(TestClient + 假图快照,不连 DB/LLM)。

对应 dev/front/docs/01-后端契约改造/task1:
- 正常回填:user/assistant 序列 + thread_id 回显
- 内部合成消息过滤:[用户回答]: / 子智能体结果已回收 / ToolMessage / 空 content
- 挂起态 pending_interrupt 与 SSE interrupt 信封同形(ask/memory/unknown/无)
"""

import json
import threading
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import api.routers.chat as chat_mod
from api.main import app
from settings.usage import UsageTracker


class _FakeGraph:
    """假图:get_state 返回预设快照(values.messages + interrupts)。"""

    def __init__(self, values=None, interrupts=None):
        self._values = values if values is not None else {"messages": []}
        self._interrupts = interrupts or []

    def get_state(self, config):
        return SimpleNamespace(values=self._values, interrupts=self._interrupts)


def _setup(monkeypatch, values=None, interrupts=None):
    monkeypatch.setattr(
        chat_mod, "_get_app", lambda: (_FakeGraph(values, interrupts), None, None, None)
    )
    return TestClient(app)  # 不 with:不触发 lifespan,不连 DB


def test_history_returns_user_assistant_sequence(monkeypatch):
    """两轮真实对话:user/assistant 交替,顺序与 content 原样,thread_id 回显。"""
    values = {
        "messages": [
            HumanMessage(content="帮我对比 pgvector 和 FAISS"),
            AIMessage(content="两款都是向量检索方案…"),
            HumanMessage(content="重点看运维成本"),
            AIMessage(content="pgvector 复用现有实例…"),
        ]
    }
    client = _setup(monkeypatch, values=values)
    body = client.get("/chat/threads/sess-a1b2c3d4/messages").json()
    assert body["thread_id"] == "sess-a1b2c3d4"
    assert body["pending_interrupt"] is None
    assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user", "assistant"]
    assert body["messages"][0]["content"] == "帮我对比 pgvector 和 FAISS"


def test_history_filters_internal_messages(monkeypatch):
    """过滤四类非真实对话:ask 合成回复 / fan-in 合成消息 / 自动汇总触发语 / ToolMessage + 空 AI。"""
    values = {
        "messages": [
            HumanMessage(content="查一下 HNSW 参数"),
            AIMessage(content=""),
            ToolMessage(content='{"hits": []}', tool_call_id="tc1"),
            AIMessage(content="知识库里暂时没有…"),
            HumanMessage(content="[用户回答]:2024 年"),
            HumanMessage(content="子智能体结果已回收:\n- retriever: ..."),
            AIMessage(content="综合来看 HNSW 默认 m=16…"),
            HumanMessage(content="(系统通知)后台子智能体任务已完成,请直接汇总结果。"),
            AIMessage(content="三个后台任务已汇总如下…"),
        ]
    }
    client = _setup(monkeypatch, values=values)
    body = client.get("/chat/threads/sess-x/messages").json()
    contents = [m["content"] for m in body["messages"]]
    assert contents == [
        "查一下 HNSW 参数", "知识库里暂时没有…", "综合来看 HNSW 默认 m=16…",
        "三个后台任务已汇总如下…",
    ]
    assert all(m["role"] in ("user", "assistant") for m in body["messages"])


def test_history_pending_interrupt_ask(monkeypatch):
    """ask 挂起:pending_interrupt 与 SSE 信封同形 {kind:"ask", text}。"""
    ints = [SimpleNamespace(value={"question": "要哪一年的数据?"})]
    client = _setup(
        monkeypatch,
        values={"messages": [HumanMessage(content="查数据")]},
        interrupts=ints,
    )
    body = client.get("/chat/threads/sess-x/messages").json()
    assert body["pending_interrupt"] == {"kind": "ask", "text": "要哪一年的数据?"}


def test_history_pending_interrupt_memory(monkeypatch):
    """memory 挂起:信封 {kind:"memory", text=proposal 原文}。"""
    ints = [SimpleNamespace(value={"proposal": "用户偏好用 uv"})]
    client = _setup(monkeypatch, interrupts=ints)
    body = client.get("/chat/threads/sess-x/messages").json()
    assert body["pending_interrupt"] == {"kind": "memory", "text": "用户偏好用 uv"}


def test_history_pending_interrupt_unknown_and_empty_history(monkeypatch):
    """未知挂起 value → unknown 兜底;空线程 → 消息为空 + pending 为 null。"""
    client = _setup(monkeypatch, interrupts=[SimpleNamespace(value={"foo": 1})])
    body = client.get("/chat/threads/sess-x/messages").json()
    assert body["pending_interrupt"]["kind"] == "unknown"

    client2 = _setup(monkeypatch)
    body2 = client2.get("/chat/threads/sess-empty/messages").json()
    assert body2["messages"] == [] and body2["pending_interrupt"] is None


# ---------- B2: 会话元数据端点 ----------

class _FakeConnCtx:
    """模拟 `with saver.conn.connection() as conn` 的上下文管理器。"""

    def __init__(self, conn):
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc):
        return False


class _FakeSaver:
    """假 saver:conn.connection() 返回假连接,execute 返回预设行
    (沿用 list_session_ids 直查裸 SQL 的调用形状,不连真库)。"""

    def __init__(self, rows):
        self._rows = rows
        self.conn = SimpleNamespace(
            connection=lambda: _FakeConnCtx(
                SimpleNamespace(
                    execute=lambda sql, params=(): SimpleNamespace(
                        fetchall=lambda: self._rows
                    )
                )
            )
        )


def test_threads_meta_orders_by_last_checkpoint(monkeypatch):
    """GET /chat/threads/meta:按 max(checkpoint_id) 降序,形状含三字段。"""
    import api.routers.chat as chat_mod

    rows = [
        ("sess-b", "1ef9-aaa", 3),
        ("sess-a", "1ef7-bbb", 7),
    ]
    fake_saver = _FakeSaver(rows)
    monkeypatch.setattr(
        chat_mod, "_get_app", lambda: (None, fake_saver, None, None)
    )
    client = TestClient(app)
    body = client.get("/chat/threads/meta").json()
    assert body["threads"] == [
        {"thread_id": "sess-b", "last_checkpoint": "1ef9-aaa", "checkpoints": 3},
        {"thread_id": "sess-a", "last_checkpoint": "1ef7-bbb", "checkpoints": 7},
    ]


def test_list_session_meta_builds_expected_sql(monkeypatch):
    """list_session_meta 直查:SQL 含 sess- 过滤/GROUP BY/降序/LIMIT 参数。"""
    from settings.db.checkpointer import list_session_meta

    captured = {}

    def fake_execute(sql, params=()):
        captured["sql"] = sql
        captured["params"] = params
        return SimpleNamespace(fetchall=lambda: [])

    fake_conn = SimpleNamespace(execute=fake_execute)
    fake_saver = SimpleNamespace(
        conn=SimpleNamespace(connection=lambda: _FakeConnCtx(fake_conn))
    )
    out = list_session_meta(fake_saver, limit=10)
    assert out == []
    assert "LIKE 'sess-%%'" in captured["sql"]  # 带参查询:字面 % 必须写 %% 才过 psycopg 解析
    assert "GROUP BY thread_id" in captured["sql"]
    assert "ORDER BY last_cp DESC" in captured["sql"]
    assert captured["params"] == (10,)


# ---------- B3: interrupt 信封 + 恢复端点类型校验 ----------

def _it(value):
    """构造假 Interrupt(SimpleNamespace,与 test_api.py 的 _It 同法)。"""
    return SimpleNamespace(value=value)


def _sse_payloads(resp):
    """从 SSE 响应文本提取 data 载荷行列表(供信封测试断言)。"""
    return [
        line.removeprefix("data: ")
        for line in resp.text.split("\n\n")
        if line.startswith("data: ")
    ]


def test_sse_interrupt_envelope_ask(monkeypatch):
    """SSE interrupt 帧:ask 挂起 → {kind:"ask", text} 对象信封(非数组)。"""
    _setup(monkeypatch)

    def interrupt_run(graph, config, text=None, resume=None,
                      on_token=None, on_route=None, on_interrupt=None):
        if on_interrupt:
            on_interrupt([_it({"question": "要哪一年的?"})])
        return None

    monkeypatch.setattr(chat_mod, "run_turn", interrupt_run)
    client = TestClient(app)
    resp = client.post("/chat", json={"text": "查数据"})
    payloads = _sse_payloads(resp)
    ev = json.loads(payloads[0])["interrupt"]
    assert ev == {"kind": "ask", "text": "要哪一年的?"}


def test_sse_interrupt_envelope_memory(monkeypatch):
    """SSE interrupt 帧:memory 挂起 → {kind:"memory", text}。"""
    _setup(monkeypatch)

    def interrupt_run(graph, config, text=None, resume=None,
                      on_token=None, on_route=None, on_interrupt=None):
        if on_interrupt:
            on_interrupt([_it({"proposal": "用户偏好用 uv"})])
        return None

    monkeypatch.setattr(chat_mod, "run_turn", interrupt_run)
    client = TestClient(app)
    resp = client.post("/chat", json={"text": "记住我喜欢 uv"})
    ev = json.loads(next(p for p in _sse_payloads(resp) if "interrupt" in p))["interrupt"]
    assert ev == {"kind": "memory", "text": "用户偏好用 uv"}


def test_sse_interrupt_envelope_unknown(monkeypatch):
    """SSE interrupt 帧:未知挂起 value → unknown 兜底,不静默丢。"""
    _setup(monkeypatch)

    def interrupt_run(graph, config, text=None, resume=None,
                      on_token=None, on_route=None, on_interrupt=None):
        if on_interrupt:
            on_interrupt([_it({"mystery": 1})])
        return None

    monkeypatch.setattr(chat_mod, "run_turn", interrupt_run)
    resp = TestClient(app).post("/chat", json={"text": "x"})
    ev = json.loads(next(p for p in _sse_payloads(resp) if "interrupt" in p))["interrupt"]
    assert ev["kind"] == "unknown"


def _recording_run(seen):
    """假 run_turn:记录 text/resume 透传,并驱动 token 回调(供 SSE 断言)。"""

    def run_turn(graph, config, text=None, resume=None,
                 on_token=None, on_route=None, on_interrupt=None):
        seen["text"] = text
        seen["resume"] = resume
        if on_token:
            on_token("OK")
        return AIMessage(
            content="好", usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}
        )

    return run_turn


def _setup_resume(monkeypatch, pending=True):
    """挂起恢复端点的公共脚手架:假图(ask 挂起)+ 假 usage + 记录型 run_turn。"""
    tracker = UsageTracker(SimpleNamespace())
    graph = (_FakeGraph(interrupts=[_it({"question": "?"})]) if pending
             else _FakeGraph())
    monkeypatch.setattr(chat_mod, "_get_app", lambda: (graph, None, tracker, None))
    seen = {}
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run(seen))
    return seen


def test_confirm_type_mismatch_rejected(monkeypatch):
    """ask 挂起误调 /chat/confirm:400 类型不匹配,不再静默把 bool 当答案。"""
    _setup_resume(monkeypatch)  # 假图挂起 value={"question": "?"}

    def spy_run(graph, config, text=None, resume=None,
                on_token=None, on_route=None, on_interrupt=None):
        raise AssertionError("类型不匹配时不应执行 run_turn")

    monkeypatch.setattr(chat_mod, "run_turn", spy_run)
    client = TestClient(app)
    resp = client.post("/chat/confirm", json={"thread_id": "t1", "approved": True})
    assert resp.status_code == 400
    assert "挂起类型不匹配" in resp.json()["detail"]
    assert "ask" in resp.json()["detail"]


def _memory_pending_graph():
    """构造 memory 挂起的假图(本文件 _FakeGraph 签名是 values/interrupts)。"""
    return _FakeGraph(interrupts=[_it({"proposal": "记住这件事"})])


def test_answer_type_mismatch_rejected(monkeypatch):
    """memory 挂起误调 /chat/answer:400 类型不匹配。"""
    tracker = UsageTracker(SimpleNamespace())
    memory_graph = _memory_pending_graph()
    monkeypatch.setattr(chat_mod, "_get_app", lambda: (memory_graph, None, tracker, None))
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run({}))
    client = TestClient(app)
    resp = client.post("/chat/answer", json={"thread_id": "t1", "text": "好的"})
    assert resp.status_code == 400
    assert "memory" in resp.json()["detail"]


def test_confirm_and_answer_type_match_pass(monkeypatch):
    """类型匹配的正路径:confirm(memory 挂起)与 answer(ask 挂起)均 200 透传。"""
    # memory 挂起 → confirm 通过
    tracker = UsageTracker(SimpleNamespace())
    memory_graph = _memory_pending_graph()
    seen_confirm = {}
    monkeypatch.setattr(chat_mod, "_get_app", lambda: (memory_graph, None, tracker, None))
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run(seen_confirm))
    resp = TestClient(app).post("/chat/confirm", json={"thread_id": "t1", "approved": True})
    assert resp.status_code == 200 and seen_confirm["resume"] is True

    # ask 挂起 → answer 通过
    seen_answer = {}
    monkeypatch.setattr(
        chat_mod, "_get_app",
        lambda: (_FakeGraph(interrupts=[_it({"question": "?"})]), None, tracker, None),
    )
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run(seen_answer))
    resp = TestClient(app).post("/chat/answer", json={"thread_id": "t1", "text": "2024"})
    assert resp.status_code == 200 and seen_answer["resume"] == "2024"


# ---------- B4: SSE 真流式 + error 帧 ----------

def test_sse_error_frame_on_exception(monkeypatch):
    """worker 内异常(B4):补发 error 帧后正常关流,不再直接断连接;无 usage。"""
    _setup(monkeypatch)

    def boom_run(graph, config, text=None, resume=None,
                 on_token=None, on_route=None, on_interrupt=None):
        raise RuntimeError("模型服务不可用")

    monkeypatch.setattr(chat_mod, "run_turn", boom_run)
    resp = TestClient(app).post("/chat", json={"text": "你好"})
    assert resp.status_code == 200
    payloads = _sse_payloads(resp)
    ev = json.loads(payloads[0])["error"]
    assert "RuntimeError" in ev["message"] and "模型服务不可用" in ev["message"]
    assert not any('"usage"' in p for p in payloads)


def test_sse_error_frame_on_recursion_marker(monkeypatch):
    """recursion 兜底(B4):service 打 taskforce_error 标记 → error 帧带 code,无 usage。"""
    _setup(monkeypatch)

    def recursion_run(graph, config, text=None, resume=None,
                      on_token=None, on_route=None, on_interrupt=None):
        return AIMessage(
            content="本轮任务循环过深,已中止。请把需求拆小一点再试。",
            additional_kwargs={"taskforce_error": "recursion_limit"},
        )

    monkeypatch.setattr(chat_mod, "run_turn", recursion_run)
    resp = TestClient(app).post("/chat", json={"text": "x"})
    payloads = _sse_payloads(resp)
    ev = json.loads(next(p for p in payloads if '"error"' in p))["error"]
    assert ev["code"] == "recursion_limit"
    assert "循环过深" in ev["message"]
    assert not any('"usage"' in p for p in payloads)


# ---------- B5: 并发与锁 ----------

def test_chat_module_singletons_initialized():
    """模块装配卫生(B5):_app 惰性单例初始为 None、_app_lock 存在。

    常规用例全部 monkeypatch _get_app,模块级变量接线漂移(app/漏写/改名)
    在单测里完全不可见,此守卫直接断言模块顶层两个符号的真实存在。
    """
    assert chat_mod._app is None
    assert chat_mod._app_lock is not None


def test_usage_tracker_thread_safe_record():
    """B5:多线程并发 record 不丢计数(SSE worker 线程化后的共享单例保护)。"""
    tracker = UsageTracker(SimpleNamespace())
    msg = AIMessage(
        content="x",
        usage_metadata={"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    )

    def hammer():
        for _ in range(1000):
            tracker.record(msg)

    threads = [threading.Thread(target=hammer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert tracker.calls == 8000
    assert tracker.input_tokens == 8000 and tracker.output_tokens == 16000
