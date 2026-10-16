# rag_0.1 · 新 RAG 系统建设(docling 解析 · 父子分块 · Milvus 混合检索 · ragas 评估)· 进度清单

> 一句话: 在 `src/rag_v01/` 从零重建知识库 RAG——docling 结构化解析 pdf/docx/md、父子分块、Milvus(HNSW + 内置 BM25)双路 top-20 召回 + 手写 RRF(k=60)取 top-5、ragas 四指标量化基线。
> 关联: 方案 [00-总览.md](README.md) | 旧改进 [docs/99-历史存档/rag_improve_v1/TODO.md](../../../99-历史存档/rag_improve_v1/TODO.md) | 契约登记 [ROADMAP.md](../../../30-开发过程/ROADMAP.md) §7

## 模块进度看板(每完成一项回来改这里)

状态口径: ✅ 完成 · ❓ 未开始 · 🔴 有问题/阻塞

| 模块 | 名称 | 状态 | 说明 |
|---|---|---|---|
| 01 | 环境与依赖 | ✅ 完成 | 2026-09-20: 依赖同步 + 6 条冒烟全绿(含重启持久性); Milvus 跑在 WSL `~/milvus`; 2 条可选项未做 |
| 02 | 文档解析与噪声处理 | ✅ 完成 | 2026-09-20: 代码 + 21 项单测全绿, ruff 干净; 2026-09-22 **真 pdf 已验证**(15 页讲义: SUCCESS、156 条目全带页码、标题正确、模型只加载一次); 遗留(不阻塞): 该 pdf 无表格/插图所以这两项仍未真件覆盖、`RAG2_IMAGE_DESC` 可选开关 |
| 03 | 父子分块策略 | ✅ 完成 | 2026-09-21: 包 `chunk/`(`__init__`/`common`/`parents`/`children`) + 21 项单测全绿; 子块切分改用 langchain 库、重叠自己写(§4.7 记四个坑); 长文验收 10/10 达标; 遗留: 真 pdf 长度分布 |
| 04 | 嵌入与 Milvus 索引 | ✅ 完成 | 2026-09-21: `embed.py`(双模式 + `embed_chunks` 分组拼回/无本地图降级) + `store.py`(双 collection 建表 + 读写三原语) 落地, 模块 61 项单测(embed 32 / store 29)、套件 103 项全绿; **真机验收清单全过**(建表幂等 / HNSW 与 BM25 索引 / 分词对齐 / 两路召回 / 幂等 / 删除 / 维度自检 / 跨模态 0.74 vs 0.23); **实测修正**: parents 必须有占位向量+FLAT 索引, 内置 BM25+jieba 可用(不切备胎); 余: FLAT 对照留到 模块 06 |
| 05 | 混合检索与 RRF 融合 | ✅ 完成 | 2026-09-21: `retrieve.py`(`rrf_fuse` 纯函数 + `search` 编排)+ `contracts.py` 补 `ChildHit`/`RetrievedChunk`, 30 项单测、套件 137 项全绿; **真机冒烟**(两份语料 44 父块/44 子块): 中文 query 前三名全落中文语料、双路分数与手算逐条相等、同父合并正确; **顺带抓到并修掉 模块 04一个真缺陷**(jieba 空格 token → sparse 噪声票, 已加 stop 停用词 + 建表自检, 见 模块 04坑位 1) |
| 06 | ragas 评估 | ✅ 完成 | 2026-09-22: 走**独立评估环境** `eval/`(uv 项目, `override-dependencies` 只在该环境放宽 rich, 主环境零改动; 实测还须钉 `langchain-community<0.4`) → `evaluation.py`(模块名不叫 `evaluate.py`, 与 facade 函数同名会被 import 覆盖) + `EvalReport` + facade 三入口 + `cli evaluate`; 22 项单测 / 套件 200 项全绿; judge 走新接口 `llm_factory`, 嵌入自实现 `BaseRagasEmbedding` 适配器; 数据用 DuReader-Robust 抽样(500 篇语料 + 40 题, 自动校验答案在源段落内); **基线四指标: 上下文精度 0.8958 / 召回 0.9500 / 忠实度 0.9595 / 答案相关度 0.5015** |
| 07 | 接口设计与移植 | ✅ 完成 | 2026-09-21: 包内交付全部落地(`contracts.py` 补 `IngestReport`; `pipeline.py` 入库流水线; `__init__.py` facade 两入口(延迟 import, 无副作用); `cli.py` 四子命令; `store.py` 补 `list_docs`/`purge_stale`), 模块 32 项单测、套件 **178 项全绿**; CLI 四子命令真机冒烟通过; **步骤 0 收口**: 旧套件 6 failed/198 passed/33 errors → **2 failed/235 passed/0 errors**(余 2 条是远程沙箱不可达的外部依赖); 移植步骤 1~7 归里程碑 B |
| 里程碑 A | 评估基线 | ✅ 完成 | 2026-09-22: 500 篇语料入库(1m59s) → 40 题全量评估(约 32 分钟) → `eval_reports/eval_rag_v01_20260922-170437.{json,md}`: **上下文精度 0.8958 / 召回 0.9500 / 忠实度 0.9595 / 答案相关度 0.5015**(7 题有个别 NaN); 答案相关度偏低的主因已实证(兜底话术 / judge 只返 1 个反向问题 / 参考答案是短语), 见 [06.5-验收与依赖](./06.5-验收与依赖.md) §五 |
| 里程碑 B | 集成移植 | ✅ 完成(6/7, 步骤 3 暂缓) | 2026-09-22 一天内做完步骤 1/2/4/5/6/7: 打包落 `src/rag_v01/`、适配层 `tools/rag/kb_search.py`(工具名与 JSON 契约不变)、新旧双跑对比、retriever + API/CLI 同批切换、旧实现下线(仅留 `embed.py`)、ROADMAP §7 登记; **步骤 3(真实语料重灌)按用户决议暂缓**, 先用评估语料跑完整流程 |

## 使用规则

1. **每次开发前先读本文件**, 确认进行到哪个模块, 从第一个未勾选项继续;
2. 每个模块按 **阅读方案 → 编码 → 单测 → 验收** 四步推进, 四项全勾才算模块完成(验收以 [各分片](./README.md) §五 清单为准);
3. 教学模式: 业务代码由**用户亲手誊写**(智能体给完整代码 + 改动点清单); `tests/` 测试由智能体编写维护; 脚本类配置(pyproject / docker-compose / `.env` 段)由智能体代写;
4. 方案有出入先改 `docs/20-决策与方案/modules/rag_0.1/` 对应分篇, 再回到本文件勾选; 契约级变更(如 score 语义)按纪律在 ROADMAP §7 登记;
5. 红线: ~~不修改 `src/tools/rag/` 与 `docs/99-历史存档/` 下任何文件~~ —— **2026-09-22 用户授权**在里程碑 B 内切换 `agent/subagents/retriever.py` 的接线并下线旧实现(`src/tools/rag/` 的 `bm25.py`/`store.py`/`kb_search.py`/`split.py`/`parse.py` 及对应测试, `embed.py` 例外: 长期记忆在用); `rag_v01` 包**本身**仍不许 import `agent/`、`tools/`、`settings/`, 全同步(禁 async/await);
6. 依赖顺序提示: `contracts.py`(模块 07 的首个文件)是所有模块的类型依赖, 建议在模块 01 环境就绪后**先行誊写**, 再进入模块 02。

## 当前进行到

**模块 01~07 + 里程碑 A + 里程碑 B 步骤 1/2/4/5/6/7 全部完成(2026-09-22), 只剩步骤 3(真实语料重灌)等你提供语料** —— 新内核 `src/rag_v01/` 已接管线上检索(agent 的 `kb_search`、API `/knowledge`、REPL `/kb` 全走它), 旧 `tools/rag/` 只留 `embed.py`(长期记忆在用); 新旧双跑对比四项全升、精度 +0.206 明确超噪声带(见 [07.3-实现要点](./07.3-实现要点.md) §4.6.2)。
评估层落地:  独立评估环境 `eval/`(ragas 与主项目依赖互斥, 用 `override-dependencies` 只在该环境放宽 rich)、`evaluation.py`(两段式: 检索+最简生成 → 中间产物 jsonl → ragas 四指标 → json/markdown 报告)、`contracts.EvalReport`、facade 第三入口 `evaluate`、`cli evaluate`(带 `--limit` 试跑与 `--samples` 仅评估入口)。模块 22 项单测、套件 **200 项全绿**、ruff 干净。

**评估基线(里程碑 A)**: 数据用 **DuReader-Robust** 公开镜像抽样(源 14,520 段 → 抽 500 段当语料 + 40 条当测试题, 答案与出处现成, "参考答案在源段落内"由 `answer_start` 自动校验) —— 比让出题器现生成再人工校对省一整道工序。语料入库 500 篇耗时 1m59s; 40 题全量评估(约 32 分钟)产出 `eval_reports/eval_rag_v01_20260922-170437.{json,md}` —— **上下文精度 0.8958 / 上下文召回 0.9500 / 忠实度 0.9595 / 答案相关度 0.5015**(40 题里 7 题有个别 NaN); 报告 meta 记 ragas 版本 / judge 型号 / 检索参数快照 / 语料快照 / NaN 名单, 便于以后任何参数改动对着比。**答案相关度最低(0.5015)的成因已查实**: 兜底话术(「根据资料无法回答。」→ 忠实但相关度为 0)、judge 对「生成 3 个反向问题」每次只返 1 个、以及参考答案本身是短语 —— 三者的细节与数据在 [06.5-验收与依赖](./06.5-验收与依赖.md) §五。**已知局限**: 这份语料一段一个文件、段落中位 215 字 → 1 文档 = 1 父块, 父子分块的"多子块 / 跨页 / 同父去重"没被覆盖; 参考答案是短语, 上下文召回读数偏乐观。

**这次落地踩到并修掉的坑**(都记进 模块 06坑位): `langchain-community` 必须钉 `<0.4`(否则 `import ragas` 崩在 `vertexai`); 嵌入适配器要**同时**实现新旧两套方法名(基类要 `embed_text`, 而 `ResponseRelevancy` 实测调 `embed_query`); ragas 的 `total_tokens`/`total_cost` 是**方法**; judge 的 `max_tokens` 要给足以免结构化输出被截断; 评估环境里 torch 是 CUDA 版起不来 → CLI 改为按子命令懒加载, 评估才不再拖 docling。

**本轮补的三件收尾(2026-09-22, 全部实测)**:
1. **判读阈值量出来了**: 把同一份中间产物用「仅评估」入口评两遍(输入固定), 检索侧两轮 Δ=0, 而 **faithfulness Δ0.20 / answer_relevancy Δ0.09** —— 于是「指标差异小于 ~0.1 不下结论」这条有了实测依据(模块 06坑位 12c);
2. **整包可搬走有了实测**: 新增单测把 `rag_v01` 拷到临时目录、只把那份拷贝放进 `PYTHONPATH`(且换 cwd), 断言能导入、能用纯函数 —— [07.1-目标与决策](./07.1-目标与决策.md) §2.3 第一条硬保证从"grep 零命中"升级为"真搬走也能跑";
3. **`cli evaluate` 补了 `--label`**: 里程碑 B 的"新旧对比"必须能给旧系统起名(`--label tools_rag_v1`), 否则报告里不会出现并排对比表;
4. **发现并记录了一个前置约束**: `rag_v01` **运行时导不进来**(`uv run python -c "import rag_v01"` → `ModuleNotFoundError`, 只有 pytest 的 `pythonpath` 与 IDE 源码根暴露它) —— 所以里程碑 B 的**步骤 1(打包)是步骤 2(适配层)的硬前置**, 三个变体与代价已写进 [07.3-实现要点](./07.3-实现要点.md) §4.6.1。

**另补两项遗留验证(2026-09-22)**: 用仓库里那份真 pdf(`data/rag2_samples/pdf/补充.pdf`, 2026-09-23 c8 自 `src/rag_v01/data` 迁入)把模块 02 的「PDF 真件验证」与模块 03 的「真实 pdf 父块长度分布」做掉了 —— 15 页讲义解析 `SUCCESS`、156 条目**全部带页码**、标题与 heading_path 正确、清洗合并 57 条超短行; 父块 37 个中位 **84 字**、达标区间只有 **1/37**, 结论是「父块达标率是文档形态的函数」(节短的文档必然产出小父块, 不是 bug)。顺带量清一条运维事实: **PDF 解析会下载约 506MB 的 docling 模型**, 落点由 `HF_HOME` 决定(本次设成仓库内 `.hf_home`, 验完已删), 模型是进程级缓存所以同一进程第二篇只要 11s。

**复现性全量实测(2026-09-22, 40 题跑两遍)**: **检索侧达标** —— context_precision 0.8958→0.8932(Δ0.0026)、context_recall 0.9500→0.9500(Δ0.0000); **生成与判分侧不达标** —— faithfulness 0.9595→0.9118(Δ0.0477)、answer_relevancy 0.5015→0.4735(Δ0.0280), NaN 题数 7→10。两份报告都在 `eval_reports/`(第二份 label=`rag_v01_rerun`)。顺带做了个纯检索诊断: 同语料 20 条 query 下 **`ef` 64/96/128 三点结果完全一致(20/20)**, 而**候选深度 20→50 会让 11/20 条查询的 top-5 变化** —— 当前规模下调参该动候选深度与 top_k, 不是 ef(记进 模块 04/05)。

**下一步(剩下的一块): 里程碑 B(移植步骤 1~7)** —— 拷目录进 `hatch packages`、写 agent 侧 `kb_search_v2` 适配层(4.3 的 JSON 契约映射)、语料重灌、新旧双跑对比(用里程碑 A 的报告当对照)、切换、下线旧路径(步骤 6 会动 `src/tools/rag/` 与 `agent/`、`api/`、`settings/`)、ROADMAP §7 契约登记。**这一步涉及删旧代码与跨包改动, 需要单独一轮明确授权**(项目红线: 不修改 `src/tools/rag/` 与 `docs/99-历史存档/`); 步骤 0(收口重命名现场)已在模块 07 完成。

| 分篇 | 文档 | 状态 |
|---|---|---|
| 00 | [00-总览.md](README.md) | ✅ 定稿(2026-09-19) |
| 01 | [01-环境与依赖.md](README.md) | ✅ 定稿 |
| 02 | [02-文档解析与噪声处理.md](README.md) | ✅ 定稿 |
| 03 | [03-父子分块策略.md](README.md) | ✅ 定稿 |
| 04 | [04-嵌入与Milvus索引.md](README.md) | ✅ 定稿 |
| 05 | [05-混合检索与RRF融合.md](README.md) | ✅ 定稿 |
| 06 | [06-ragas评估.md](README.md) | ✅ 定稿 |
| 07 | [07-接口设计与移植方案.md](README.md) | ✅ 定稿 |

## 模块进度清单

### 模块 01 · 环境与依赖([模块 01](README.md))

**落地文件**: pyproject `rag2` extra(`dashscope` + `pymilvus`,实测只需这两个)/ `rag2-local`(离线备选)/ `docker-compose.milvus.yml`(已在仓库根,WSL 内起)/ `.env` 追加 RAG2_ 段; 无业务 `.py`。**备注**: ragas 因依赖冲突暂未入 extra,留到模块 06 定隔离方案(见 模块 01坑位 10 / 模块 06坑位 2)。

- [ ] **阅读方案**: 通读 模块 01; 记牢三个结论——milvus-lite 官方不支持 Windows、pymilvus>=2.5 是 BM25 Function 硬下限、`HF_ENDPOINT` 用于 docling 解析模型下载(embedding 主用百炼**多模态** API `qwen3-vl-embedding`, 走 **DashScope SDK**——OpenAI 兼容端点不支持图片输入; local BGE-M3 仅是纯文本离线备选)
- [x] **编码**: `uv sync --extra rag2`(需 `dashscope` + `pymilvus`); WSL 内 `docker compose -f docker-compose.milvus.yml up -d`; `.env` 追加 RAG2_ 段(11 键) —— 均已完成(2026-09-20, 智能体代写; 栈起在 WSL `~/milvus`, 数据卷 `~/milvus/volumes`)
- [x] **单测**: 本篇无业务代码, 以 [01.5-验收与依赖](./01.5-验收与依赖.md) §五冒烟替代 —— 6 条必做项全绿(依赖安装 / import / healthy / 19530 连通 / embed 1024 维 / judge 一问一答 / 重启持久); 2 条可选项(图片向量冒烟、local 备选)未做
- [x] **验收**: [01.5-验收与依赖](./01.5-验收与依赖.md) §五执行记录已回填(2026-09-20); ragas 未装属已知阻塞, 见 [01.4-坑位](./01.4-坑位.md) 坑位 10 / [06.4-坑位](./06.4-坑位.md) 坑位 2

### 模块 02 · 文档解析与噪声处理([模块 02](README.md))

**落地文件**: `contracts.py`(解析侧 `ParsedDoc`/`ParsedItem`, 首次落) + `config.py`(`RAG2_` 读取) + `parsers/` 包(`__init__.py` 分派 / `common.py` 遍历 / `images.py` 图片落盘 / `pdf.py` / `docx.py` / `md.py`) + `clean.py`(用户誊写); 样例语料 `data/rag2_samples/`(智能体已造); `tests/` 下解析与清洗单测(智能体)。

- [x] **阅读方案**: [02.5-验收与依赖](./02.5-验收与依赖.md) §五"环境自检"已在开发机实测(结论见该节"实测结论"); 标【待验证】的 API 全部定稿(另补两条: md 图片引用取不到、标题 heading_path 必须在弹栈后算)
- [x] **编码**: 解析层按格式拆包落地——`parsers/__init__.py`(分派) + `common.py`(遍历/标题栈/表格/ParseError) + `images.py`(落盘/占位/图注) + `pdf.py` / `docx.py` / `md.py`(格式专属 option) + `contracts.py` + `config.py` + `clean.py`(五条规则按定稿顺序)
- [x] **单测**: `tests/test_parse.py`(9) + `tests/test_clean.py`(12) = **21 项全绿**(11s, 不联网、不下模型); 覆盖 doc_id 内容寻址/后缀白名单/标题栈/页眉页脚剔除/去重/超短行/乱码告警/真格式 md+docx 冒烟
- [x] **验收**: md/docx 已通(标题路径、表格整块、图片落盘、清理统计); **PDF 真件 2026-09-22 已验**(`data/pdf/补充.pdf` 15 页: 解析 SUCCESS 无警告、156 条目**全部带页码**、标题与 heading_path 正确、清洗合并 57 条超短行; 实测数字见 [02.1-目标与决策](./02.1-目标与决策.md) §〇); ② 损坏文件进 `IngestReport.failed` —— [07.3-实现要点](./07.3-实现要点.md) 的 ingest 落地后已覆盖(单测断言失败隔离); ③ `RAG2_IMAGE_DESC` 可选开关本期未实现(图片语义由 [04.3-实现要点](./04.3-实现要点.md) 多模态向量承担)。**未覆盖**: 该 pdf 没有表格与插图, "PDF 表格序列化 / 图片落盘 / 扫描件 OCR"仍只有单测与样例 docx 覆盖

### 模块 03 · 父子分块策略([模块 03](README.md))

**落地文件**: 分块包 `src/rag_v01/chunk/`(`__init__.py` 编排 / `common.py` 共享件 / `parents.py` 父块侧 / `children.py` 子块侧; 子块侧依赖 langchain-text-splitters) + `contracts.py` 追加 `Chunk`/`ParentChunk`/`ChildChunk`(九字段 + 透传 `image_path`); `tests/test_chunk.py`(21 项)。

- [x] **阅读方案**: 通读 模块 03; 三条硬规则——父块绝不跨节(宁小勿跨)、表格整块不切、子块重叠 50 字符封顶且对齐句子边界(2026-09-21)
- [x] **编码**: 包 `chunk/` 四文件 —— `__init__.py` 只编排 `split(doc, cfg, *, clock)`; 父块侧 `parents.py`(`aggregate` 规则 A/B/C + 原子块独占 + 空壳标题块后处理 `absorb_heading_only` + `join_units` 拆标题前缀/正文/页码表 + `block_spans` 退化切分); 子块侧 `children.py`(`split_pieces` 库切分 + 分隔符回搬 + 起点修正、`add_overlap`/`_overlap_tail` 句界重叠、`build_children` 装配九字段); 共用小件 `common.py`。子块 `page_no` 按单元偏移回查, 父块面包屑取开块单元
- [x] **单测**: `tests/test_chunk.py` **21 项全绿**(模块合计 **42 项**, 10s, 无 fake): 三条父块规则、退化切分、表格/图片原子性、子块上限与重叠 40~50、中文句界(引号/小数/省略号)、九字段名钉死、ID 链路、确定性、跨页页码、空壳标题块三条边界
- [x] **验收**: [03.3-验收与依赖](./03.3-验收与依赖.md) §五清单逐条勾选并回填实测数字(长文 14,465 字符: 父块达标率 10/10、上限 1778、子块 max 496、重叠 38 组全在 40~50、表格子块 1 个、切两遍一致); **真 pdf 父块分布 2026-09-22 已测**(15 页讲义: 37 父块中位 84 字、达标区间 1/37、子块 49 个全部挂到现存父块; 结论「达标率是文档形态的函数」见 [03.3-验收与依赖](./03.3-验收与依赖.md) §五)

### 模块 04 · 嵌入与 Milvus 索引([模块 04](README.md))

**落地文件**: `embed.py` / `store.py`(用户誊写); `tests/` 下 embed 与 store 单测(智能体)。

- [x] **阅读方案**: 模块 04读完; 两条前置实测都在写代码前做了(见下), 结论是**不需要** rank_bm25 备胎
- [x] **编码**: `embed.py`(公共件 `_l2_normalize`/`_to_data_uri`/`_check_dim` → `_ApiBackend` → `_LocalBackend` + 门面 `get_embedder`/`embed_documents`/`embed_images`/`embed_query`/`embedding_dim` → `embed_chunks` 分组拼回) 与 `store.py`(建表侧 `_child_schema`/`_child_index`/`_parent_schema`/`_parent_index`/`ensure_collections`/`_check_children`/`load`/`flush`; 读写侧 `Hit`/`ParentRow`/`upsert_parents`/`upsert_children`/`delete_doc`/`dense_search`/`sparse_search`/`get_parents`), 用户亲手誊写、智能体逐步给码 + 每步实测(教学口径: 按 5 步给码, 每步给完 ruff 校验过再交付)
- [x] **单测**: `tests/test_embed.py` **32 项** + `tests/test_store.py` **29 项**(模块合计 **61 项**, 套件 103 项全绿): embed 侧 monkeypatch `MultiModalEmbedding.call`(批次数 45→[20,20,5] / 12图→[5,5,2]、`index` 乱序归位、逐条顺序映射、维度自检文案、图片 Base64 形态、`embed_chunks` 分组与降级、local 注入假 ST); store 侧 FakeClient(payload 无 sparse、`page_no` 哨兵、metadata 键集、超长跳过告警、数量不一致抛错、分批、filter 字符串、三原语参数、`_hit` 兜底)
- [x] **验收**: [04.5-验收与依赖](./04.5-验收与依赖.md) §五清单逐条勾选并回填**真机执行记录**(真 Milvus 2.6.0 + 真百炼多模态 embedding): 建表幂等(`created_timestamp` 不变)、索引与 Function 自检(HNSW M=16/efC=200/COSINE、sparse BM25、`text_bm25`)、`run_analyzer.tokens` 与本地 jieba 逐 token 一致、同批 upsert 幂等、dense 0.9093 / sparse 4.8875 各命中目标子块、`delete_doc` 两表清零、`ensure_collections(dim=768)` 报可读错、跨模态 0.7444 > 0.2282; **两处定稿修正回填 [04.3-实现要点](./04.3-实现要点.md)**(parents 占位向量 + FLAT + INVERTED; BM25 不切备胎); **未做**: FLAT 对照(留到 [06.5-验收与依赖](./06.5-验收与依赖.md) 评估期)

### 模块 05 · 混合检索与 RRF 融合([模块 05](README.md))

**落地文件**: `retrieve.py`(用户誊写); `tests/` 下检索单测(智能体)。

- [x] **阅读方案**: 模块 05读完; RRF 公式、截断后再同父去重、错误语义分层、ef ≥ limit 四条都落到代码里
- [x] **编码**: `contracts.py` 追加 `ChildHit` / `RetrievedChunk`; `retrieve.py` = `FusedChild`(内部结构)+ `rrf_fuse`(名次从 1 起、同分按 chunk_id、`k`/`top_k` 必填由 config 传)+ `search`(两路 top-20 → 融合 → `get_parents` 去重点查 → 同父合并 + 父块缺失跳过记 warning + `page_no` 哨兵还原); 用户分 2 步亲手誊写、智能体每步先过 ruff 再交付
- [x] **单测**: `tests/test_retrieve.py` **30 项**: 手算 `1/61 + 1/63`、单路为空退化、两路皆空 `[]`、双路同条不重复、并列按 chunk_id 且与输入顺序无关、round 在排序之后、透传字段取先见到的那条、同父合并(3 子块 → 1 条 + 3 明细)、名次连续、父块缺失跳过告警、`page_no=-1 → None`、`top_k=0` **在 embedding 之前**抛、连接异常不被吞成 `[]`、两个契约的字段名钉死
- [x] **验收**: [05.5-验收与依赖](./05.5-验收与依赖.md) §五清单全过(见该分片执行记录)。真机集成冒烟(真 Milvus + 真 embedding, 两份语料共 44 父块/44 子块): 中文 query 前三名全落在中文语料、image/table 块能被命中、双路分数与手算逐条相等、`rrf_rank` 连续、父块不重复、`Table of Contents` 4 条同父合并成 1 条; **顺手抓到并修掉 [04.3-实现要点](./04.3-实现要点.md) 的一个真缺陷**(jieba 把空格当 token → sparse 噪声票与真信号等值, 见 [04.4-坑位](./04.4-坑位.md) 坑位 1/[04.5-验收与依赖](./04.5-验收与依赖.md) §五与下方变更登记); 套件 137 项全绿

### 模块 06 · ragas 评估([模块 06](README.md))

**落地文件**: `evaluation.py`(原计划名 `evaluate.py`, 因与 facade 函数同名而改) / `contracts.py`(`EvalReport`) / `__init__.py`(第三入口) / `cli.py`(`evaluate` 子命令); 独立环境 `eval/`(pyproject + uv.lock, 智能体代写); `tests/test_evaluate.py`(22 项, 智能体)。数据: `data/eval_dureader/corpus/`(500 篇) + `data/eval_qa_v1.jsonl`(40 题)。

- [x] **阅读方案**: 模块 06读完; 两段式(先落中间产物再喂 ragas)、父块口径、四指标口径名、NaN 统计、成本控制(先 limit=5 试跑)全部落到代码
- [x] **环境**: 独立 uv 项目 `eval/` —— `uv add --directory eval ragas "langchain-community<0.4"` + `[tool.uv] override-dependencies = ["rich>=14,<15"]` + 路径依赖 `taskforce[rag2]`; 主 `pyproject.toml`/`uv.lock` 一字未动(实测隔离解析与安装); 见 [06.1-目标与决策](./06.1-目标与决策.md) §2.7
- [x] **编码**: `evaluation.py` 数据面(jsonl 读写与校验 / `make_sample` 父块保序组 contexts / `simple_answer` 固定 prompt / `debug_of` 命中明细)+ ragas 面(`llm_factory` 装配 judge / `build_metrics` 四指标 / `BaseRagasEmbedding` 适配器 / `run_config` 带 seed)+ 报告面(json + markdown, meta/NaN/对比表); ragas 与 openai 的 import 全在函数体内
- [x] **单测**: `tests/test_evaluate.py` **22 项**(jsonl 读写与行号报错、测试集字段校验、`make_sample` 保序与 debug、固定 prompt 与 temperature=0、`summarize` 的 NaN 语义、指标名映射、报告 json/markdown/对比表、Milvus 缺失容错、`run_eval` 两条入口、facade 回归、`cli evaluate` 参数与输出); 缺 ragas 时的指引也在单测里
- [x] **验收**: [06.5-验收与依赖](./06.5-验收与依赖.md) §五清单(见该分片执行记录); `cli evaluate` 真机跑通(真 Milvus + 真 embedding + 真 judge), 报告落 `eval_reports/`

### 模块 07 · 接口设计与移植方案([模块 07](README.md))

**落地文件**: `contracts.py`(补 `IngestReport`)/ `pipeline.py`(原 `ingest.py`, 改名原因见下)/ `__init__.py`(facade)/ `cli.py`, 加 `store.py` 的运维面 `list_docs` / `purge_stale`(用户誊写); `tests/test_pipeline.py`(13 项)+ `tests/test_cli.py`(19 项, 含 facade 与子进程空跑)(智能体)。

- [x] **阅读方案**: 模块 07读完; 三条硬保证、§4.5 旧接口对照表、§4.6 移植清单都落到代码与本次验收里; `evaluate` 按方案 A **先不暴露**(ragas 未就绪, 不留占位死代码)
- [x] **编码**: 按 7 步给码(契约 → store 运维面 → 流水线 → facade → cli → 步骤 0 → 验收), 每步先过 ruff 再交付; **4 处与文档骨架的出入记进 [07.3-实现要点](./07.3-实现要点.md) §4.7**: ① 流水线模块改名 **`pipeline.py`**(与 facade 函数 `ingest` 同名会让子模块 import 后**把函数换成 module** —— 第二次调用才 `TypeError`, 单测留了回归用例); ② facade 的子模块 import 放进函数体内(`import rag_v01` 因此不拉起 docling/pymilvus); ③ `search(top_k=None)`; ④ `ingest` 补"同源旧版本清理"`purge_stale`(文件改过重灌不留新旧两份)
- [x] **单测**: `test_pipeline.py`(文件展开/source 计算/单文件失败隔离/计数/flush 时机/notes 汇总/purge 收到新 doc_id)+ `test_cli.py`(USAGE 与退出码/四子命令输出/`--top-k` 两种位置/空结果/错误路径/facade `__all__`/回归用例/**子进程空跑验无副作用**); 模块合计 32 项, 套件 178 项
- [x] **验收**: [07.4-验收与依赖](./07.4-验收与依赖.md) §五逐条(两入口可导入与 `__all__`、子进程空跑 heavy=[]、零项目依赖 grep 零命中、零 async grep 零命中、CLI 四子命令真机冒烟无 GBK 乱码、tests 无 docker/Milvus 全绿); **步骤 0 已完成**(只改 `tests/` 5 处 monkeypatch 字符串, 不碰红线目录, 旧套件恢复全绿); 余"适配层 JSON 契约"属里程碑 B

**改名说明(重要)**: 流水线模块最终叫 `pipeline.py` —— 原计划的 `ingest.py` 与 facade 的公开函数 `ingest` 同名, Python 在 import 子模块时会把父包上的 `ingest` 属性从函数换成模块对象, 于是"第一次调用正常、第二次 `TypeError: 'module' object is not callable`"。公开 API 名仍是 `ingest`(模块 07定稿)。

## 里程碑 A · 评估基线(依赖模块 06; 先于移植——移植步骤 4 的同集对比靠它)

- [ ] 出题: `TestsetGenerator` + `default_query_distribution` 从语料生成 ~40 条原始题(一次性脚本, 放 `src/rag_v01/` 之外)
- [ ] 人工校对五查(出处 / 超纲 / multi-hop 可答性 / 问法 / 去重), `reviewed=true` 另存 `eval_qa_v1.jsonl`(30~50 条)
- [ ] `limit=5` 试跑, 实测 judge token 账单与四指标形态
- [ ] 全量跑通: `reports/` 下产出 json + markdown(meta 含 ragas 版本 / judge 型号 / embedding 型号与模式 / 检索参数快照 top-20、top-5、k=60 / contexts 口径)
- [ ] 复现性: 同配置重跑一次, 四指标均值波动 ±0.02 量级
- [ ] 冻结评估配置: `RAG2_DO_OCR` / `RAG2_IMAGE_DESC` / 生成 prompt 版本写进报告 meta(冻结后才可作基线)

## 里程碑 B · 集成移植([07.3-实现要点](./07.3-实现要点.md) §4.6; 前置: 里程碑 A 的测试集与评估链路)

- [ ] 步骤 0: 收拾旧目录半途重命名现场(目录 / import 与 monkeypatch 字符串二选一收干净)
- [ ] 步骤 1: 整目录拷贝 `src/rag_v01/` 到目标位置并重命名包(确认 hatchling 打包配置覆盖、`uv sync` 后可 import)
- [ ] 步骤 2: agent 侧新写 `kb_search_v2` 适配层(doc_id / filename / seq / content / score + 截断 500 / top_k 钳 1-10); API/CLI knowledge 路由换等价方法面
- [ ] 步骤 3: 语料不迁移, 对新系统全量 `ingest`(旧 pgvector 库全程不动, 作回滚依托)
- [ ] 步骤 4: 并行双跑: 旧 `kb_search` 与 `kb_search_v2` 用同一测试集跑 ragas 对比, 产出并排对比报告(公平性清单逐项打勾)
- [ ] 步骤 5: 指标达标后切换——retriever 装配处(`retriever.py:94`)与 API/CLI 路由同批换新
- [ ] 步骤 6: 下线旧路径(bm25 / store / kb_search / split / parse 与对应测试); `embed.py` 例外——保留原文件或把长期记忆(`settings/db/store.py:14`)改指新 embed
- [ ] 步骤 7: ROADMAP §7 契约登记(score 语义、kb_search JSON 契约若有变更)

## 里程碑 B 进度(2026-09-22 起)

| 步骤 | 状态 | 说明 |
|---|---|---|
| 1 打包登记 | ✅ 完成 | 落点 **`src/rag_v01/`**(不是 `src/tools/rag_v01`: `packages` 里已有 `src/tools` → 会打包成 `tools.rag_v01`)。`packages` 加 `src/rag_v01`、删 `pythonpath = ["src/new_module"]`、per-file-ignore 与 `tests/conftest.py`/`test_cli.py` 的路径假设同步; 旧副本 `src/new_module/` 已删(删前逐文件 sha256 比对: 40/40 一致, 仅两处刻意改的测试路径不同)。验证: `import rag_v01` → `src/rag_v01/__init__.py`; `uv run pytest src/rag_v01/tests -q` → **203 passed**; `ruff check src/rag_v01` 干净。**坑**: `uv sync`(不带 `--extra rag2`)会把 pymilvus/dashscope 卸掉, 于是 `test_store.py`/`test_embed.py` 整文件 skip(129 passed/2 skipped) —— 要 `uv sync --extra rag2` |
| 2 agent 侧适配层 | ✅ 完成 | 落点是 `src/tools/rag/kb_search_v2.py`(不是骨架写的 `agent/subagents/` —— 工具属于 `tools/`), 工具名保持 `kb_search`(提示词写死了它), 单测 8 项; 下线旧码后改名回 `kb_search.py` |
| 3 语料重新入库 | ⏸ 暂缓 | 无真实语料输入, 先用现有评估语料(500 段)跑完整流程; 要切个人语料时从旧库导出 source 清单再 `ingest()` |
| 4 新旧双跑对比 | ✅ 完成 | 两侧同语料同测试集, 只经中间产物 jsonl 交换(旧系统那侧的一次性脚本用完即删); 数字见 [07.3-实现要点](./07.3-实现要点.md) §4.6.2 |
| 5 切换 `retriever.py` | ✅ 完成 | import + API/CLI 路由 + 测试注入点同批切 |
| 6 下线旧路径 | ✅ 完成 | 删 `parse/split/bm25/store/kb_search/cli.py` 与 4 个旧测试; `embed.py` 保留(长期记忆在用), 覆盖搬到 `tests/test_rag_embed.py` |
| 7 契约登记 ROADMAP §7 | ✅ 完成 | `kb_search` JSON 契约未变; API 三处变更(doc_id 内容寻址 / created_at 恒 null / delete 404)已登记 |

## 整体完成口径

- 每模块四类条目全部勾选 + 两个里程碑全部勾选 = 新系统落地完成;
- 移植完成 = 步骤 0~7 全勾, 且主线 `uv run pytest -q` 与 `uv run ruff check .` 全绿。

## 变更登记

| 日期 | 变更 |
|---|---|
| 2026-09-19 | 00~07 方案文档定稿(只产文档, 未动任何代码); 本文件建立, 进度指针停在模块 01"阅读方案" |
| 2026-09-20 | 定稿口径更新: embedding 改走百炼 API(`qwen3.7-text-embedding-flash`, 1024 维, OpenAI 兼容), local BGE-M3 降为离线备选并拆出 `rag2-local` extra; Milvus 部署确定为 WSL 内 docker 暴露 19530; 模块 01/04改写, 00/02/03/06/07 与本文件同步 |
| 2026-09-20 | embedding 再定稿: 换多模态 qwen3-vl-embedding(文本/图片同空间, DashScope SDK, 维度仍锁 1024, 顶层参数 `dimension=1024` 实测生效), 图片块进 dense 真向量; rag2 extra 增 dashscope |
| 2026-09-20 | 模块 01 落地实测(开发机): rag2 extra 定为 `dashscope`+`pymilvus`(ragas 因 rich 冲突未入, 见 模块 01坑位 10 / 模块 06坑位 2); `docker-compose.milvus.yml` 已入仓库根并在 WSL 起好(19530, server 2.6.0, 三容器 healthy; minio 改 quay.io 镜像); `.env` 补全 RAG2_ 段; 冒烟: import / Milvus 连通 / embed 1024 维 / judge 问答 全绿 |
| 2026-09-20 | 代码目录改名 `rag_0.1` → **`rag_v01`**(点号不能当包名): 包内改相对导入、测试改 `from rag_v01... import`; 暴露方式 = pyproject `pythonpath = ["src/new_module"]` + IDE 源码根(故意不进 hatch packages); 模块 02 的 `parsers/` 包 + `clean.py` + 21 项单测落地, 文档与记忆同步 |
| 2026-09-21 | 模块 03 落地: `chunk.py`(父块聚合 + 子块递归切分 + 句界对齐重叠, 纯标准库) + `contracts.py` 追加 `Chunk`/`ParentChunk`/`ChildChunk`(`char_len` 由 `text` 派生; 透传字段 `image_path` 不入九字段) + `tests/test_chunk.py`(21 项); 模块 03补三节(§3.2 接口、§4.6 坑位四"空壳标题块"、§五实测数字), §四加"骨架 vs 落地"对照表 |
| 2026-09-21 | 模块 03 重构: 单文件 `chunk.py` 拆成包 `chunk/`(`__init__` 编排 / `common` 共享件 / `parents` 父块侧 / `children` 子块侧, 跨模块调用去下划线); 子块切分由手写递归器改为 **langchain `RecursiveCharacterTextSplitter`**(分隔符末尾空串、分隔符回搬、起点修正、无 slack 容差四个坑记进 [03.2-契约与实现](./03.2-契约与实现.md) §4.7), 重叠仍自己写(库按整片量化, 落 32~41 或 ~76); 父块装配修正"标题前缀只贴第一条"(退化多条父块时曾重复 N 遍); 42 项单测全绿 + 长文验收 10/10; 教学模式下由用户亲手誊写、智能体逐步骤给码并实测 |
| 2026-09-21 | 模块 04 落地(第一步): 真机探针先于编码, 把 [04.4-坑位](./04.4-坑位.md) 标"待验证"的风险点实测掉 —— **BM25 Function + jieba 可用**(`run_analyzer.tokens` 与本地 `jieba.lcut_for_search(HMM=True)` 逐 token 一致; 不写 `sparse` 能入库; sparse 检索命中 4.8875) → [04.1-目标与决策](./04.1-目标与决策.md) §2.5 的 rank_bm25 备胎**不需要**; dense HNSW + COSINE 正常; delete filter + flush 可见性正常; **发现 Milvus 硬约束**: collection 必须至少一个向量字段(1100)、每个向量字段必须有索引(65535)、向量字段不支持 nullable(1100)、维度下限 2 → [04.1-目标与决策](./04.1-目标与决策.md) §2.3/[04.3-实现要点](./04.3-实现要点.md) §4.2 的 parents schema 修正为"占位 `dense`(dim=2) + FLAT + `doc_id` INVERTED", [04.3-实现要点](./04.3-实现要点.md) §4.3 骨架注释同步 |
| 2026-09-21 | 模块 05 落地: `retrieve.py`(`FusedChild` + `rrf_fuse` 纯函数 + `search` 编排: 两路 top-20 → RRF k=60 → `get_parents` 点查 → 同父去重 → `list[RetrievedChunk]`) + `contracts.py` 补 `ChildHit`/`RetrievedChunk`(30 项单测); 三处与 模块 05骨架的出入记进 §4.6(`k`/`top_k` 不给默认值、`search(top_k=None)`、`rrf_rank` 取最终结果名次)、§3.2 那句有歧义的"融合槽位"措辞已改; 真机集成冒烟(中英文两份语料)全过 |
| 2026-09-21 | **修正 [04.3-实现要点](./04.3-实现要点.md) 一个真缺陷(模块 05 冒烟抓到)**: jieba analyzer 把空白切成 token(实测占语料 token 44%), 带空格的 query 让 sparse 路返回一大批无关子块且分数近乎相同 —— RRF 只吃名次, 噪声票与真信号票等值, 融合被噪声左右。修法: `text` 的 `analyzer_params` 加 `stop` filter(138 个停用词; 实测该 tokenizer 只支持 `stop`, `removepunct`/`length`/`alphanumonly`/`lowercase` 全报 `unsupport filter type`), 新增 `_analyzer_params()` / `_ANALYZER_STOP_WORDS` / `_check_analyzer()`(建表自检第三道, 拦旧表); children/parents 已 drop 重建并重灌; [04.3-实现要点](./04.3-实现要点.md) §4.2/§4.3/[04.4-坑位](./04.4-坑位.md) 坑位 1·3/[04.5-验收与依赖](./04.5-验收与依赖.md) §五 同步(验收口径改为"与本地 jieba 的差集 ⊆ 停用词表") |
| 2026-09-22 | **模块 06 + 里程碑 A 落地**: 评估环境选定**独立 uv 项目 `eval/`**(`override-dependencies = ["rich>=14,<15"]` 只在该环境生效, 主 `pyproject.toml`/`uv.lock` 一字未动; 实测还须钉 `langchain-community<0.4`, 否则 `import ragas` 崩在已移除的 `chat_models.vertexai`); `evaluation.py`(模块名不叫 `evaluate.py` —— 与 facade 公开函数同名会被 import 覆盖, 同 `pipeline.py` 的规则) + `EvalReport` + facade 三入口 + `cli evaluate`; judge 走新接口 `llm_factory`(不用已弃用的 langchain Wrapper), 嵌入自实现 `BaseRagasEmbedding` 适配器(基类强制 sync+async, 且 ragas 内部仍调旧名 `embed_query`); CLI 改为按子命令懒加载; 22 项单测 / 套件 200 项全绿 |
| 2026-09-22 | **评估基线(里程碑 A)**: 数据源定 **DuReader-Robust** HF 镜像(单 JSON 18.5MB、无脚本、无需令牌), 抽 500 段当语料 + 40 条当题; 语料入库 1m59s; 40 题全量评估产出 `eval_reports/` json+markdown 报告; 原始数据与派生语料因学术研究许可**不进 git**; 已知局限(段落短 → 1 文档 1 父块, 多子块能力未覆盖)写进 [06.2-契约与数据流](./06.2-契约与数据流.md) §3.2 |
| 2026-09-22 | **基线数字落定**: 40 题四指标 = 上下文精度 **0.8958** / 上下文召回 **0.9500** / 忠实度 **0.9595** / 答案相关度 **0.5015**(7 题个别 NaN); 报告 `eval_reports/eval_rag_v01_20260922-170437.{json,md}`; 过程两次事故(都不是逻辑错, 已记进 [06.5-验收与依赖](./06.5-验收与依赖.md) §五): ① 第一次全量跑到最后崩在 `total_cost()`(已改容错 + 回归用例); ② judge 账户余额不足导致 39/40 题 NaN, 充值后重跑 |
| 2026-09-22 | **复现性实测(重要)**: 同 5 题同配置跑两轮 —— 检索侧逐题一致(两轮精度/召回都 1.0), 但忠实度 0.3333↔0.8333、相关度 0.1605↔0.5026, 根源是 5 题里 3 题的**生成答案**在 `temperature=0` 下都不一样。结论: 噪声来自 LLM 两端而非检索; 比参数改动要用「仅评估」入口固定同一批生成结果, 差异 <0.05 不下结论(模块 06坑位 12) |
| 2026-09-22 | 评估收尾三件: ① 量出**judge 判读阈值**(同输入评两遍: 检索侧 Δ=0, faithfulness Δ0.20 / answer_relevancy Δ0.09 → 差异 <0.1 不下结论); ② 新增**整包可搬走**单测(拷到别处 + 只给那份拷贝 PYTHONPATH 仍可导入); ③ `cli evaluate` 补 `--label`(新旧对比靠它); 另记录一条前置约束: `rag_v01` 运行时不可导入 → 里程碑 B 步骤 1(打包)是步骤 2 的硬前置 |
| 2026-09-22 | **复现性全量实测 + 调参诊断**: 40 题重跑两遍 → 检索侧 Δ≤0.003(达标)、生成/判分侧 Δ0.028~0.048(不达标, NaN 7→10); 同语料下 `ef` 64/96/128 结果一致(20/20)、候选深度 20→50 改变 11/20 条 top-5 → 调参动候选深度不动 ef |
| 2026-09-22 | **里程碑 B 步骤 1 打包登记(变体 A 落地)**: `src/new_module/rag_v01/` → **`src/rag_v01/`**(与其它六个包同深度; 骨架写的 `src/tools/rag_v01` 会被 `packages = ["src/tools"]` 打包成 `tools.rag_v01`, 是错的); `packages` 加一行 + 删 `pythonpath` + per-file-ignore/测试路径假设同步; 删前逐文件 sha256 比对确认副本完整; 旧目录已删。验证 `import rag_v01` 解析到新位置、新包单测 **203 passed**、ruff 干净; 顺带记下 `uv sync` 不带 `--extra rag2` 会卸掉 pymilvus/dashscope(整套 store/embed 测试变整文件 skip) |
| 2026-09-22 | **里程碑 B 步骤 2/4/5/6/7 全部落地(步骤 3 语料重灌按用户决议暂缓)**: 适配层 `tools/rag/kb_search_v2.py` → 下线旧码后改名回 `kb_search.py`(工具名与 JSON 契约一字未改, 所以提示词与 `_collect_hits` 都没动); `retriever.py` + API/CLI knowledge 路由同批切到 `rag_v01`; 删 `tools/rag/{parse,split,bm25,store,kb_search,cli}.py` 与 4 个旧测试, `embed.py` 保留(长期记忆在用, 覆盖搬到 `tests/test_rag_embed.py`); ROADMAP §7 + 前端 API-CONTRACT §2.3 同步。**新旧双跑对比(40 题同语料)**: 旧系统 精度 0.6896/召回 0.9000/忠实度 0.8681/相关度 0.4774 → 新系统 **0.8958/0.9500/0.9595/0.5015**, 四项全升但只有精度(+0.206)明确超出噪声带(阈值见 模块 06坑位 12c)。主线测试 400 passed / 2 failed(远程沙箱不可达), `src/rag_v01/tests` 203 passed, ruff 干净 |
| 2026-09-22 | **补两项遗留验证**: 真 pdf(`补充.pdf`, 15 页)跑通解析与切块 —— 解析 SUCCESS、页码全覆盖、标题正确、耗时(首次 72.76s 含下载 506MB 模型 / 之后 11s); 父块 37 个中位 84 字、达标 1/37 → 「父块达标率是文档形态的函数」; 模型缓存设 `HF_HOME=.hf_home`(仓库内)并在验完后删除, `.hf_home/` 已进忽略列表 |
| 2026-09-21 | 模块 07 落地: `contracts.py` 补 `IngestReport`; 新增 `pipeline.py`(逐文件 parse→clean→chunk→embed→store + 目录展开 + 单文件失败隔离 + 同源旧版本清理 + 收尾 flush)、`pipeline.py` 的 facade 两入口(子模块延迟 import, `import rag_v01` 不拉重依赖)、`cli.py`(ingest/search/list/delete, 入口 reconfigure utf-8, E402 已进 pyproject per-file-ignores)、`store.py` 补 `list_docs`/`purge_stale`; 32 项单测、套件 178 项; CLI 四子命令真机冒烟全过; 与文档骨架的 5 处出入记进 [07.3-实现要点](./07.3-实现要点.md) §4.7 |
| 2026-09-21 | **命名冲突真 bug 修正**: 流水线模块原计划叫 `ingest.py`, 与 facade 公开函数 `ingest` 同名 —— 子模块被 import 后 Python 会把父包的 `ingest` 属性从函数换成 module, 于是第一次调用正常、第二次 `TypeError: 'module' object is not callable`; 已改名为 `pipeline.py`(公开 API 名不变), 单测留回归用例。另: `tests/` 5 处 monkeypatch 字符串从 `tools.rag_0.1.kb_search` 退回 `tools.rag.kb_search`(模块 07步骤 0), 旧套件 6 failed/33 errors → 0 errors |
| 2026-09-21 | 模块 04 落地(第二步): `embed.py` + `store.py` 由用户按 5 步誊写、智能体每步先过 ruff 再交付并补单测; embed 侧新增 `embed_chunks`(按 `chunk_type` 分组 + 按原下标拼回 + 无本地图降级 + `supports_images` 能力声明), `Hit` 补 `metadata` 透传(展示图片路径与来源不用回表); store 侧超长 `text`(>8192 字节)**跳过并告警**不截断; 真机验收清单全过(含跨模态 0.7444 vs 0.2282: 图像与相关文本确实同空间); 模块 61 项单测 / 套件 103 项全绿; [04.2-契约与数据流](./04.2-契约与数据流.md) §3.2/[04.3-实现要点](./04.3-实现要点.md) §4.1/§4.2/§4.5/[04.4-坑位](./04.4-坑位.md) 坑位 2·3·4·7·8·9·12/[04.5-验收与依赖](./04.5-验收与依赖.md) §五 全部回填 |
