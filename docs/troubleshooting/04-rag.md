# 04-RAG 模块 — 问题与解决记录

> 格式规范见 [README.md](README.md)。本文件登记 RAG 内核(模块 04 及其后续增强)的实踩坑位。

## 1. 知识库无内容级判重,同一文件可被无限重复上传

- **现象**:同一文档多次 `/kb upload` 产生多份 documents+chunks,检索结果重复、embedding 调用费用白白浪费;用文件名判重不可靠——同内容不同名(a.md / a副本.md)漏判,同名改稿重传误判。
- **根因**:documents 表没有任何内容指纹,`upload` 只管插入;判重缺少"内容一样"的可靠定义。
- **解决(2026-09-04)**:documents 加 `content_hash` 列 = **解析后文本规范化哈希**(`\r\n|\r → \n` 统一换行 + strip 后的 SHA-256;不按原始字节算,否则同内容存成 txt/md、Word 重新另存都会漏判),配 `(user_id, content_hash)` **唯一索引**做竞态兜底;`upload` 先查哈希,命中直接复用已有 doc_id(不再切块/向量化,省 embedding 调用),返回值改为 `(doc_id, created)` 并捕获 UniqueViolation 处理极端竞态;**存量旧数据不回填**(用户决议,content_hash 为 NULL 的旧行不参与判重,PG 唯一索引允许多个 NULL 不冲突)。
- **关联**:`tools/rag/store.py`(_content_hash/_ensure_table/upload)、ROADMAP §7(upload 返回值变更登记)、04-DEV §6/§7、tests/test_rag.py 防重 5 用例。

## 2. 维度断言测试抛错后不恢复表状态,后续用例连锁崩溃

- **现象**:给 test_rag.py 追加新用例后,排在 `test_dim_mismatch_raises` **之后**的用例全部报 `UndefinedTable: relation "documents" does not exist`。
- **根因**:维度测试先 DROP documents/chunks 再伪造 vector(4) 表;`RAGStore(db)` 在维度断言处**抛 RuntimeError 提前返回**——正常表永远没机会重建,污染了模块级 fixture 的后续状态。旧版测试恰好排在最后才没暴露。
- **解决**:断言之后显式清伪表并 `RAGStore(db)` 重建正常表;教训:**任何"断言抛错"的测试,若中途修改了共享资源,必须在断言后恢复,不能依赖被测代码的异常路径顺带恢复**。
- **关联**:tests/test_rag.py::test_dim_mismatch_raises、troubleshooting/R-react-refactor.md #4(同族问题:测试不得污染真实数据)。

## 3. Windows 上 NamedTemporaryFile 默认换行翻译,写 "\r\n" 落盘成 "\r\r\n"

- **现象**:换行规范化测试(CRLF vs LF 应判重命中)失败——第二次上传竟按新内容入库。
- **根因**:Windows 文本模式(`newline=None`)写文件时把 `\n` 翻译成 `os.linesep`,`f.write("行一\r\n行二")` 落盘为 `行一\r\r\n行二`;读回(universal newlines)变成 `行一\n\n行二`,与第一次上传的 `行一\n行二` 真的是不同内容——测试构造的"仅换行差异"前提不成立。
- **解决**:`NamedTemporaryFile(..., newline="")` 禁用翻译,让 CRLF 原样落盘;教训:**Windows 上凡涉及字节/换行敏感的测试夹具,一律显式 newline=""**。
- **关联**:tests/test_rag.py::_tmp_txt、store.py::_content_hash(规范化逻辑本身正确)。

## 4. 测试内未限定 schema 的裸表名,在 public 脏状态下解析歧义、隔离被击穿

- **现象**:维度测试连锁报 `DependentObjectsStillExist: cannot drop table documents because constraint chunks_doc_id_fkey ... depends on it`,后续去重用例连环崩;同库状态不同轮次结果漂移。
- **根因**:维度测试的 `DROP/CREATE TABLE chunks/documents` 用**未限定表名**,依赖 search_path 隐式解析;public 残留同名表(历史轮次隔离不彻底的产物)时,对象归属与依赖关系跨 schema 纠缠,行为不可复现。
- **解决**:测试内 DDL 一律 `current_schema()` 显式限定(`DROP TABLE "{schema}".chunks`);**教训:测试内凡涉及 DDL,禁止裸表名,不把解析交给 search_path**。另:probe 排查时若 search_path 首个 schema 不存在,CREATE 会静默落到 public——隔离 schema 必须 CREATE SCHEMA 后再连。
- **关联**:tests/test_rag.py::test_dim_mismatch_raises、troubleshooting/R-react-refactor.md #4(同族:测试与真实数据隔离)。

## 5. 长文档上传报智谱错误码 1214:input 数组最大不得超过 64 条

- **现象(2026-09-04)**:`/kb upload` 一篇较长的 md,报 `Error code: 400 - {'error': {'code': '1214', 'message': 'input数组最大不得超过64条'}}`;短文档(≤64 块)上传一直正常,问题只在长文档出现。
- **根因**:`embed_texts` 把全部 chunk **一次性**塞进 `embed_documents` 发出;智谱 embedding 接口单请求 input 数组上限 64 条,长文档切块(500/100)后超过 64 块即被整单拒绝。属于"开发期用短文档测不出、真实文档才暴露"的供应商限流类坑。
- **解决**:`tools/rag/embed.py` 的 `embed_texts` 按常量 `ZHIPU_BATCH_LIMIT = 64` 分批请求,结果按原顺序拼接,调用方(store.upload/search)无感知;注意拼接顺序不能乱——chunks 表的 `seq` 与向量按下标一一对应。
- **关联**:`tools/rag/embed.py`(embed_texts)、`tools/rag/store.py`(upload 调用方)、tests/test_rag.py。

## 6. rank_bm25 0.2.2 小语料负 idf:epsilon 下限为负,BM25 关键词路全军覆没

- **现象(2026-09-14,优化 01 混合检索)**:`Bm25Index.search("苹果", 3)` 对含"苹果"的固定语料返回空列表;直接调 `BM25Okapi.get_scores(["苹果"])` 得到负分(-0.031),`score > 0` 过滤把全部命中滤光,关键词路等于失效。
- **根因**:rank_bm25 0.2.2 的 `_calc_idf` 用 `idf = log(N-df+0.5) - log(df+0.5)`,词出现在**超过一半文档**时 idf 为负;它的负值兜底是 `eps = epsilon * average_idf`(默认 epsilon=0.25),但**小语料下高频词占多数时 average_idf 本身为负**,eps 成了负下限,负 idf 词仍然得负分;显式 `epsilon=0` 更糟——负 idf 词得 0 分,同样被 `score > 0` 过滤。两个配置都无法让高频词产生正分,而个人知识库(文档少、词频集中)正是这种"高频词占多数"的典型场景。
- **解决**:子类 `SafeBM25Okapi(BM25Okapi)` 覆写 `_calc_idf`,改用带 +1 平滑的标准 BM25 idf `log(1 + (N-df+0.5)/(df+0.5))`(恒非负),打分与 k1/b 保持库默认;`"score > 0 即有命中词"` 语义恢复成立,测试断言"高频 > 低频 > 无命中"全绿。教训:**第三方检索库的 idf 平滑在小语料下可能与"命中即正分"的过滤语义冲突,接入前先用小语料冒烟打分符号,不要只信文档里的"eps 下限防负分"描述**。
- **关联**:`tools/rag/bm25.py`(SafeBM25Okapi)、docs/improved/rag_improve_v1/00-方案总览.md §7 坑表、tests/test_bm25.py::TestBm25Index。
