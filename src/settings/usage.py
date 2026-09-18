"""Token 用量统计:REPL /stats 与退出汇总的数据源。

使用位置:
    - cli/repl.py:每轮 run_turn 后 record(final),/stats 与 /quit 打印 stats_text()。
"""
import threading

from langchain_core.messages import AIMessage


class UsageTracker:
    """进程内累计 LLM 调用次数与输入/输出 token,并按单价估算费用。"""

    def __init__(self,settings)->None:
        """初始化计数器;settings 提供 llm_*_price_per_m 计费单价。"""
        self._s=settings
        self.calls=0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0  # 缓存命中 token(ADR-0011:观测缓存收益)
        self._warned = False
        self._lock=threading.Lock()# B5:SSE 线程化后 record可能被并发调用

    def record(self,message:AIMessage)->None:
        """从最终 AIMessage 读 usage_metadata 累加;
        None 按 0 兜底并告警一次。"""
        meta = message.usage_metadata
        with self._lock:
            if meta is None:
                if not self._warned:
                    print("[usage] 该消息无 usage_metadata,按 0 计")  # 只提示一次
                    self._warned = True
                return

            self.calls += 1
            self.input_tokens += meta.get("input_tokens") or 0
            self.output_tokens += meta.get("output_tokens") or 0
            # 缓存命中字段随 provider 而异(Anthropic cache_read_input_tokens /
            # OpenAI prompt_cache_hit_tokens / langchain input_token_details.cache_read)
            details = meta.get("input_token_details") or {}
            self.cache_read_tokens += (
                    meta.get("cache_read_input_tokens")
                    or meta.get("prompt_cache_hit_tokens")
                    or details.get("cache_read")
                    or 0
            )

    def stats_text(self) -> str:
        """一行统计:调用次数 / 输入 / 输出 / 缓存命中 / 合计(单价留档于 .env)。"""
        total = self.input_tokens + self.output_tokens
        base = (
            f"usage: 调用 {self.calls} 次 | 输入 {self.input_tokens} tok | "
            f"输出 {self.output_tokens} tok | 合计 {total} tok"
        )
        if self.cache_read_tokens:
            base += f" | 缓存命中 {self.cache_read_tokens} tok"
        return base
