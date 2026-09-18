"""执行子智能体(模块 09):ReAct 循环 + 沙箱执行/文件工具/Skill 全文/MCP 工具。

工具三层来源装配(CLAUDE.md 架构):tools/tool(内置文件工具,操作沙箱工作区)
+ tools/skills(load_skill 按需读全文)+ tools/mcp(get_tool_detail 查 schema、
MCP 工具直连);执行一律经 execute_python 走远程沙箱(ADR-0007)。

T3 收尾纪律:ResultSummary.warnings 强制列执行侧效应(写了哪些文件/跑了几段代码),
从消息历史中 AIMessage.tool_calls 收集,不依赖模型自报。

使用位置:
    - agent/build.py:build_graph() 中 build_executor_graph(llm) 直挂 executor 节点;
    - tests/test_executor.py:fake model 循环行为测试。
"""

import json
import sys
import uuid

from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph.state import CompiledStateGraph

from agent.contracts import ResultSummary, SubgraphContract
from agent.subagents.react import ReactState, build_react_subgraph, extract_answer
from settings.loader import load_prompt
from tools.mcp.client import MCPToolProvider
from tools.sandbox.client import execute_python as _execute_python
from tools.skills.loader import SkillRegistry
from tools.tool.files import list_files, read_file, write_file

MAX_ITERATIONS = 12  # 工具调执行轮数上限


@tool
def execute_python(code: str, timeout: int = 60) -> str:
    """在远程沙箱执行 Python 代码。返回 stdout/stderr/exit_code;stdout 超 10k 字符会被截断。"""
    return str(_execute_python(code, timeout=timeout))


@tool
def load_skill(name: str) -> str:
    """按名加载 Skill 全文(完整执行指令)。任务要求按某 Skill 执行时,先调用它读全文。"""
    try:
        return SkillRegistry().load_skill(name)
    except Exception as e:
        return f"加载失败:{e}"


@tool
def get_tool_detail(name: str) -> str:
    """查看 MCP 工具的完整参数 schema。不确定 MCP 工具参数怎么传时先查。"""
    try:
        return json.dumps(MCPToolProvider().get_tool_detail(name), ensure_ascii=False)
    except Exception as e:
        return f"查询失败:{e}"


def _gather_tools() -> list:
    """装配工具集:内置 + 元工具 + MCP(发现失败降级为空,不阻塞装配;重名加前缀)。"""
    base = [read_file, write_file, list_files, execute_python, load_skill, get_tool_detail]
    out = list(base)
    names = {t.name for t in out}
    try:
        provider = MCPToolProvider()
        index = provider.list_tools()  # 连接发现;单服务器失败已降级告警
        for t in provider.get_langchain_tools([i["name"] for i in index]):
            if t.name in names:  # MCP 工具与内置重名:加前缀(09-DEV 坑表)
                t = t.model_copy(update={"name": f"mcp__{t.name}"})
                names.add(t.name)
            out.append(t)
    except Exception as e:
        print(f"[executor] MCP 工具装配失败,仅用内置工具:{e}", file=sys.stderr)
    return out


def _collect_effects(messages: list) -> list[str]:
    """从 AIMessage.tool_calls 统计执行侧效应(T3:warnings 强制列,不依赖模型自报)。"""
    files_written: list[str] = []
    code_runs = 0
    for m in messages:
        if not isinstance(m, AIMessage):
            continue
        for call in m.tool_calls or []:
            if call["name"] == "write_file":
                files_written.append(str(call["args"].get("filename", "?")))
            elif call["name"] == "execute_python":
                code_runs += 1
    warns: list[str] = []
    if files_written:
        warns.append("写入过沙箱工作区文件:" + ", ".join(dict.fromkeys(files_written)))
    if code_runs:
        warns.append(f"在沙箱执行了 {code_runs} 段 Python 代码")
    return warns


def build_executor_graph(llm) -> CompiledStateGraph:
    """编译执行 ReAct 子图(共享键直挂,ADR-0009 方案 A)。"""
    def _tools_meta(tools: list) -> str:
        """工具索引(一行一条,desc 截断 60 字):进 executor 系统提示词(09-DEV T4)。"""
        lines = []
        for t in tools:
            text = (t.description or "").strip()
            desc = text.splitlines()[0] if text else ""
            lines.append(f"- {t.name}: {desc[:60]}")
        return "\n".join(lines)

    tools = _gather_tools()
    meta = _tools_meta(tools)
    exec_prompt = load_prompt("subagents/executor", tools_meta=meta)
    system_prompt = load_prompt("base") + "\n\n" + exec_prompt

    def build_summary(state: ReactState) -> ResultSummary:
        contract = SubgraphContract(**state["contract"])
        task_id = uuid.uuid4().hex[:8]
        effects = _collect_effects(state["react_msgs"])
        if getattr(state["react_msgs"][-1], "tool_calls", None):
            # 被轮数上限截停:诚实返回不完整结果
            return ResultSummary(
                agent="executor",
                task_id=task_id,
                task=contract.task,
                status="partial",
                conclusion="执行轮数达上限,返回当前进度",
                warnings=["达到工具调用轮数上限,任务可能未完成", *effects],
            )
        conclusion, key_points = extract_answer(str(state["react_msgs"][-1].content))
        return ResultSummary(
            agent="executor",
            task_id=task_id,
            task=contract.task,
            status="success",
            conclusion=conclusion,
            key_points=key_points,
            warnings=effects,
        )

    return build_react_subgraph(
        llm=llm,
        tools=_gather_tools(),
        system_prompt=system_prompt,
        max_iterations=MAX_ITERATIONS,
        build_summary=build_summary,
    )
