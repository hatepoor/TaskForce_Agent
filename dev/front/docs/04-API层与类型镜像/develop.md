# API层与类型镜像

> 编号: `04`
> 英文标识: `api-types`
> 状态: ✅ 已完成
> 最后更新: 2026-09-17

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [02-工程脚手架](../02-工程脚手架/develop.md) | `request<T>` 封装与 `ApiError` | `request`、`errText` |
| [API-CONTRACT.md](../API-CONTRACT.md) | 全部端点契约(唯一事实源) | 17 端点请求/响应形状 |

---

## 概述

把后端六个资源域全部封装成类型化 API 模块,`types/` 目录成为契约的手工镜像。六资源封装相互独立,可按视图模块(06~11)的需要分批实现,但本模块统一完成并以 ApiProbeView 验收。

## 功能清单

- **类型镜像**:`types/` 下 chat / knowledge / memory / skills / mcp / api 六个文件,含 MCP 判别联合
- **资源封装**:chat(threads/threads-meta/messages/三 SSE 入口留待 05)/ knowledge / memory / skills / mcp(CRUD + test)/ health
- **验收工具**:临时 `ApiProbeView.vue` 逐端点实测正反路径

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `api/chat.ts` 等 6 个资源模块 | 函数集 | 组件/store 只经此层访问后端 |
| `types/*.ts` | 类型 | 与契约一一对应,冲突以契约为准 |

## 模块开发规范

### 本模块关键约束

- 类型**手工镜像**,不引 openapi-typescript;与契约冲突以契约为准
- `POST /mcp/servers` 的 name 在 **query**、body 是 config 对象(B6 落地前),封装在 `api/mcp.ts` 内消化并写文件头注释(坑 12)
- `DELETE /memory/{key}` 的 key 必须 `encodeURIComponent`
- knowledge 上传是 FormData,**不手动设 Content-Type**
- SSE 端点(`POST /chat*`)在本模块只定义类型与函数签名,实现指向模块 05 的 `sseFetch`
