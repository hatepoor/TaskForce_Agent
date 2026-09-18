# 01-Minimal-Agent 模块开发文档:最小对话闭环(最小 demo)

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`agent/`、`settings/usage.py`、`cli/repl.py`
> 一句话:做完本模块,**最小 demo 达成**--REPL 里输入一条消息,收到豆包的流式回复,usage 有打点。

## 1. 目标与范围

- **做什么**:豆包 OpenAI 兼容接入;单节点 LangGraph 图(`START -> chat -> END`);REPL 基础循环(无斜杠命令,仅 /quit);流式逐 token 输出;usage 打点框架。
- **范围外**:不做 checkpointer(02)、斜杠命令(02)、系统提示词注入(agents.md 在 06)、子图与路由(03)、SSE/API(11)。但 `run_turn` 的 on_token 回调设计为 SSE 预留。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 | 何时用 |
|---|---|---|
| [00-bootstrap](../00-bootstrap/DEV.md) | `get_settings()`(LLM 配置)、目录骨架 | 启动时 |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `agent/state.py` | `AgentState`(仅 `messages: Annotated[list, add_messages]`) |
| `agent/build.py` | `make_llm(settings)` + `build_graph(llm, checkpointer=None)` |
| `agent/service.py` | `run_turn()` 单轮业务层(CLI 与未来 API 共用的唯一入口) |
| `settings/usage.py` | `UsageTracker`(record/stats_text/cost_yuan) |
| `cli/repl.py` | REPL 基础循环(input + 流式打印 + /quit) |
| `tests/test_minimal.py` | 图在无 checkpointer 下 invoke 单测(fake/真模型可选) |

## 4. 分步任务清单

### T1:实现 state.py 与 build.py
```python
# agent/state.py
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]

# agent/build.py 要点
def make_llm(settings) -> ChatOpenAI:
    return ChatOpenAI(base_url=..., api_key=..., model=...,
                      temperature=0.7, streaming=True, max_retries=3, timeout=60)

def chat_node(state, llm) -> dict:
    return {"messages": [llm.invoke(state["messages"])]}

def build_graph(llm, checkpointer=None):
    b = StateGraph(AgentState)
    b.add_node("chat", lambda s: chat_node(s, llm))
    b.add_edge(START, "chat"); b.add_edge("chat", END)
    return b.compile(checkpointer=checkpointer)   # None 时便于单测
```
- 验收:脚本 `build_graph(make_llm(get_settings())).invoke({"messages":[("user","你好")]})` 返回中文 AIMessage。

### T2:实现 run_turn(业务层)
```python
def run_turn(graph, config, text, on_token=None):
    """单轮对话。on_token(str) 逐 token 回调;返回最终 AIMessage。
    未来 SSE:API 层把 on_token 接到 StreamingResponse 的 generator 即可,零改动。"""
    for chunk, _meta in graph.stream({"messages": [("user", text)]},
                                      config=config, stream_mode="messages"):
        if on_token and chunk.content:
            on_token(chunk.content)
    return graph.get_state(config).values["messages"][-1]
```
- 要点:`stream_mode="messages"` 才是逐 token;默认 values 模式是整块吐。
- 验收:单元测试(fake ChatModel)证明 on_token 被多次调用、返回值为 AIMessage。

### T3:实现 UsageTracker
- [ ] `record(message)` 从 `message.usage_metadata` 读 `input_tokens/output_tokens`(None 按 0 兜底并告警一次);`stats_text()` 输出调用次数/输入/输出/合计/估算费用(单价来自 config,为 0 时费用列 0 不误导)。
- 验收:单元测试累加正确、计费公式正确。

### T4:REPL v1
- [ ] 入口 `sys.stdout.reconfigure(encoding="utf-8")`;`input("你 > ")` 循环;`/quit` 退出;普通消息走 `run_turn`,`on_token=lambda t: print(t, end="", flush=True)`;每轮结束 `tracker.record(final)`。
- 验收:`uv run python -m cli.repl`,输入问句,打字机式逐 token 回复;Ctrl+C/Ctrl+D 干净退出。

### T5:pytest 冒烟
- [ ] tests/test_minimal.py:fake ChatModel(返回固定字符串)驱动 `build_graph(fake_llm).invoke`(checkpointer 默认 None);UsageTracker 两项单测。
- 验收:`uv run pytest -q` 全绿。

## 5. 验收标准(整模块)

- [ ] 演示:REPL 输入"用一句话介绍 LangGraph",逐 token 收到回复;连聊三轮上下文连贯(messages 累积生效)。
- [ ] 日志/终端能看到每轮 usage(输入/输出 tokens 非零)。
- [ ] `uv run pytest -q` 全绿;`ruff check .` 通过。
- [ ] **这就是简历 demo 的第一块里程碑:能跑的 Agent。**

## 6. 核心概念速查

- `StateGraph` / `add_messages`:LangGraph 图与消息追加 reducer;本模块只用最小形态。
- `stream_mode="messages"`:逐 token 消息块流;chunk 是 `AIMessageChunk`,`.content` 为增量。
- **usage 不能从 chunk 拿**(流式下只有部分值甚至 None),必须流结束后从 `graph.get_state(config)` 的最终 AIMessage 读 `.usage_metadata`。
- 全同步纪律:节点/客户端/调用全部 `def`,禁 async。

## 7. 常见坑与规避

| 坑 | 表现 | 规避 |
|---|---|---|
| base_url 少 `/api/v3`、model 填错 | 401/404 | .env 注释强调用推理接入点 `ep-xxx`;REPL 把 HTTP 错误打印成含状态码的可读中文 |
| 忘开 `streaming=True` | 整段输出 | make_llm 里固定开启 |
| 从 chunk 取 usage | 数字为 0 或 None | 一律 `get_state` 后取,见 §6 |
| 中文乱码 | UnicodeEncodeError | 入口 reconfigure + PYTHONUTF8=1 |

## 8. 契约接口

**本模块定义**:
```python
# agent/build.py
def make_llm(settings) -> ChatOpenAI: ...
def build_graph(llm, checkpointer=None) -> CompiledGraph: ...   # CLI/API 唯一构建入口

# agent/service.py
def run_turn(graph, config, text, on_token=None) -> AIMessage: ...

# settings/usage.py
class UsageTracker:
    def record(self, message) -> None: ...
    def stats_text(self) -> str: ...
```

**本模块消费**:`settings.config.get_settings`(00)。
