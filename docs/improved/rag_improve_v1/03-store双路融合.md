# 模块 03 · store.py 双路融合改造

> 状态:✅ 已完成(2026-09-14 验收:29 passed = bm25 12 + rag 17 真实库 roundtrip,ruff 全绿)
> 备注:rrf_fuse 契约细化为返回 (chunk_id, 融合分)(见 00 总览 §5);`cli.py` 核对结论:输出无"距离"字样,零改动
> 目标:`RAGStore.search` 升级为双路召回 + RRF 融合,写入路径置脏,并发安全;对外签名不变。
> 共享设计见 [00-方案总览.md](00-方案总览.md);进度见 [TODO.md](TODO.md)。

## 任务清单

- [ ] 3.1 原 `search` 内向量逻辑抽为私有方法 `_search_vector(query, top_k) -> list[dict]`(SQL 与返回形状不变,score 为 cosine 距离)
- [ ] 3.2 新 `search(query, top_k=5)`:
  - 向量路 `_search_vector(query, top_M=5)` 与关键词路 `bm25.search(query, top_M=5)` 并行取候选
  - 经 `rrf_fuse` 融合 → 回填 `doc_id/filename/seq/content/score` 原形状
  - score 为融合值,**越大越相关**(语义翻转,见总览 §3.3)
- [ ] 3.3 `upload`/`delete` 成功后调用 `bm25.mark_dirty()`;内容重复(`created=False`)不置脏
- [ ] 3.4 `RAGStore.__init__` 挂 `Bm25Index(loader=...)`:loader 读 chunks 全量 content;懒加载保证存量零迁移
- [ ] 3.5 并发锁落地:确认共享单例(`kb_search._default_store`)下懒重建竞态被锁覆盖
- [ ] 3.6 核对 `tools/rag/cli.py` search 输出文案("距离"字样按新语义调整);`kb_search` 接口冻结不改

## 设计要点

- 双路**并行**:向量路走 SQL、关键词路走内存索引,互不阻塞(全同步线程模型下顺序调用即可,天然串行无竞态,锁只护懒重建);
- 融合在 Python 侧做,SQL 保持单路简单,不引入 DB 侧加权 SQL;
- `_search_vector` 抽取后仍可被测试单测(保留纯向量路基线,评测对比用);
- 候选池 M=5 由 `rrf_fuse` 内部处理,`search` 只暴露 `top_k`。

## 验收

```bash
uv run pytest tests/test_rag.py -q          # 全绿(旧用例 + 本模块不改动时先回归)
uv run python -m tools.rag.cli search "关键词"   # 命中正常,score 为融合值(越大越相关)
uv run ruff check src/tools/rag/store.py
```

> 说明:新增混合命中/脏重建用例在模块 05 统一补,本模块先保证行为不回归。

## 学习点

| 学习点 | 可问问题 |
|---|---|
| 双路召回融合的工程接入(不破坏既有 SQL 风格) | "为什么融合放在 Python 侧?" |
| 懒重建 + 置脏与写入路径的联动 | "upload 失败时置脏吗?" |
| 共享单例下的并发安全 | "Send 并行分支为什么可能同时触发重建?" |
