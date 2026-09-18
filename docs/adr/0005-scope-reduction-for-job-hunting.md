---
status: accepted
---

# v2:范围收缩为单用户实习项目

项目定位变更为"面向实习求职的项目经历",据此收缩范围:取消多用户与 JWT 鉴权(数据表保留 user_id 列默认 'local' 作为扩展点,ADR-0003 中的多用户决策被本决策取代);不实现时间旅行、Send 并行、Langfuse tracing、rerank,移入 backlog;文档解析放弃 unstructured(其依赖链在 Windows 上极易安装失败,是本项目最可能的烂尾点),改用 pypdf + python-docx + 内置读取;放弃 ORM 与 async,采用全同步 + psycopg 裸 SQL(FastAPI def 端点 + 同步 generator SSE + graph.stream),理由是单用户本地场景 async 零收益且"SSE 流式 + interrupt"的组合在异步下极难调试。

保留 PostgreSQL + pgvector 作为唯一存储底座:原始需求即指定 pgsql,长期记忆的向量化检索依赖 pgvector,且 SQLite 无对应的官方 LangGraph Store 实现;环境问题用 Docker Compose(pgvector/pgvector:pg16)一条命令规避。三个子智能体全部保留:边际成本低且是原有设计,但要求 README 能论证"子图与普通工具的边界"。

## Considered Options

- 换 SQLite 进一步简化:被否决,失去 pgvector 向量检索能力,且与原始存储需求不符。
- 子智能体砍到 1 个(仅留调研子图,检索降为普通工具):被否决,三个子图的边际成本远低于架构叙事的收益。
