# TaskForce 前端架构设计

> 一句话: 前端架构设计入口:决策速览 + 分片索引
> 体系: 前端文档 · ARCHITECTURE
> 分片: 01~08 · 04 分 04a/04b
> 索引: 文末「分片索引」节

**版本**:v1.1 · 2026-09-16 · 目标工程 `dev/front/`
> v1.1 修订:① 视图统一命名 SettingsView;② 设计 token 以 UI-DESIGN.md §5.3 为准(深色默认);③ interrupt 载荷按 API-CONTRACT v1.1 对象信封(`{kind, text}`)调整类型与解析;④ 契约速查表移除,以 API-CONTRACT.md 为唯一契约事实源。
> 后端六 router 已就绪(全同步),本文档为设计定稿 + 开发顺序说明;代码骨架供用户誊写。

---

## 0. 决策速览

| 议题 | 结论 | 一句话理由 |
|---|---|---|
| 构建 | Vite 7 + Vue 3.5 + TypeScript(严格模式) | 用户指定;Vite 冷启动快,单页工作台无需 SSR |
| 路由 | vue-router 4,**hash 模式**,仅 4 条顶层路由 | 懒加载压首屏体积;hash 避免前端路径与后端 `/memory` 等真实端点撞车(history 模式下 catch-all 会语义冲突) |
| 状态 | Pinia(仅 chat + ui 两个 store) | 消息流需跨页存活、跨组件读写;管理页数据是页面局部状态,不进 store |
| CSS | 原生 CSS 变量 + `<style scoped>`,零 UI 库;token 用 UI-DESIGN §5.3 | 本地单用户工具、组件量 < 20,引组件库收益不抵主题覆盖与体积成本 |
| Markdown | `marked` + `dompurify` | 助手回答是 Markdown,~30KB 可接受;XSS 防护必须 |
| 测试 | Vitest,只测纯函数(帧解析) | `splitFrames`/`parseFrame` 是唯一值得单测的部分 |
| 部署 | 生产构建产物由 FastAPI StaticFiles 挂载(形态 B) | 单用户本地工具,一条 `uvicorn` 起全栈最省事;hash 路由使 `html=True` 足够 |

**前置结论**:后端无 `/api` 前缀。开发期 `VITE_API_BASE=/api`(proxy rewrite 剥掉),生产期 `VITE_API_BASE=`(同源直连)。全项目只在 `http.ts` 一处拼 base。

## 分片索引

| 分片 | 涵盖章节 | 内容一句话 |
|---|---|---|
| [01-工程总览.md](./01-工程总览.md) | §1 | 技术栈选型表、为什么需要 vue-router、为什么不用 UI 组件库 / Tailwind、TypeScript 配置基线、开发期 vite proxy |
| [02-目录结构.md](./02-目录结构.md) | §2 | `dev/front/` 目录树与各目录职责 |
| [03-分模块开发计划.md](./03-分模块开发计划.md) | §3 | M0~M6 分模块开发计划与模块依赖图 |
| [04a-SSE客户端设计-传输层.md](./04a-SSE客户端设计-传输层.md) | §4.1、§4.2 | SSE 客户端四条约束与传输层 `src/api/sse.ts`(帧切分与解析) |
| [04b-SSE客户端设计-领域层与错误处理.md](./04b-SSE客户端设计-领域层与错误处理.md) | §4.3、§4.4 | 领域层 `src/composables/useChatStream.ts` 与 SSE 错误处理约定 |
| [05-状态管理设计.md](./05-状态管理设计.md) | §5 | store 划分、`chat.ts` 结构、消息类型建模(`src/types/chat.ts`)、usage 角标为何显示「增量」 |
| [06-构建与集成.md](./06-构建与集成.md) | §6 | npm 脚本、两种部署形态与推荐、仓库卫生 |
| [07-风险与坑位.md](./07-风险与坑位.md) | §7 | 坑 1~12(SSE 半帧、interrupt 双语义、thread_id 前缀、线程池占用、token 流渲染性能、usage 累计等) |
| [08-开发顺序总览.md](./08-开发顺序总览.md) | 附录 | 开发顺序总览 |

> 本手册由原 `ARCHITECTURE.md` 按节拆分而成,正文除新增分片头部与本索引外未作改动。
