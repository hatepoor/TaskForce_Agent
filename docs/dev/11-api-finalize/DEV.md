# 11-Api-Finalize 模块开发文档:FastAPI 6-Router + SSE + 收尾

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`api/routers/`、`api/main.py`、根目录 README
> 一句话:第二入口上线(SSE 流式 API 全家),然后 README、演示剧本、录屏--项目交付。

## 1. 目标与范围

- **做什么**:六个 router(chat/knowledge/memory/skills/mcp/health);SSE 用**同步 generator** 喂 `StreamingResponse`;HITL 两类挂起的 API 恢复端点;API 冒烟测试;README(定位句/架构图/五分钟起步/刻意不做/设计决策);3-5 条固定演示剧本;(可选)录屏。
- **范围外**:前端、鉴权、多用户(backlog);不引入 async(全 def 端点,FastAPI 自动丢线程池)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [02-persistence-cli](../02-persistence-cli/DEV.md) | checkpointer、SessionStore |
| [04-rag](../04-rag/DEV.md) | RAGStore(CRUD) |
| [05/06/07/08/09/10](../05-retriever-subagent/DEV.md) | 各能力(经 build_graph/run_turn 统一暴露) |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `api/routers/chat.py` | POST /chat(SSE)、GET /chat/threads、POST /chat/confirm、POST /chat/answer;**后台任务闭环(2026-09-18):GET /chat/tasks(peek)、POST /chat/summary(自动汇总轮)** |
| `api/routers/model_settings.py` | GET/PUT /models/config(设置页模型配置;覆盖表落 `.taskforce/model_config.json`,重启生效;api_key 掩码回显)【2026-09-18 追加】 |
| `api/routers/knowledge.py` | GET /knowledge、POST /knowledge/upload、DELETE /knowledge/{doc_id} |
| `api/routers/memory.py` | GET /memory、DELETE /memory/{id} |
| `api/routers/skills.py` | GET /skills |
| `api/routers/mcp.py` | GET/POST/DELETE /mcp/servers、POST /mcp/servers/{name}/test |
| `api/routers/health.py` | GET /health(存活 + DB + 可选沙箱自检) |
| `api/main.py` | 挂载 router、lifespan 里初始化(连不上 DB 启动即报) |
| `README.md` | 见 T5 |
| `tests/test_api.py` | TestClient 冒烟 |
| `docs/demo-scripts.md`(或 README 内) | 3-5 条固定演示剧本 |

## 4. 分步任务清单

### T1:chat SSE(核心)
```python
@router.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    graph = build_graph(...); config = {"configurable": {"thread_id": req.thread_id}}
    def gen():
        final = run_turn(graph, config, req.text, on_token=lambda t: None)
        yield f"data: {json.dumps({'token': ...})}\n\n"   # on_token 改为写入队列/列表的方案按实现取简
        yield f"data: {json.dumps({'usage': ...})}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```
- [ ] 同步 generator + `def` 端点(禁 async def);事件格式:`token` 增量、`route` 轨迹、`usage` 收尾、`interrupt`(挂起时)。
- 验收:curl -N POST /chat 逐行收到 token 流;CLI(REPL)与 API 调同一 run_turn(无第二套实现,验收时 grep 确认)。

### T2:HITL 的 API 恢复
- [ ] `POST /chat/confirm {thread_id, approved}` -> `Command(resume=bool)`;`POST /chat/answer {thread_id, text}` -> `Command(resume=text)`;两者与 REPL 的 /confirm、自由文本行为一致;GET /chat/threads 返回近 N 个 thread_id(查 checkpoints 表 DISTINCT)。
- 验收:TestClient 脚本:发消息 -> 收到 interrupt 事件 -> confirm -> 收到续流。

### T3:其余 router
- [ ] knowledge(multipart 上传,复用 RAGStore)、memory(list/delete,复用 06 的 store 封装)、skills(元数据)、mcp(配置 CRUD + test,复用 08)、health(200 + db ping + 沙箱可选)。
- 验收:tests/test_api.py 冒烟全绿;uvicorn 起服务后 curl /health 返回 ok。

### T4:全量回归
- [ ] `uv run pytest -q` 全绿;ruff 通过;`uv run python -m cli.repl` 仍正常(双入口并存)。
- 验收:两入口各跑一遍黄金剧本。

### T5:README(面试官 30 秒扫描线)
- [ ] 必含:顶部定位句(DESIGN.md 顶部原文)、mermaid 架构图(本地主体 + 远程沙箱分离)、GIF/录屏 + 一行启动、五分钟起步(compose up -> cp .env -> uv sync -> uvicorn / repl)、功能勾选清单、**"刻意不做"清单(附一句取舍理由,取自 DESIGN §12)**、设计决策章节(五道必答题:子图vs工具/多智能体价值/无async并行/沙箱远程/HITL单点)、一条命令跑测试。
- 验收:新人按 README 五分钟起步能跑通 demo。

### T6:演示剧本(3-5 条固定)
- [ ] ①"记住我偏好 X" -> 新会话生效(记忆);②缺参数 -> ask 提问 -> 回答继续(HITL);③上传 PDF -> 知识库问答(RAG);④"写脚本统计 CSV" -> 沙箱执行;⑤黄金剧本:并行派发 2 调研 + 1 检索一次汇总(多智能体+Send)。每条含:输入、预期轨迹、预期输出要点。
- 验收:每条剧本彩排一遍通过(不临场发挥);(可选)录 5 分钟屏。

## 5. 验收标准(整模块)

- [ ] API 全端点冒烟绿;SSE 流式与 interrupt 恢复可用;
- [ ] README 齐备且五分钟起步可复现;
- [ ] 演示剧本全部彩排通过;`uv run pytest -q` 全量绿;ruff 通过;
- [ ] 项目交付:GitHub push,repo 名 taskforce。

## 6. 核心概念速查

- **同步 SSE**:`def` 端点 + 同步 generator + StreamingResponse;FastAPI 把同步端点丢线程池,不阻塞事件循环。
- **双入口共用业务层**:REPL 与 API 都只调 `build_graph`/`run_turn`,这是验收红线。

## 7. 常见坑与规避

| 坑 | 规避 |
|---|---|
| 误写成 async def | 全 def;写 SSE 时对照本模块 T1 代码骨架 |
| SSE 里做 interrupt 恢复复合 bug | 06 已在 REPL 测通语义,本模块只做端点映射 |
| multipart 上传大文件卡死 | 上传大小限制(如 20MB)与友好报错 |
| lifespan 未初始化就请求 | lifespan 里完成 checkpointer/store/setup 后才放行 |

## 8. 契约接口

**本模块定义**:HTTP API 面(见 §3 表);`api/main.py` 为部署入口。

**本模块消费**:全部前置模块的契约(见 ROADMAP §6)。
