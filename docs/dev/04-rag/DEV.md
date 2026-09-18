# 04-RAG 模块开发文档:RAG 内核 + 知识库管理

> 状态:见 [ROADMAP.md](../ROADMAP.md) | 代码目录:`tools/rag/`
> 一句话:做完本模块,知识库子系统独立可用--上传 TXT/MD/Word/PDF,切块向量化入库,top-5 检索命中正确。(支线:可与 01-03 并行)

## 1. 目标与范围

- **做什么**:文档解析(TXT/MD 内置、PDF 用 pypdf、Word 用 python-docx)、`RecursiveCharacterTextSplitter`(500/100)、智谱 embedding(OpenAI 兼容)、pgvector 存取、文档级 CRUD(上传/列表/删除连同向量)、维度启动断言。
- **范围外**:不接子智能体(05)、不做 API router(11)、不装 unstructured(ADR-0005)。管理入口先做成 `python -m tools.rag.cli` 命令行。

## 2. 前置依赖

| 依赖模块 | 需要其中的什么 |
|---|---|
| [00-bootstrap](../00-bootstrap/DEV.md) | `get_settings()`(EMBEDDING 配置)、`ensure_vector_ext` |

## 3. 产出物(文件清单)

| 文件 | 职责 |
|---|---|
| `tools/rag/parse.py` | 四格式 -> 纯文本(按扩展名分发) |
| `tools/rag/split.py` | RCTS(500/100)封装 |
| `tools/rag/embed.py` | 智谱 embedding 客户端(OpenAIEmbeddings,base_url 指智谱) |
| `tools/rag/store.py` | `RAGStore`:建表(documents/chunks 两张)、upload/list_docs/delete/search |
| `tools/rag/cli.py` | `python -m tools.rag.cli upload|list|delete|search` |
| `tests/test_rag.py` | roundtrip 测试(固定小 fixture:txt/md/docx 各一) |

表结构要点:`documents(id, user_id 默认 'local', filename, created_at)`;`chunks(id, doc_id, seq, content, embedding vector(N))`;N 从 embedding 实测维度写入建表语句;删除文档级联删 chunks。

## 4. 分步任务清单

### T1:加依赖 + parse.py
- [x] pyproject 加 `pypdf`、`python-docx`、`langchain-text-splitters`;实现 parse(未知扩展名报错;空文档/解析失败给出可读中文错误)。
- 验收:单测对三种 fixture 提取出非空文本。

### T2:split.py + embed.py
- [x] RCTS(500/100);embed 封装 `embed_texts(list[str]) -> list[list[float]]`,首次调用实测维度并与 `vector(N)` 断言一致(不一致抛 RuntimeError)。
- 验收:单测切块数量符合预期;维度断言逻辑被测试覆盖(伪造不匹配时抛错)。

### T3:RAGStore 建表与写入
- [x] 幂等建表;`upload(path_or_bytes, filename)` = 解析->切块->embed->批量插入(向量以字符串 `'[0.1,...]'` 传给 pgvector)。
- 验收:上传 fixture 后 SQL 计数 = 切块数。

### T4:检索与删除
- [x] `search(query, top_k=5)` = embed 查询 -> `<=>` 余弦距离排序 -> 返回 `{doc_id, filename, seq, content, score}`;`delete(doc_id)` 连同 chunks;`list_docs()`。
- 验收:roundtrip 测试--上传含目标关键词的文档,search 返回 top-5 且第一 chunk 命中;删除后 search 不再命中。

### T5:rag.cli 管理命令
- [x] upload/list/delete/search 四个子命令(为 11 的 /knowledge router 与 CLI /kb 命令复用同一 RAGStore)。
- 验收:`uv run python -m tools.rag.cli search "关键词"` 输出命中列表。

## 5. 验收标准(整模块)

- [ ] `uv run pytest tests/test_rag.py -q` 全绿(roundtrip + 删除 + 断言);
- [ ] 手工:上传一份真 PDF,search 相关问题命中正确段落;
- [ ] embedding 维度与 vector(N) 一致性断言生效。

## 6. 常见坑与规避

| 坑 | 规避 |
|---|---|
| 智谱 embedding 维度与建表不符 | T2 实测维度 + 启动断言(DESIGN.md §6) |
| 向量插入格式 | psycopg 裸 SQL 用字符串字面量传 vector |
| pypdf 解析扫描版 PDF 得空文本 | 不上 OCR;空文本明确报错并提示 |
| 依赖蔓延 | 只加 pypdf/python-docx/langchain-text-splitters,禁 unstructured |
| 测试直连 public 表,DROP 清空真实知识库 | 测试一律用隔离 schema(search_path),见 [troubleshooting/R-react-refactor.md](../../docs/troubleshooting/R-react-refactor.md) #4 |
| 同一文件重复上传(无内容级判重) | documents.content_hash(解析后文本 SHA-256)+ (user_id, content_hash) 唯一索引,见 [troubleshooting/04-rag.md](../../docs/troubleshooting/04-rag.md) #1 |
| 维度断言测试抛错后不恢复表状态 | 断言后显式清伪表并重建,见 [troubleshooting/04-rag.md](../../docs/troubleshooting/04-rag.md) #2 |
| Windows 测试夹具换行翻译(\r\n 写成 \r\r\n) | NamedTemporaryFile(..., newline=""),见 [troubleshooting/04-rag.md](../../docs/troubleshooting/04-rag.md) #3 |

## 7. 契约接口

**本模块定义**:
```python
class RAGStore:
    def upload(self, source, filename: str) -> tuple[str, bool]: ...
    # 返回 (doc_id, created);内容重复(解析后文本 SHA-256 相同)时复用已有 doc_id,
    # created=False 且不再切块/向量化(2026-09-04 内容级防重,存量数据不回填)
    def list_docs(self) -> list[dict]: ...
    def delete(self, doc_id: str) -> None: ...
    def search(self, query: str, top_k: int = 5) -> list[dict]: ...
def embed_texts(texts: list[str]) -> list[list[float]]: ...
```

**本模块消费**:`get_settings`/`ensure_vector_ext`(00)。

## 8. 优化 01:RAG 混合检索(rag_improve_v1)

> 2026-09-14 优化(纯 pgvector → BM25 + 向量双路召回 + RRF 融合,方案 A)。方案、任务与进度见 [docs/improved/rag_improve_v1/](../../improved/rag_improve_v1/TODO.md)。

- 新增 `tools/rag/bm25.py`:`tokenize`(入库/查询双端共用)/ `Bm25Index`(内存 BM25,懒加载 + 脏标记 + 双检锁,loader 注入)/ `rrf_fuse`(排名并集融合,返回 (chunk_id, 融合分));
- `store.search` 拆 `_search_vector`(向量路,SQL 补 `c.id AS chunk_id`)与关键词路,`rrf_fuse` 融合取 top_k,关键词路独占命中 `_fetch_chunks` 回填;upload/delete 后置脏(懒重建,存量零迁移);
- **score 语义翻转**:余弦"越小越近" → RRF"越大越相关",已登记 [ROADMAP §7](../../ROADMAP.md);返回 dict 新增 `chunk_id` 键(只增不改);
- 坑:rank_bm25 0.2.2 小语料负 idf(高频词占多数时 epsilon 下限为负)→ `SafeBM25Okapi` 子类覆写 `_calc_idf` 用 +1 平滑 idf(恒非负)。
