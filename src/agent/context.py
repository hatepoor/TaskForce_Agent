"""主图上下文视图层(水位制定稿式压缩,P4)。

本文件作用:
    存储层(state["messages"])全量 append-only 是唯一事实源;本模块只做两件事——
    ① assembleView:把"发给 LLM 的视图"确定性拼装为 固定 system + digest 摘要
    (SystemMessage)+ 水位后原始消息,digest 冻结期内每轮输出前缀稳定,
    prefix cache 零损失;② maybeCompact:answer 入口的确定性预算检查,
    超预算才调一次摘要 LLM 增量更新 digest 并推进水位。
    digest 与水位存 AgentState.contextDigest = {"digest": str, "uptoId": str},
    随 checkpoint 持久化、可再生(从 messages 全量层重摘即可)。

红线(docs/new_module/agent_opt_0.1/05-上下文分层.md §六):
    绝不删改 messages;digest 绝不写进 messages channel;水位用 message id 对齐;
    compact 只在 answer 触发(supervisor 只消费);不感知子图。

使用位置:
    - agent/supervisor.py / agent/answer.py:发 LLM 前 assembleView 拼装;
    - agent/answer.py:入口 maybeCompact(写回 contextDigest 仅此一处)。
"""

import logging

from langchain_core.messages import SystemMessage

from settings.loader import load_prompt

logger = logging.getLogger(__name__)

DIGEST_HEADER = "[会话历史摘要]\n"  # digest 消息前缀说明(先例:PREFIX_SUBAGENT_RESULT 常量)


def overBudget(messages: list, budget: int) -> bool:
    """消息字符总数是否越过预算(与 subagents/react.py 的 _msgs_over_budget 同风格;
    假设 content 为 str,与该处现状一致)。"""
    return sum(len(getattr(m, "content", "") or "") for m in messages) > budget


def locateWatermark(messages: list, uptoId: str) -> int:
    """水位 id → 列表下标;找不到(旧会话消息被清理等)返回 -1,
    调用方降级为全量直塞(= 现状行为)并告警,不抛错(05 §七)。"""
    for i in range(len(messages) - 1, -1, -1):
        if getattr(messages[i], "id", None) == uptoId:
            return i
    if uptoId:
        logger.warning("[context] contextDigest.uptoId 未定位到,降级全量直塞:%s", uptoId)
    return -1


def _truncateLongMsg(msg, limit: int):
    """单条超长确定性截断:确定性函数 × 不变输入 = 每轮产出逐字节相同(缓存安全);
    只截 content,不动 id/tool_calls(配对与水位稳定)。"""
    content = str(getattr(msg, "content", "") or "")
    if len(content) <= limit:
        return msg
    return msg.model_copy(update={
        "content": content[:limit] + f"…[截断,原文 {len(content)} 字符]",
    })


def assembleView(system: str, digestState: dict, messages: list, longMsgLimit: int) -> list:
    """拼装"发给 LLM 的视图"(05 §2.2):[固定 system] + [digest 摘要消息] + [水位后消息]。

    确定性纯函数:digest 冻结 + 水位不动 + messages append-only ⇒ 每轮输出
    字节级 = 上轮 + 尾部新增,prefix cache 零损失(05 §2.3)。digestState 为空或
    水位定位失败时退化为现状(全量直塞)。不写回 state。"""
    digestState = digestState or {}
    digest = str(digestState.get("digest", "") or "").strip()
    uptoId = str(digestState.get("uptoId", "") or "")
    out: list = [SystemMessage(content=system)]
    start = 0
    if digest:
        idx = locateWatermark(messages, uptoId)
        if idx >= 0:
            out.append(SystemMessage(content=DIGEST_HEADER + digest))
            start = idx + 1
        # 定位失败:不注入 digest(digest 描述的区间已不可信),全量直塞即现状
    out.extend(_truncateLongMsg(m, longMsgLimit) for m in messages[start:])
    return out


def maybeCompact(messages: list, digestState: dict, llm, budget: int, target: int) -> dict | None:
    """answer 入口的确定性预算检查(05 §2.4):活跃段(水位后)超 budget 才调一次
    摘要 LLM,增量摘要"旧 digest + 水位后消息"并推进水位,返回新的 contextDigest
    (写回 state 由 answer 节点合并,单点写);不超预算/摘要失败/空产出/末条无 id
    返回 None(保留旧 digest,超预算轮不阻塞对话)。supervisor 不调本函数。"""
    digestState = digestState or {}
    uptoId = str(digestState.get("uptoId", "") or "")
    idx = locateWatermark(messages, uptoId) if uptoId else -1
    start = idx + 1 if idx >= 0 else 0
    active = messages[start:]
    if not active or not overBudget(active, budget):
        return None
    newUpto = str(getattr(active[-1], "id", "") or "")
    if not newUpto:
        # 末条无 id 时水位会失效导致每轮重摘,宁可放弃本次 compact(在调 LLM 前拦截)
        return None
    transcript = "\n".join(
            f"[{type(m).__name__}] {getattr(m, 'content', '')}" for m in active
        )
    try:
        prompt = load_prompt(
                "compact",
                digest=str(digestState.get("digest", "") or "") or "(无)",
                transcript=transcript,
                target=str(target),
            )
        res = llm.invoke(prompt)
    except Exception as e:  # 降级:摘要失败保留旧 digest,本轮仍可服务(05 §2.4)
        logger.warning("[context] compact 摘要失败,保留旧 digest:%s", e)
        return None
    newDigest = str(getattr(res, "content", "") or "").strip()
    if not newDigest:
        return None
    return {"digest": newDigest, "uptoId": newUpto}
