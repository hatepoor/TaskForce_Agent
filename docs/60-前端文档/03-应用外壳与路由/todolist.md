# 应用外壳与路由 开发进度

> 编号: `03`
> 依赖模块: 02
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | hash 路由与四个空视图 | ✅ | 无 |
| [task2](./task2.md) | AppShell / NavRail / ContextPanel | ✅ | task1 |
| [task3](./task3.md) | 原子组件与 Toast | ✅ | task2 |

## 进度日志

### 2026-09-16

- ✅ task1~task3 已于 2026-09-17 全部完成(见下)

### 2026-09-17

- ✅ task1: hash 路由 + 4 个懒加载视图 + KeepAlive(前进/后退/刷新直达实测)
- ✅ task2: AppShell / NavRail / ContextPanel 四段式外壳(验收期修复折叠布局 bug:显式 grid-column 防主区塌陷)
- ✅ task3: 5 原子组件 + useUiStore/ToastHost(新增 ui.test.ts 4 条);临时验证块已按流程移除
- 验收证据:vue-tsc 零错误、npm run build 通过、vitest 10/10、headless Edge 冒烟 36/36(路由/外壳/KeepAlive/toast 3s+上限 3/深浅主题/1024px/折叠恢复/tooltip/焦点环/控制台零错)
- 备注:新增依赖 vue-router@4.6.4、pinia@3.0.4;index.html 补内联 favicon(消除 /favicon.ico 404)
