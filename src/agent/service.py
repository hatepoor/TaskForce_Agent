"""单轮业务层:CLI REPL 与 FastAPI 共用的唯一入口(01 模块契约,禁止出现第二套实现)。

本文件作用:
    run_turn() 驱动一轮对话——graph.stream 同步双流消费(messages 流逐 token 回调
    做打字机输出;updates 流抓 supervisor 路由决策做轨迹回调),并兜底
    GraphRecursionError 与"无模型输出"两类异常路径。

使用位置:
    - cli/repl.py:主循环中调用(on_token 打印 / on_route 打印路由);
    - api/(06 模块):on_token 接 SSE StreamingResponse 的 generator,零改动复用。
"""

from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

# ADR-0009 承诺:上下文全量保留 + 超阈值日志告警(只观测不阻断)。
# 会话消息数超阈值时打印膨胀提示,长会话可 /new 换线程。
_MESSAGE_WARN_THRESHOLD = 40

# 后台任务全批完成后的自动汇总触发语:被 REPL watcher 与 API /chat/summary 共用,
# 保证双入口语义一致(历史回填按此前缀过滤,不出现在对话记录里)。
AUTO_NOTICE = "(系统通知)后台子智能体任务已完成,请直接汇总结果。"


def run_turn(graph, config, text=None, resume=None, on_token=None, on_route=None,on_interrupt=None):
    """单轮对话:graph 为 build_graph() 的编译产物。

    on_token(str) 逐 token 回调(打字机);on_route(Route) 每次路由决策回调(轨迹打印)。
    未来 SSE:API 层把 on_token 接到 StreamingResponse 的 generator 即可,零改动。
    """
    try:
        final = None
        inputs = Command(resume=resume) if resume is not None else {"messages": [("user", text)]}
        for mode, payload in graph.stream(
                inputs,
                config=config,
                stream_mode=["messages", "updates"],
        ):
            if mode=='messages':
                chunk,meta = payload
                # 主图白名单过滤(R-T7):只有面向用户的三个主图节点的消息进对话流。
                # supervisor 的结构化 JSON 会被排除(其 parsed 合并会 TypeError);
                # 子图 ReAct 的 agent/tools/finalize 消息(tool_calls 与知识库片段)同样不得泄漏。
                # 白名单不含 memory(实测坑):memory 节点经 with_structured_output 的 JSON
                # 会作为流式 chunk 泄漏到终端;其确认文本走末尾整段渲染(streamed=False)。
                # 只对 AIMessageChunk 流式回调(T4 实测坑):ask 节点 resume 后追加的
                # HumanMessage("[用户回答]:...") 若也触发 on_token,会误启 rich Live
                # 并吞掉后续 console.input 的回显(挂起态盲打)。
                if meta.get("langgraph_node") in {"answer", "ask"}:
                    if isinstance(chunk, AIMessageChunk):
                        if on_token and chunk.content:
                            on_token(chunk.content)
                        final=chunk if final is None else final+chunk
            else:
                for node,update in payload.items():
                    if node=="__interrupt__":
                        # T4:ask 问询挂起——update 即 Interrupt 元组,交回调,返回 None(图保持挂起)
                        if on_interrupt:
                            on_interrupt(update)
                        return None
                    if node=="supervisor" and isinstance(update, dict) and "last_route" in update:
                        if on_route:
                            on_route(update["last_route"])
    except GraphRecursionError:
        # B4:打 taskforce_error 标记——API 层据此发 error 帧(前端可区分"兜底中止"与正常回答)
        return AIMessage(
            content="本轮任务循环过深,已中止。请把需求拆小一点再试。",
            additional_kwargs={"taskforce_error": "recursion_limit"},
        )
    try:
        state = graph.get_state(config)
        msgs = state.values["messages"]
        if len(msgs) >= _MESSAGE_WARN_THRESHOLD:
            print(
                f"[warn] 会话已累积 {len(msgs)} 条消息(阈值 {_MESSAGE_WARN_THRESHOLD}),"
                "上下文将膨胀;长会话可 /new 换新线程"
            )
        return msgs[-1]
    except ValueError:
        # 无 checkpointer 且本轮没有流式 LLM 输出(如 ask/memory 桩节点)时:
        # final 可能为 None,不能返回 None 让调用方(tracker.record 等)炸掉。
        return final if final is not None else AIMessage(content="(本轮无模型输出)")
