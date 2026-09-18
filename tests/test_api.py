"""模块 11 单测:chat SSE + HITL 恢复 + knowledge/memory/skills 路由
(TestClient + 假存储,不连 DB/LLM)。"""

import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

import api.routers.chat as chat_mod
from api.main import app
from settings.usage import UsageTracker


def _fake_run_turn(events: list):
    def run_turn(graph, config, text=None, resume=None,
                 on_token=None, on_route=None, on_interrupt=None):
        events.append((config["configurable"]["thread_id"], text))
        if on_token:
            on_token("你")
            on_token("好")
        if on_route:
            on_route({"next": "answer"})
        return AIMessage(
            content="回复",
            usage_metadata={"input_tokens": 5, "output_tokens": 3, "total_tokens": 8},
        )

    return run_turn


def _setup(monkeypatch, tasks=None):
    """替换 _get_app(返回假 checkpointer/usage/tasks)与 run_turn(脚本化回调)。"""
    tracker = UsageTracker(SimpleNamespace())
    monkeypatch.setattr(
        chat_mod, "_get_app", lambda: (None, None, tracker, tasks or _FakeTasks())
    )
    monkeypatch.setattr(chat_mod, "run_turn", _fake_run_turn([]))
    return tracker


def _payloads(resp) -> list[str]:
    return [
        line.removeprefix("data: ")
        for line in resp.text.split("\n\n")
        if line.startswith("data: ")
    ]


class _FakeTasks:
    """假 TaskManager:status 是 /chat/tasks 与 /chat/summary 守卫唯一读的接口。"""

    def __init__(self, pending=0, done=0):
        self._st = {"pending": pending, "done": done}

    def status(self, thread_id):
        return dict(self._st)


def test_chat_sse_streams_events_in_order(monkeypatch):
    """SSE 事件顺序:token(增量) → route(轨迹) → usage(收尾)。"""
    _setup(monkeypatch)
    client = TestClient(app)  # 不 with:不触发 lifespan,不连 DB
    resp = client.post("/chat", json={"text": "你好"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    payloads = [
        line.removeprefix("data: ")
        for line in resp.text.split("\n\n")
        if line.startswith("data: ")
    ]
    assert '"token"' in payloads[0] and "你" in payloads[0]
    assert '"token"' in payloads[1] and "好" in payloads[1]
    assert '"route"' in payloads[2] and "answer" in payloads[2]
    assert '"usage"' in payloads[3] and '"input_tokens": 5' in payloads[3]


def test_chat_autogenerates_thread_id(monkeypatch):
    """未传 thread_id:服务端生成 sess- 前缀会话,且 usage 事件回显该 id。"""
    _setup(monkeypatch)
    client = TestClient(app)
    resp = client.post("/chat", json={"text": "hi"})
    payloads = [
        line.removeprefix("data: ")
        for line in resp.text.split("\n\n")
        if line.startswith("data: ")
    ]
    usage_ev = next(p for p in payloads if '"usage"' in p)

    tid = json.loads(usage_ev)["usage"]["thread_id"]
    assert tid.startswith("sess-")


def test_chat_interrupt_emits_event(monkeypatch):
    """run_turn 触发 interrupt:on_interrupt 收到挂起值并发出 interrupt 事件,无 usage。"""
    _setup(monkeypatch)

    def interrupt_run(graph, config, text=None, resume=None,
                      on_token=None, on_route=None, on_interrupt=None):
        class _It:
            value = {"question": "要哪一年的?"}
        if on_interrupt:
            on_interrupt([_It()])
        return None

    monkeypatch.setattr(chat_mod, "run_turn", interrupt_run)
    client = TestClient(app)
    resp = client.post("/chat", json={"text": "查数据"})
    payloads = [
        line.removeprefix("data: ")
        for line in resp.text.split("\n\n")
        if line.startswith("data: ")
    ]
    assert '"interrupt"' in payloads[0] and "要哪一年的" in payloads[0]
    assert not any("usage" in p for p in payloads)


# ---------- T2: HITL 恢复端点 ----------

class _FakeGraph:
    """假图:get_state 返回预设挂起快照(B3 后恢复端点校验挂起类型,
    默认 memory 提案挂起——与 /chat/confirm 的期望类型匹配)。"""

    def __init__(self, pending=True):
        self._pending = pending

    def get_state(self, config):
        interrupts = [SimpleNamespace(value={"proposal": "记住这件事"})] if self._pending else []
        return SimpleNamespace(interrupts=interrupts)


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
    tracker = UsageTracker(SimpleNamespace())
    monkeypatch.setattr(
        chat_mod, "_get_app", lambda: (_FakeGraph(pending), None, tracker, _FakeTasks())
    )
    seen = {}
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run(seen))
    return seen


def test_confirm_resumes_boolean(monkeypatch):
    """POST /chat/confirm:approved 透传为 Command(resume=bool),SSE 有 token+usage。"""
    seen = _setup_resume(monkeypatch)
    client = TestClient(app)
    resp = client.post("/chat/confirm", json={"thread_id": "t1", "approved": True})
    assert resp.status_code == 200
    assert seen["resume"] is True and seen["text"] is None
    assert '"token"' in resp.text


def test_confirm_without_pending_rejects(monkeypatch):
    """thread_id 无挂起:confirm 拒绝(400),不会空转 resume。"""
    _setup_resume(monkeypatch, pending=False)
    client = TestClient(app)
    resp = client.post("/chat/confirm", json={"thread_id": "t1", "approved": True})
    assert resp.status_code == 400


def test_answer_resumes_text(monkeypatch):
    """POST /chat/answer:text 透传为 Command(resume=str),SSE 有 token+usage。
    (B3 后恢复端点校验类型,此处用 ask 挂起形状匹配 /chat/answer 的期望。)"""
    tracker = UsageTracker(SimpleNamespace())
    ask_graph = _FakeGraph(pending=True)
    ask_graph.get_state = lambda config: SimpleNamespace(
        interrupts=[SimpleNamespace(value={"question": "?"})]
    )
    monkeypatch.setattr(chat_mod, "_get_app", lambda: (ask_graph, None, tracker, _FakeTasks()))
    seen = {}
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run(seen))
    client = TestClient(app)
    resp = client.post("/chat/answer", json={"thread_id": "t1", "text": "2024 年"})
    assert resp.status_code == 200
    assert seen["resume"] == "2024 年"
    assert '"usage"' in resp.text


def test_answer_type_mismatch_rejected(monkeypatch):
    """B3 新增:ask 挂起(question)误调 /chat/confirm → 400 类型不匹配,
    不再静默把 approved 当答案写进对话。"""
    _setup_resume(monkeypatch)  # 注意:此处假图仍是旧 ask 形状,单独覆写
    tracker = UsageTracker(SimpleNamespace())
    ask_graph = _FakeGraph(pending=True)
    ask_graph.get_state = lambda config: SimpleNamespace(
        interrupts=[SimpleNamespace(value={"question": "?"})]
    )
    monkeypatch.setattr(chat_mod, "_get_app", lambda: (ask_graph, None, tracker, _FakeTasks()))
    client = TestClient(app)
    resp = client.post("/chat/confirm", json={"thread_id": "t1", "approved": True})
    assert resp.status_code == 400
    assert "挂起类型不匹配" in resp.json()["detail"]


# ---------- 异步派发闭环:peek 端点 + 自动汇总轮 ----------

def test_chat_tasks_peek(monkeypatch):
    """GET /chat/tasks:非消费 peek 返回 {pending, done},前端据此决定何时发起汇总。"""
    _setup(monkeypatch, tasks=_FakeTasks(pending=1, done=2))
    client = TestClient(app)
    body = client.get("/chat/tasks", params={"thread_id": "sess-x"}).json()
    assert body == {"pending": 1, "done": 2}


def test_summary_requires_done_results(monkeypatch):
    """POST /chat/summary:没有已完成结果时 400,不空转一轮(前端轮询竞态的兜底)。"""
    _setup(monkeypatch, tasks=_FakeTasks(pending=0, done=0))
    client = TestClient(app)
    resp = client.post("/chat/summary", json={"thread_id": "sess-x"})
    assert resp.status_code == 400


def test_summary_runs_auto_notice_turn(monkeypatch):
    """POST /chat/summary:以 AUTO_NOTICE 触发汇总轮(与 REPL watcher 同一触发语)。"""
    from agent.service import AUTO_NOTICE

    seen = {}
    monkeypatch.setattr(chat_mod, "_get_app", lambda: (
        None, None, UsageTracker(SimpleNamespace()), _FakeTasks(pending=0, done=1),
    ))
    monkeypatch.setattr(chat_mod, "run_turn", _recording_run(seen))
    client = TestClient(app)
    resp = client.post("/chat/summary", json={"thread_id": "sess-x"})
    assert resp.status_code == 200
    assert seen["text"] == AUTO_NOTICE
    assert '"token"' in resp.text and '"usage"' in resp.text


def test_zero_token_turn_emits_final_content(monkeypatch):
    """零 token 轮的合成消息(派发确认)整段补发:否则 Web 侧只剩"无文本输出"兜底文案。"""
    _setup(monkeypatch)

    def run_turn(graph, config, text=None, resume=None,
                 on_token=None, on_route=None, on_interrupt=None):
        if on_route:
            on_route({"next": "dispatch", "question": None, "tasks": []})
        return AIMessage("已派发 2 个后台任务:[research:x1、retriever:x2]。完成后我会自动汇总。")

    monkeypatch.setattr(chat_mod, "run_turn", run_turn)
    client = TestClient(app)
    resp = client.post("/chat", json={"text": "对比一下"})
    payloads = _payloads(resp)
    assert '"route"' in payloads[0]
    assert '"token"' in payloads[1] and "已派发 2 个后台任务" in payloads[1]
    assert '"usage"' in payloads[2]  # usage 仍在最后(前端把用量挂在同一条 AI 项上)


# ---------- T3: knowledge / memory / skills 路由 ----------

class _FakeKB:
    def __init__(self):
        self.uploaded = None
        self.deleted = None

    def list_docs(self):
        return [{"doc_id": "d1", "filename": "a.md", "chunks": 3, "created_at": "2026-09-11 12:00"}]

    def upload(self, path, name):
        self.uploaded = (str(path), name)
        return ("d1", True)

    def delete(self, doc_id):
        self.deleted = doc_id


class _FakeMemoryStore:
    def __init__(self):
        self.deleted = None

    def search(self, ns, query=None, limit=100):
        return [
            SimpleNamespace(
                key="k1",
                value={"content": "用户偏好 X", "source": "user", "created_at": "2026-09-11 10:00"},
            )
        ]

    def delete(self, ns, key):
        self.deleted = key


def test_knowledge_list_upload_delete(monkeypatch):
    """GET/POST/DELETE /knowledge 复用 RAGStore;multipart 上传返回 doc_id/created。"""
    import api.routers.knowledge as kb

    fake = _FakeKB()
    monkeypatch.setattr(kb, "RAGStore", lambda: fake)
    client = TestClient(app)
    assert client.get("/knowledge").json()["docs"][0]["doc_id"] == "d1"
    r = client.post(
        "/knowledge/upload",
        files={"file": ("note.md", "# 笔记内容".encode(), "text/markdown")},
    )
    assert r.status_code == 200
    assert r.json()["doc_id"] == "d1" and r.json()["created"] is True
    assert fake.uploaded[1] == "note.md"
    assert client.delete("/knowledge/d1").status_code == 200
    assert fake.deleted == "d1"


def test_knowledge_upload_too_large_rejects(monkeypatch):
    """超过 20MB 上传上限:400 拒绝,不写临时文件不触库。"""
    import api.routers.knowledge as kb

    monkeypatch.setattr(kb, "RAGStore", lambda: _FakeKB())
    client = TestClient(app)
    r = client.post(
        "/knowledge/upload",
        files={"file": ("big.md", b"x" * (kb.MAX_UPLOAD_BYTES + 1), "text/markdown")},
    )
    assert r.status_code == 400


def test_memory_list_delete(monkeypatch):
    """GET/DELETE /memory 复用 PostgresStore(namespace memory/default)。"""
    import api.routers.memory as mem

    fake = _FakeMemoryStore()
    monkeypatch.setattr(mem, "get_store", lambda url: fake)
    client = TestClient(app)
    items = client.get("/memory").json()["items"]
    assert items[0]["key"] == "k1" and items[0]["content"] == "用户偏好 X"
    assert client.delete("/memory/k1").status_code == 200
    assert fake.deleted == "k1"


def test_skills_list(monkeypatch):
    """GET /skills 返回结构化元数据(SkillRegistry.list_metadata)。"""
    import api.routers.skills as sk

    monkeypatch.setattr(
        sk.SkillRegistry, "list_metadata",
        lambda self: [{"name": "hello-world", "description": "示例技能"}],
    )
    client = TestClient(app)
    body = client.get("/skills").json()
    assert body["skills"][0]["name"] == "hello-world"


# ---------- T3: mcp / health 路由 ----------

class _FakeProvider:
    """假 MCPToolProvider:list_tools 返回预设索引(空=不可达)。"""

    def __init__(self, found):
        self._found = found

    def list_tools(self):
        return self._found


def test_mcp_servers_crud_and_test(monkeypatch):
    """GET/POST/DELETE /mcp/servers + /test 复用 08 config/client。"""
    import api.routers.mcp as mc
    from tools.mcp.config import MCPConfig, StdioServer

    server = StdioServer(command="echo", args=[])
    monkeypatch.setattr(mc, "load_mcp_config", lambda: MCPConfig(servers={"a": server}))
    client = TestClient(app)
    # list
    body = client.get("/mcp/servers").json()
    assert body["servers"]["a"]["command"] == "echo"
    # create:config 经 transport 判别解析为 StdioServer
    added = {}
    monkeypatch.setattr(
        mc, "add_server",
        lambda name, s, path=None: added.update(name=name, server=s),
    )
    r = client.post("/mcp/servers?name=b", json={"transport": "stdio", "command": "uvx"})
    assert r.status_code == 200
    assert added["name"] == "b" and added["server"].transport == "stdio"
    # delete
    removed = {}
    monkeypatch.setattr(
        mc, "remove_server",
        lambda name, path=None: removed.update(name=name) or True,
    )
    assert client.delete("/mcp/servers/a").json()["ok"] is True
    assert removed["name"] == "a"
    # test:发现工具即通
    monkeypatch.setattr(
        mc, "MCPToolProvider",
        lambda config=None, timeout=10: _FakeProvider(
            [{"server": "a", "name": "t1", "short_desc": "x"}]
        ),
    )
    assert client.post("/mcp/servers/a/test").json()["ok"] is True


def test_mcp_test_unreachable_returns_false(monkeypatch):
    """单服务器连不上:list_tools 返回空 → ok=False(不抛,复用降级契约)。"""
    import api.routers.mcp as mc
    from tools.mcp.config import MCPConfig, StdioServer

    monkeypatch.setattr(
        mc, "load_mcp_config", lambda: MCPConfig(servers={"a": StdioServer(command="x")})
    )
    monkeypatch.setattr(mc, "MCPToolProvider", lambda config=None, timeout=10: _FakeProvider([]))
    r = TestClient(app).post("/mcp/servers/a/test")
    assert r.json()["ok"] is False


def test_mcp_delete_missing_404(monkeypatch):
    import api.routers.mcp as mc

    monkeypatch.setattr(mc, "remove_server", lambda name, path=None: False)
    assert TestClient(app).delete("/mcp/servers/nope").status_code == 404


def test_health_db_and_sandbox(monkeypatch):
    """GET /health:DB/沙箱均正常时 status=ok,sandbox=ok(真实沙箱 /health 返回 {"status": "ok"})。"""
    import api.routers.health as h

    monkeypatch.setattr(h, "get_checkpointer", lambda url: None)
    monkeypatch.setattr(h, "sandbox_health", lambda: {"status": "ok"})
    body = TestClient(app).get("/health").json()
    assert body["status"] == "ok" and body["db"] == "ok" and body["sandbox"] == "ok"


def test_health_sandbox_error_no_degrade(monkeypatch):
    """GET /health:sandbox 异常透传 error 文本,status 不降级(契约 §2.2:status 只随 DB 降级)。"""
    import api.routers.health as h

    monkeypatch.setattr(h, "get_checkpointer", lambda url: None)
    monkeypatch.setattr(
        h, "sandbox_health", lambda: {"ok": False, "error": "沙箱不可达:ConnectError"}
    )
    body = TestClient(app).get("/health").json()
    assert body["status"] == "ok" and body["db"] == "ok"
    assert body["sandbox"] == "沙箱不可达:ConnectError"
