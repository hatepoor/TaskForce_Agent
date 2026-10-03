# TaskForce 文档索引

> 用法:先在本索引定位,再深入对应文档。**新增文档/目录先在此登记再建文件**(与 AGENTS.md 文档表纪律同源);旧方案被取代时就地加『状态+日期+继任链接』横幅,不删除。
> 最后更新:2026-09-28

## 按任务找文档

| 我要… | 去看 |
|---|---|
| 了解项目是什么、卖点在哪 | [README](../README.md)、[design/DESIGN.md](design/DESIGN.md)(方案定稿)、personal/(简历与演示) |
| 动手写代码(进度与顺序) | [dev/TODO.md](dev/TODO.md) → [dev/ROADMAP.md](dev/ROADMAP.md)(进度唯一事实源) → [dev/NN-xxx/DEV.md](dev/)(模块开发文档) |
| 看现行模块方案(唯一口径) | [new_module/rag_0.1/](new_module/rag_0.1/)、[new_module/plan_0.1/](new_module/plan_0.1/)、[new_module/agent_opt_0.1/](new_module/agent_opt_0.1/)(智能体框架优化:00 报告 + 01~03、05 方案 + TODO) |
| 查某个设计为什么这样定 | [adr/](adr/)(0001~0012,**编号被 src 代码注释引用,文件不可改名**) |
| 排查报错 / 避免重复踩坑 | [troubleshooting/](troubleshooting/)(现象/根因/解决,按模块组织) |
| 学 RAG 全链路 / 备面试 | [guide/rag/](guide/rag/)(rag_v01 讲解 9 篇 + interview 面试 6 篇,两级索引) |
| 看架构与提示词成文设计 | [design/ARCHITECTURE.md](design/ARCHITECTURE.md)、[design/PROMPT-DESIGN.md](design/PROMPT-DESIGN.md)(§编号被 src 注释引用) |
| 看前端设计与契约 | [../dev/front/docs/](../dev/front/docs/)(API-CONTRACT 为契约唯一事实源) |
| 查术语定名 | [../CONTEXT.md](../CONTEXT.md)(仓库根,代码命名与沟通必须用其术语) |

## 目录总览

| 目录 | 内容 | 状态 |
|---|---|---|
| `adr/` | 架构决策记录 0001~0012,含被否决项(勿"修复"有意为之的设计) | 活跃 |
| `dev/` | 12 个模块目录(各含 DEV.md)+ ROADMAP.md(进度唯一事实源)+ TODO.md(任务总清单)+ react-refactor-plan.md(已完结专项计划)+ style-violations-20260925.md(风格违规底单,谁改到谁顺手改) | 活跃 |
| `design/` | 方案与架构定稿:DESIGN(what/why)、PROMPT-DESIGN(上下文与提示词)、ARCHITECTURE(现有架构总览)、ARCH-REVIEW(2026-09-04 评审快照存档) | 活跃 |
| `new_module/` | 现行模块方案树(**唯一口径**,新方案文档一律建在此处):rag_0.1(知识库新内核)、plan_0.1(Plan-and-Execute)、agent_opt_0.1(智能体框架优化:报告与方案齐,按 TODO 实施) | 活跃 |
| `guide/` | 面向人的讲解与面试材料(非工程约束文档),rag/ 下两级索引 | 活跃 |
| `troubleshooting/` | 踩坑沉淀,格式见其 README;具普遍性的坑回填对应 DEV.md 坑表 | 活跃 |
| `personal/` | 个人素材:简历、五条演示剧本(demo-scripts.md,README 配套) | 私人 |
| `improved/` | rag_improve_v1 前身方案 | **已下线**(各篇头部带横幅,仅存档) |

## 仓库根与仓库外文档

| 位置 | 内容 |
|---|---|
| `README.md` | 项目门面:定位、架构图、起步、刻意不做、设计决策 |
| `CONTEXT.md` | 术语表 |
| `AGENTS.md` | 编码智能体工作区指令(**单一事实源**,CLAUDE.md 为其指针) |
| `BACKEND.md` | TaskForce 产品内智能体运行时背景(经 `agent/memory_ctx.py` 注入产品 system) |
| `agents.example.md` | 运行时 `agents.md`(gitignore)的入库示例模板 |
| `dev/front/docs/` | 前端 12 模块开发文档 + 契约三件套(README/API-CONTRACT/ARCHITECTURE/UI-DESIGN) |
