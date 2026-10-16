# 02-Persistence-Cli 模块开发文档:会话持久化 + CLI 骨架

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`settings/db/checkpointer.py`、`settings/session.py`、`cli/repl.py`
> 一句话:做完本模块,聊天有记忆--重启服务后 `/resume` 接着聊,`/new` 开新会话,`/stats` 看消耗。

## 1. 目标与范围

- **做什么**:PostgresSaver checkpointer 接入(连接池);thread_id 会话隔离;`SessionStore` 本地持久化当前 thread_id;斜杠命令 `/new /resume /stats /help /quit`。
- **范围外**:不做长期记忆(06)、会话列表 API(11 可选);不改图结构(仍单节点)。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 | 何时用 |
|---|---|---|
| [01-minimal-agent](../01-minimal-agent/DEV.md) | `build_graph` / `run_turn` / `UsageTracker` | 全程 |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `settings/db/checkpointer.py` | `get_checkpointer(database_url)`(lru_cache 单例,from_conn_string + setup) |
| `settings/session.py` | `SessionStore`(读写 `.taskforce/current_thread`) |
| `cli/repl.py`(增强) | 挂 checkpointer、斜杠命令分发骨架(后续模块的命令都注册到这里) |
| `tests/test_session.py` | SessionStore 读写/默认生成单测 |

## 4. 分步任务清单

### T1:实现 checkpointer 工厂
```python
# settings/db/checkpointer.py
from functools import lru_cache
from langgraph.checkpoint.postgres import PostgresSaver

@lru_cache
def get_checkpointer(database_url: str) -> PostgresSaver:
    saver = PostgresSaver.from_conn_string(database_url)  # 内部 psycopg_pool,线程安全
    saver.setup()                                          # 幂等建 4 张表
    return saver
```
- **必须 `from_conn_string`,绝不手传单个 psycopg 连接**(连接非线程安全,未来 API 线程池会炸);必须同步版 `PostgresSaver`,禁 Async。
- 验收:执行后 psql `\dt` 可见 checkpoints/checkpoint_blobs/checkpoint_writes/checkpoint_wal;重复调用不报错。

### T2:实现 SessionStore
- [ ] 属性 `current_thread_id`(文件不存在则生成 `sess-{uuid4().hex[:8]}` 并写入)、`set_current(tid)`;文件路径 `.taskforce/current_thread`,目录与读写显式 utf-8;`.taskforce/` 进 .gitignore。
- 验收:单测覆盖"无文件生成/读写往返"。

### T3:REPL 挂 checkpointer + thread_id
- [ ] `build_graph(llm, get_checkpointer(s.database_url))`;`config = {"configurable": {"thread_id": thread_id}}` 传给 run_turn。
- 验收:聊 2 轮 -> 退出重进 -> 同 thread_id 问"我刚才说了什么"能答上。

### T4:斜杠命令 /new /resume /stats
- [ ] `/new`:生成新 thread_id、写 SessionStore、换 config;`/resume <id>`:切 thread_id(缺省用当前);`/stats`:打印 tracker.stats_text();命令分发写成"注册表"结构(后续 /kb /memory /mcp 都挂进来)。
- 验收:`/new` 后新会话不记得旧内容;`/stats` 显示非零 tokens。

### T5:重启自动恢复
- [ ] REPL 启动时读 SessionStore,显示"当前会话 {thread_id}",自动接上上下文。
- 验收:聊 2 轮 -> 重启 REPL(进程) -> 不输任何命令直接追问,上下文完整。

> ⚠️ **2026-09-04 用户决议**:启动行为改为**每次开启全新会话**(与历史完全隔离),不再自动接上;旧会话不丢,经 `/resume <id>` 恢复,新增 `/list_session` 列出全部会话 id(checkpointer.py 的 `list_session_ids()`)。

## 5. 验收标准(整模块)

- [ ] 演示剧本:聊天 -> `/new` 开新话题(旧话题遗忘)-> 切回 `/resume <旧id>` 记忆恢复 -> 重启程序自动续上 -> `/stats` 出数。
- [ ] `uv run pytest -q` 全绿(含 test_session)。

## 6. 核心概念速查

- **checkpointer**:LangGraph 的短期记忆--每步图状态按 `thread_id` 持久化;`config["configurable"]["thread_id"]` 是会话的"外键"。
- **`setup()` 幂等**:`CREATE TABLE IF NOT EXISTS`,进程启动调一次。
- thread_id 与未来 API:11 模块里 `thread_id` 改由请求体传入,业务层无感。

## 7. 常见坑与规避

| 坑 | 表现 | 规避 |
|---|---|---|
| 手传单连接给 PostgresSaver | 并发/重启后 "connection is closed" | 只用 `from_conn_string` 连接池 |
| setup() 忘调或每次调用 | 表不存在 / 重复建表 | lru_cache 单例内 setup 一次 |
| 同步异步混用 | "Cannot run async in this thread" | 全链路只碰同步版 |
| thread_id 每次随机 | 会话永远"失忆" | SessionStore 持久化,重启读回 |

## 8. 契约接口

**本模块定义**:
```python
# settings/db/checkpointer.py
@lru_cache
def get_checkpointer(database_url: str) -> PostgresSaver: ...   # 进程唯一连接池

# settings/session.py
class SessionStore:
    @property
    def current_thread_id(self) -> str: ...
    def set_current(self, tid: str) -> None: ...
```

**本模块消费**:`build_graph`/`run_turn`/`UsageTracker`(01)、`get_settings`(00)。
