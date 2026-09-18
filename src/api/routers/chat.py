"""chat 路由:POST /chat(SSE 流式)+ GET /chat/threads(模块 11 T1)。

后台任务闭环(Web 侧):GET /chat/tasks 非消费 peek + POST /chat/summary 自动汇总轮
——前端轮询到全批完成即发起,主智能体主动出汇总,无需用户询问(与 REPL watcher 同语义)。

双入口红线:与 REPL 共用 build_graph/run_turn,本文件不出现第二套实现。

SSE 用同步 generator + def 端点(FastAPI 自动丢线程池,禁 async);真流式(B4):
run_turn 在 worker 线程里同步跑、回调帧投 queue.Queue,generator 从队列逐条
yield(不引入 async):token 增量 / route 轨迹 / interrupt 挂起 / usage 收尾 /
error 异常收尾。图与 checkpointer 惰性单例:首次请求才 build(executor 装配 MCP 较慢),
避免拖慢 uvicorn 启动;lifespan 只预检 DB。
"""

import json
import queue
import threading
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from agent.build import build_graph, make_llm
from agent.service import AUTO_NOTICE, run_turn
from agent.tasks import TaskManager
from settings.config import get_settings
from settings.db.checkpointer import get_checkpointer, list_session_ids, list_session_meta
from settings.usage import UsageTracker

router = APIRouter(prefix="/chat", tags=["chat"])


def _interrupt_envelope(updates) -> dict:
    """把 Interrupt 载荷规范化成自描述信封:两类挂起用统一形状下发。

    question/proposal 是不同 key(ask 与 memory 各写各的),前端只能靠 key
    存在性猜类型,而恢复端点不校验类型,猜错会把 approved=True 当答案写进
    对话(静默污染)。此处补显式 kind,前端按 kind 选恢复端点,不再靠猜。
    """
    first = (updates[0].value if updates else None) or {}
    if "proposal" in first:
        return {"kind": "memory", "text": first["proposal"]}
    if "question" in first:
        return {"kind": "ask", "text": first["question"]}
    return {"kind": "unknown", "text": str(first)}  # 兜底:新挂起类型不静默丢


def _require_interrupt(graph, config, expect: str) -> None:
    """校验挂起存在且类型匹配,不符抛 400:防止把 bool当答案/把文本当审批送进图。"""
    interrupts = getattr(graph.get_state(config), "interrupts", None)
    if not interrupts:
        raise HTTPException(status_code=400, detail="该会话没有待处理的挂起")
    value = (interrupts[0].value if interrupts else None) or {}
    actual = ("memory" if "proposal" in value
                else "ask" if "question" in value
                else "unknown")
    if actual != expect:
        raise HTTPException(
            status_code=400,
            detail=f"挂起类型不匹配:期望 {expect},实际 {actual}",
        )

def _sse_run(graph,config,usage,*,text=None,resume=None)->StreamingResponse:
    """跑一轮 run_turn,事件以 SSE 逐条 yield(B4 真流式)。

    run_turn 是同步阻塞的:直接写进 gen 会"攒完全部帧才吐"(首字节延迟=整轮
    耗时,打字机是快放录像)。此处 worker 线程里跑图、回调帧投 queue.Queue,
    gen 从队列逐条 yield——gen 仍是同步 generator、图仍是同步 graph.stream,
    不引入 async(项目红线)。异常补发 error 帧后正常关流(此前异常直接断连接,
    客户端无法区分"正常结束/崩溃/中止");客户端 abort 后 worker 仍会跑完
    (同步阻塞无法取消),daemon 线程保证不阻塞进程退出,单用户场景可接受。
    """
    def gen():
        q:queue.Queue=queue.Queue()
        _DONE=object()
        streamed = False  # 本轮是否已有 answer/ask 的流式 token(零 token 轮要整段补发)

        def emit(etype:str,data):
            q.put(f"data: {json.dumps({etype: data}, ensure_ascii=False)}\n\n")
        def worker():
            nonlocal streamed
            try:
                def on_token(t: str) -> None:
                    nonlocal streamed
                    streamed = True
                    emit("token", t)

                final=run_turn(
                    graph, config, text=text, resume=resume,
                    on_token=on_token,
                    on_route=lambda r: emit("route", r),
                    on_interrupt=lambda updates: emit("interrupt", _interrupt_envelope(updates)),
                )
                if isinstance(final,AIMessage) and final.additional_kwargs.get("taskforce_error"):
                    # recursion 兜底类错误:走 error 帧(前端区别于正常回答),不计 usage
                    emit("error",
                        {
                                "message": final.content,
                                "code": final.additional_kwargs["taskforce_error"],
                            }
                        )
                elif final is not None and isinstance(final, AIMessage):
                    usage.record(final)
                    if not streamed and (final.content or "").strip():
                        # 零 token 轮的合成消息(派发确认、记忆确认)不经 answer/ask 流:
                        # 不补发的话 Web 侧这一轮只剩"无文本输出"兜底文案
                        emit("token", final.content)
                    emit("usage", {
                        "thread_id": config["configurable"]["thread_id"],
                        "calls": usage.calls,
                        "input_tokens": usage.input_tokens,
                        "output_tokens": usage.output_tokens,
                    })
            except Exception as e: #同步执行，捕获后仍能发帧
                emit(
                    "error",
                    {
                        "message":f"{type(e).__name__}:{e}"
                    }
                )
            finally:
                q.put(_DONE)

        threading.Thread(target=worker, daemon=True).start()
        while (item := q.get()) is not _DONE:
            yield item

    return StreamingResponse(gen(), media_type="text/event-stream")


class ChatRequest(BaseModel):
    thread_id: str = ""  # 空则服务端新建会话
    text: str


_app = None  # (graph, checkpointer, usage, tasks) 惰性单例
_app_lock = threading.Lock()  # B5 双检锁:worker 线程化后快速连点可能并发进入 _get_app


def _get_app():
    """首次调用装配图(挂 checkpointer + 后台任务管理器)+ 用量跟踪,之后复用同一实例。

    TaskManager 由本处显式构造并交给 build_graph:Web 侧的自动汇总要经 /chat/tasks
    问它要状态,不能像 REPL 那样只在图内部持有。
    """
    global _app
    if _app is None:
        with _app_lock:
            if _app is None:
                settings = get_settings()
                checkpointer = get_checkpointer(settings.database_url)
                llm = make_llm(settings)
                tasks = TaskManager(llm)
                graph = build_graph(llm, checkpointer, tasks=tasks)
                _app = (graph, checkpointer, UsageTracker(settings), tasks)
    return _app


@router.post("")
def chat(req: ChatRequest) -> StreamingResponse:
    """SSE 聊天:单轮 run_turn,事件流式返回;interrupt 挂起时发 interrupt 事件。"""
    graph, _checkpointer, usage, _tasks = _get_app()
    thread_id = req.thread_id or f"sess-{uuid.uuid4().hex[:8]}"
    config = {"recursion_limit": 40, "configurable": {"thread_id": thread_id}}
    return _sse_run(graph, config, usage, text=req.text)


@router.get("/tasks")
def task_status(thread_id: str):
    """后台任务 peek(非消费):{pending: 未完成数, done: 已完成未消费数}。

    前端在派发后按此轮询:全批完成(pending==0)且有结果(done>0)时发起
    POST /chat/summary 自动汇总——结果不被本端点消费,仍留给汇总轮 drain。
    """
    _graph, _checkpointer, _usage, tasks = _get_app()
    return tasks.status(thread_id)


@router.get("/threads")
def list_threads():
    """近 N 个会话线程 id(checkpoints 表 DISTINCT,复用 REPL /list_session 的数据源)。"""
    _graph, checkpointer, _usage, _tasks = _get_app()
    return {"threads": list_session_ids(checkpointer)}

@router.get("/threads/meta")
def threads_meta():
    """会话元数据:最近活跃排序 + checkpoint 数。与 /threads/{id}/messages
    的路由次序无关(路径无重叠),但务必放在 /threads 附近,便于阅读。"""
    _graph, checkpointer, _usage, _tasks = _get_app()
    return {"threads": list_session_meta(checkpointer)}

@router.get("/threads/{thread_id}/messages")
def thread_messages(thread_id:str):
    """历史消息回填:读 checkpointer state 的 messages,过滤内部合成消息
    ([用户回答]: / 子智能体结果已回收,过滤规则与 memory 节点 _last_user_text
    同源),附挂起态 pending_interrupt(与 SSE interrupt 信封同形,供前端
    刷新后恢复挂起卡)。ToolMessage/空 content 的 AIMessage 一律跳过。"""
    graph,_checkpointer,_usage,_tasks=_get_app()
    config={
        "configurable":{
            "thread_id":thread_id
        }
    }
    state=graph.get_state(config)
    msgs=(state.values or {}).get("messages") or []
    out=[]
    for m in msgs:
        if isinstance(m,HumanMessage):
            c=m.content or ""
            # 内部合成消息全部过滤:[用户回答] / 子智能体结果已回收 / (系统通知)自动汇总触发语
            if (c.startswith("[用户回答]:") or c.startswith("子智能体结果已回收")
                    or c.startswith("(系统通知)")):
                continue
            out.append({"role": "user", "content": c})
        elif isinstance(m, AIMessage):
            if m.content:
                out.append({"role": "assistant", "content": m.content})

    ints = getattr(state, "interrupts", None) or []
    v = (ints[0].value if ints else None) or {}
    if "proposal" in v:
        pending = {"kind": "memory", "text": v["proposal"]}
    elif "question" in v:
        pending = {"kind": "ask", "text": v["question"]}
    elif v:
        pending = {"kind": "unknown", "text": str(v)}
    else:
        pending = None

    return {
        "thread_id": thread_id,
        "messages": out,
        "pending_interrupt": pending
    }


class ConfirmRequest(BaseModel):
    thread_id: str
    approved: bool


class AnswerRequest(BaseModel):
    thread_id: str
    text: str


class SummaryRequest(BaseModel):
    thread_id: str


@router.post("/summary")
def summary(req: SummaryRequest) -> StreamingResponse:
    """后台任务全批完成后的自动汇总轮(SSE,前端轮询触发,用户无需询问)。

    触发语与 REPL watcher 共用 agent.service.AUTO_NOTICE(双入口同语义);
    结果由 supervisor 在汇总轮里 drain 消费,本端点只负责开这一轮。
    """
    graph, _checkpointer, usage, tasks = _get_app()
    if tasks.status(req.thread_id)["done"] == 0:
        raise HTTPException(status_code=400, detail="该会话没有待汇总的后台任务结果")
    config = {"recursion_limit": 40, "configurable": {"thread_id": req.thread_id}}
    return _sse_run(graph, config, usage, text=AUTO_NOTICE)


@router.post("/confirm")
def confirm(req: ConfirmRequest) -> StreamingResponse:
    """memory 确认挂起恢复:resume=bool,与 REPL /confirm yes|no 同语义。"""
    graph, _checkpointer, usage, _tasks = _get_app()
    config = {"recursion_limit": 40, "configurable": {"thread_id": req.thread_id}}
    _require_interrupt(graph,config,"memory")
    return _sse_run(graph, config, usage, resume=req.approved)


@router.post("/answer")
def answer(req: AnswerRequest) -> StreamingResponse:
    """ask 问询挂起恢复:resume=自由文本,与 REPL 直接回答同语义。"""
    graph, _checkpointer, usage, _tasks = _get_app()
    config = {"recursion_limit": 40, "configurable": {"thread_id": req.thread_id}}
    _require_interrupt(graph,config,"ask")
    return _sse_run(graph, config, usage, resume=req.text)
