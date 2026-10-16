# 工程脚手架

> 编号: `02`
> 英文标识: `scaffold`
> 状态: ✅ 已完成
> 最后更新: 2026-09-16

## 前置依赖

无(与模块 01 可并行;验收时需后端可跑)。

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| 无 | 后端 `GET /health` 已存在(模块 11) | `{status, db, sandbox}` |

---

## 概述

创建 `dev/front/` Vue 3 + Vite + TS 工程骨架,打通"前端 → vite proxy → FastAPI"链路,并封装 http 基础层。配置类文件由 Claude 代写。

## 功能清单

- **工程初始化**:Vite 7 + Vue 3.5 + TS 严格模式,清理示例代码
- **代理与环境**:`/api` 前缀 proxy + rewrite;`.env.development` / `.env.production`
- **基础层**:`src/api/http.ts`(BASE 拼接、ApiError、errText 归一化)、`src/api/health.ts`
- **设计令牌与样式底座**:`tokens.css`(UI-DESIGN §5.3)+ `base.css`

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `request<T>(path, init)` | 函数 | 统一 fetch 封装,非 2xx 抛 `ApiError(status, detail)` |
| `ApiError` / `errText` | 类/函数 | 错误归一化,detail 兼容 string 与 object[] |
| `BASE` | 常量 | 全项目唯一 BaseURL 来源 |

## 模块开发规范

### 本模块关键约束

- proxy 必须带 `rewrite` 剥掉 `/api`(后端无此前缀)与 SSE 防缓冲配置(ARCHITECTURE §1.5)
- **生产环境严禁 `VITE_API_BASE=/api`**(坑 11);两份 `.env` 都入库
- tsconfig 严格项按 ARCHITECTURE §1.4;`@` 别名需 vite alias 同步
- `.gitignore` 必含 `node_modules/`、`dist/`、`*.local`、`.vite/`

### 模块目录结构

见 ARCHITECTURE.md §2 的 `dev/front/` 全目录树(本模块只建骨架与 `src/api/http.ts`、`health.ts`、`assets/`)。
