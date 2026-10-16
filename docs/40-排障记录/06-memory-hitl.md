# 模块 06:长期记忆 + 统一 HITL — 问题与解决记录

> 格式规范见 [README.md](README.md)。本文件登记模块 06(长期记忆 Store + ask/memory 双 interrupt)开发中的实踩坑位。

## 1. pgvector HNSW 索引 2000 维上限:智谱 embedding(2048 维)建索引直接失败

- **现象**:`get_store()` 装配 PostgresStore 后,`tests/test_memory.py` 全部 skip,skip 原因是 `column cannot have more than 2000 dimensions for hnsw index`(setup 建索引时抛错)。
- **根因**:默认 `ann_index_config: {"kind": "hnsw"}` 触发 HNSW 索引;pgvector 的 HNSW/IVFFlat 索引**硬上限 2000 维**,而智谱 embedding 实测 2048 维(见 `embedding_dim()`)。
- **解决**:索引类型改 `{"kind": "flat"}`(暴力扫描,无维度上限)。单用户长期记忆量级小(几十~几百条),flat 全扫描性能完全够用,且不依赖 pgvector 版本(半精度 halfvec 方案需 pgvector>=0.7,当前不可取)。
- **关联**:settings/db/store.py::get_store、tests/test_memory.py、经验:**embedding 维度先探测再选索引类型,默认 HNSW 对 >2000 维模型直接不可用**。

## 2. PostgresStore 的 index.embed 契约是批量签名,传单文本函数会套娃出错

- **现象**:`_embed_query(text: str) -> list[float]`(单文本)传给 `index.embed` 后,put 时报 `TypeError: 'list' object ...`(tiktoken 内部编码失败),traceback 经 `embed_documents -> func(texts)` 链路过进 `embed_texts([[text]])`(list 套 list)。
- **根因**:langgraph 的 `EmbeddingsFunc = Callable[[Sequence[str]], list[list[float]]]`(**批量**签名,embed.py:19);PostgresStore 内部用 `EmbeddingsLambda` 包装 embed,put/search 都调 `embed_documents(texts)`(传列表)。单文本函数被调用时收到的是 `[str]` 而非 `str`,再包一层 `[text]` 就成了 `[[str]]`。
- **解决**:`index.embed` 直接复用 04 的 `embed_texts(texts)`(恰好就是批量签名 `(list[str]) -> list[list[float]]`),删除自造的 `_embed_query`。单文本与批量两种形态由 `EmbeddingsLambda` 内部统一,用户侧只需给批量函数。
- **关联**:settings/db/store.py::get_store、tools/rag/embed.py::embed_texts、.venv langgraph/store/base/embed.py(EmbeddingsFunc 定义)、经验:**给 store 的 embed 传"列表进列表出"的批量函数,不要按 embed_query 单文本语义写**。

## 3. interrupt 挂起的问题被打印两次:run_turn 回调与 REPL 主循环挂起检测重复

- **现象**:T4 真模型验收时,"帮我查询下天气"触发 ask 挂起后,`Agent 提问 › 你想查询哪个城市…` 在终端**连续打印两次**,随后才出现"你的回答 ›"输入提示。
- **根因**:问题打印存在两条路径——①`run_turn` 遇 `__interrupt__` 时经 `on_interrupt` 回调打印一次;②`run_turn` 返回 None 后 REPL 主循环 `continue`,下一轮顶部的挂起检测(`graph.get_state(config).interrupts` 非空)又打印一次。两条路径各自"正确",叠加即双重。
- **解决**:问题打印**统一收敛到主循环挂起检测**一处(它对跨进程重启后 resume 挂起的场景同样生效);`on_interrupt` 回调保留接口但改为空实现(docstring 注明实测坑)。见 `cli/repl.py::on_interrupt` 与主循环挂起检测分支。
- **关联**:ADR-0008(单一挂起点)、tests/test_ask.py、经验:**interrupt 的 UI 呈现只放"挂起检测"一处,流式回调(run_turn on_*)不做呈现,两者并存必重复**。

## 4. ask 多轮追问后输入盲打:ask 节点的 HumanMessage 误启 rich Live 且挂起路径不清理

- **现象**:T4 真模型验收第二轮:首次提问回答正常;supervisor 追问(第二次 ask 挂起)后,用户在"你的回答 ›"输入**不回显(盲打)**;此后所有输入都不显示。日志里 resume 轮意外出现了"Agent ›"标签。
- **根因**(两处叠加):
  1. `service.py` 的 messages 流白名单含 `"ask"`,resume 轮中 ask 节点返回的 `[用户回答]:...` **HumanMessage** 也触发了 `on_token` → 打印"Agent ›"并启动 rich Live(`on_token` 原逻辑先判 content 再判 `isinstance(chunk, AIMessageChunk)`,顺序反了);
  2. REPL 主循环 resume 分支的 `run_turn` 调用**没有 try/finally 清理**——`on_token` 启动的 Live 在 run_turn 遇 interrupt 返回 None 时残留运行,rich Live 的持续重绘吞掉后续 `console.input` 的终端回显。
- **解决**:①`service.py` 把流式回调移进 `isinstance(chunk, AIMessageChunk)` 分支(只有模型 chunk 触发 on_token,HumanMessage/ToolMessage 不再误启 Live);②repl.py resume 分支补与正常轮同款的 finally 清理(stop_status + live.stop/live=None)。
- **关联**:service.py::run_turn(R-T7 白名单)、cli/repl.py 主循环、经验:**流式回调只认 AIMessageChunk;任何分支 return/continue 前必须收 rich Live 与 Spinner,挂起路径也不例外**。

## 5. memory 节点显示原始 JSON:结构化输出在流式模型上泄漏到终端

- **现象**:T6 真模型验收,"记住,我叫张飞航" 路由 memory 后,终端显示 `Agent ›\n{"content":"用户叫张飞航","source":"explicit"}`(原始 JSON 当回答渲染),而非"已记住:用户叫张飞航";且 `[usage] 该消息无 usage_metadata,按 0 计`。
- **根因**:`make_llm` 开启 `streaming=True` 后,`with_structured_output().invoke()` 底层以流式 chunk 生成 JSON;这些 chunk 经 `graph.stream(mode="messages")` 暴露,而 R-T7 白名单含 `"memory"` 节点 → `on_token` 收到 JSON chunk → 启动 Live 渲染原始 JSON;同时 `streamed=True` 使 run_turn 末尾"整段渲染最终消息"的分支被跳过(用户看不到"已记住"),且 chunk 聚合的 final 无 usage_metadata(usage 告警)。
- **解决**:①`service.py` 白名单 `{answer,ask,memory}` → `{answer,ask}`——memory 的 JSON 不进用户流,其确认文本走末尾整段渲染(streamed=False);②memory 节点改用**普通 invoke + JSON 解析**(`_parse_memory_proposal` 容错剥 markdown 围栏),返回的 AIMessage 显式携带 `usage_metadata`,/stats 打点正常。
- **关联**:agent/memory.py::_propose/_parse_memory_proposal、agent/service.py::run_turn、agent/build.py::make_llm(streaming=True)、经验:**在白名单内的节点若用结构化输出,JSON 会经流式通道泄漏;要么移出白名单,要么改普通 invoke + 解析(还能顺带拿 usage)**。
