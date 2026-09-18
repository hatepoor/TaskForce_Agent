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
from agent.state import AgentState
from agent.subagents.executor import build_executor_graph
from agent.subagents.research import build_research_graph
from agent.subagents.retriever import build_retriever_graph
from agent.supervisor import route_node
from agent.tasks import TaskManager
from settings.config import get_settings


def make_llm(settings=None) -> ChatOpenAI:
    """把 .env 配置装配成 ChatOpenAI(豆包 OpenAI 兼容)。

    extra_body 显式关闭深度思考:seed 系模型默认开思考,首 token 要等想完(~8s);
    关掉后延迟降一个量级。换非思考模型时此参数被忽略,保留无害。
    """
    s = settings or get_settings()
    return ChatOpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        model=s.llm_model,
        temperature=0.7,
        streaming=True,
        max_retries=3,
        timeout=60,
        stream_usage=True,
        extra_body={"thinking": {"type": "disabled"}},
    )


def build_graph(llm, checkpointer=None, tasks=None):
    """CLI 与 API 共用的唯一构建入口;三个子图编译后直挂 add_node。

    异步派发(方案 A):TaskManager 随图构建(测试可注入 fake),supervisor 的
    dispatch 分支提交后台任务、结果经 supervisor 每轮回收注入(主图同步 Send
    通道在 tasks=None 时保留为备胎)。
    """
    b = StateGraph(state_schema=AgentState)
    tasks = tasks or TaskManager(llm)
    b.add_node("supervisor", lambda s, config: route_node(s, llm, tasks=tasks, config=config))
    b.add_node("answer", lambda s: answer_node(s, llm))
    b.add_node("ask", ask_node)
    b.add_node("memory", lambda s: memory_node(s, llm))
    b.add_node("retriever",build_retriever_graph(llm) )
    b.add_node("research", build_research_graph(llm))
    b.add_node("executor", build_executor_graph(llm))

    b.add_edge(START, "supervisor")
    # fan-in:子图完成后回 supervisor 重新路由
    for name in ("retriever", "research", "executor"):
        b.add_edge(name, "supervisor")
    b.add_edge("answer", END)
    b.add_edge("ask", "supervisor")
    b.add_edge("memory", END)

    return b.compile(checkpointer=checkpointer)
