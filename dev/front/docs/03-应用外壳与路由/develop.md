# 应用外壳与路由

> 编号: `03`
> 英文标识: `app-shell`
> 状态: ✅ 已完成
> 最后更新: 2026-09-17

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [02-工程脚手架](../02-工程脚手架/develop.md) | 工程可跑、tokens/base.css、`request<T>` 封装 | `request`、`ApiError`、`errText` |

---

## 概述

搭建四段式应用外壳(导航轨 + 上下文栏 + 主区 + 抽屉容器)、hash 路由与四个空视图、Toast 轻提示与通用原子组件。只搭骨架不装业务,业务由 04~11 各模块填入。

## 功能清单

- **路由**:vue-router hash 模式,4 条顶层路由懒加载
- **外壳**:`AppShell` 四段式栅格、`NavRail` 导航轨 + Health 状态点、`ContextPanel` 上下文栏容器
- **通用原子组件**:`AppButton` / `AppInput` / `EmptyState` / `Spinner` / `StatusDot`
- **Toast**:`useUiStore` toast 队列 + `ToastHost`(3s 自动消失,最多堆叠 3 条)

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `AppShell` / `NavRail` / `ContextPanel` | 组件 | 布局骨架,视图经 `<router-view>` 注入主区 |
| `AppButton` 等 5 个原子组件 | 组件 | 后续所有视图复用,不做第二套按钮/输入 |
| `useUiStore.toast(msg, type)` | Pinia action | 全局轻提示唯一入口 |

## 模块开发规范

### 本模块关键约束

- 路由必须 **hash 模式**(history 会与后端 `/memory` 等端点撞车,ARCHITECTURE §1.2)
- 视图懒加载 `() => import(...)`;ChatView 用 `<KeepAlive>` 包裹
- 主题不做切换按钮,跟随 `prefers-color-scheme`(tokens.css 已内置)
- 原子组件样式一律用 tokens 变量,禁止硬编码色值/字号
