"""主图装配:LLM 构造 + 六节点 StateGraph 的唯一定义(双入口共用)。

本文件作用:
    build_graph() 是 CLI REPL 与 FastAPI 共用的唯一构建入口——把
    supervisor/answer/ask/memory 四个主图节点与 retriever/research/executor
    三个子图包装节点接上边并编译;make_llm() 把 .env 配置装配成 ChatOpenAI。

使用位置:
    - cli/repl.py:main() 中 make_llm + build_graph(挂 checkpointer);
    - api/(06 模块):同一 build_graph,不允许第二套实现;
    - tests/test_graph.py:图结构与路由测试。
"""
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from agent.answer import answer_node
from agent.ask import ask_node
from agent.memory import memory_node
from agent.planner import plan_confirm_node, plan_draft_node
from agent.state import AgentState
from agent.subagents.registry import get_subgraph
from agent.supervisor import route_node
from agent.tasks import TaskManager
from settings.config import get_settings


def make_llm(settings=None, thinking: str | None = None) -> ChatOpenAI:
    """把 .env 配置装配成 ChatOpenAI(豆包 OpenAI 兼容)。

    thinking:adaptive / enabled / disabled,None 时读 settings.llm_thinking。
    supervisor 路由与 planner 计划生成固定传 "disabled"——两者都用
    with_structured_output(强制 tool_choice),DeepSeek 思考模式不支持该组合
    (底层 400);reasoning_effort 仅在思考模式下携带。
    换非豆包/非 DeepSeek 模型时 extra_body 被忽略,保留无害。
    """
    s = settings or get_settings()
    thinkingMode = thinking or s.llm_thinking
    extraBody = {"thinking": {"type": thinkingMode}}
    if thinkingMode != "disabled":
        extraBody["reasoning_effort"] = "high"
    return ChatOpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        model=s.llm_model,
        temperature=0.7,
        streaming=True,
        max_retries=3,
        timeout=60,
        stream_usage=True,
        extra_body=extraBody,
    )


def build_graph(llm, checkpointer=None, tasks=None, routeLlm=None):
    """CLI 与 API 共用的唯一构建入口;三个子图经共享注册表装配后直挂 add_node
    (c7:与 TaskManager 后台 invoke 取同一批编译实例,不再双份装配)。

    routeLlm:supervisor 路由 + planner 计划生成专用 LLM,缺省复用 llm;
    生产入口应传 thinking=disabled 的实例——两者都强制 tool_choice,
    DeepSeek 思考模式会 400(见 make_llm)。

    异步派发(方案 A):TaskManager 随图构建(测试可注入 fake),supervisor 的
    dispatch 分支提交后台任务、结果经 supervisor 每轮回收注入(主图同步 Send
    通道保留为备胎,ADR-0009 双通道语义不变)。
    """
    b = StateGraph(state_schema=AgentState)
    tasks = tasks or TaskManager(llm)
    routeLlm = routeLlm or llm
    b.add_node("supervisor", lambda s, config: route_node(s, routeLlm, tasks=tasks, config=config))
    b.add_node("answer", lambda s: answer_node(s, llm))
    b.add_node("ask", ask_node)
    b.add_node("memory", lambda s: memory_node(s, llm))
    b.add_node("retriever", get_subgraph(llm, "retriever"))
    b.add_node("research", get_subgraph(llm, "research"))
    b.add_node("executor", get_subgraph(llm, "executor"))
    b.add_node("plan_draft", lambda s: plan_draft_node(s, routeLlm))
    b.add_node("plan_confirm", lambda s, config: plan_confirm_node(s, tasks, config=config))
    b.add_edge(START, "supervisor")
    # fan-in:子图完成后回 supervisor 重新路由
    for name in ("retriever", "research", "executor"):
        b.add_edge(name, "supervisor")
    b.add_edge("answer", END)
    b.add_edge("ask", "supervisor")
    b.add_edge("memory", END)
    b.add_edge(START, "supervisor")
    # plan_draft / plan_confirm 都用 Command(goto=...) 显式路由(成功去确认、
    # 失败回 answer),不能再加 plan_draft->plan_confirm 静态边:静态边优先,
    # planner 回退时也会被拉进 plan_confirm,state 无 plan 直接 KeyError。
    return b.compile(checkpointer=checkpointer)
