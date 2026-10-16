# Task 2: AppShell / NavRail / ContextPanel 外壳

> 模块: `03-应用外壳与路由`
> 前置 task: task1
> 模块依赖: 02
> 状态: ✅ 已完成

## 目标

四段式布局成型:56px 导航轨 + 240px 上下文栏 + 弹性主区;导航轨含当前项指示与 Health 状态点。

## 前置准备

- [ ] task1 已完成并通过验收
- [ ] UI-DESIGN §1(布局图与规则)已通读

## 实现步骤

1. **`src/components/layout/AppShell.vue`**(用户誊写,UI 参照 UI-DESIGN §1.1):
   - 文件: `dev/front/src/components/layout/AppShell.vue`
   - 详情: CSS Grid 四段式;上下文栏可折叠;主区 min-width 520px
2. **`NavRail.vue`**:
   - 文件: `dev/front/src/components/layout/NavRail.vue`
   - 详情: 四图标(当前项 `--accent` + 左 2px 竖条,悬停 tooltip);底部 Health 状态点——先接假数据,模块 11 才接真轮询
3. **`ContextPanel.vue`**:
   - 文件: `dev/front/src/components/layout/ContextPanel.vue`
   - 详情: 按路由切换内部列表组件的插槽容器(本模块放占位标题)
4. **重构 App.vue 移除 task 临时 health 代码**,改为 `AppShell` + `<router-view>`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/layout/AppShell.vue` | 新增 | 用户誊写 |
| `dev/front/src/components/layout/NavRail.vue` | 新增 | Health 点接假数据 |
| `dev/front/src/components/layout/ContextPanel.vue` | 新增 | 插槽容器 |
| `dev/front/src/App.vue` | 修改 | 重构 |

## 验收标准

- [x] 四视图切换时外壳常驻,上下文栏内容随路由变化
- [x] 最小窗口宽度 1024px 下布局不破
- [x] ChatView 切走再切回,占位状态保留(KeepAlive 生效)
