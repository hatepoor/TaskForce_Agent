# 系统设置页 开发进度

> 编号: `11`
> 依赖模块: 04(+01 的 B6/B8 建议)
> 最后更新: 2026-09-17

## Task 进度总览

| Task | 名称 | 状态 | 依赖 |
|------|------|------|------|
| [task1](./task1.md) | Health 节 + NavRail 轮询接线 | 🟡 Health 节完成;NavRail 接线未落地(文件归属限制) | 模块04 |
| [task2](./task2.md) | Skills 节 + MCP 列表与删除 | ✅ | task1 |
| [task3](./task3.md) | MCP 新增表单与连通测试 | ✅ | task2 |

## 进度日志

### 2026-09-16

- ⬜ task1~task3: 未开始

### 2026-09-17

**实现要点**

- 新增 `src/components/settings/` 12 个文件 + 重写 `src/views/SettingsView.vue`(页面外壳:左栏三节锚点 + MCP → Skills → Health 内容区)。
- 纯逻辑层抽两个纯函数模块,便于单测:`healthModel.ts`(三态归一化、三卡模型、聚合状态点、tooltip)、`mcpModel.ts`(草稿 / 校验 / 提交体 / 摘要 / 重名判定 / tools 防御式归一化 / 弹窗文案)。
- health 数据源 `useHealthPoll.ts`:30s 轮询;`document.visibilityState === 'hidden'` 暂停;因 AppShell 用 `<KeepAlive>`,额外接 `onActivated` / `onDeactivated` 暂停与恢复;`onUnmounted` 清定时器 + 监听器。`refresh()` 返回错误文案:手动刷新弹 toast,后台轮询只就地展示(避免后端一挂就每 30s 弹一次)。
- `sandbox` **非 ok 即异常**(不精确匹配 `unreachable` / `unknown`),黄点 + 原文本直出;`db` 非 ok 一律红点 + 异常文本直出。
- MCP:`ok:false` 是正常业务返回 → 只渲染"未连通 + 无法连接…",**不弹 toast、不标红**;请求层失败(30s 超时 / 404 / 500)才 toast,超时用 30s 专属话术。抽屉表单两份 transport 草稿并存(切换不丢),`buildConfig` 收口"只发当前类型字段 + 必带 transport"。两处二次确认:删除 + 同名覆盖。
- 测试装置:`data-testid` 覆盖各交互点;`v-for` 内重复的 testid 额外带 `data-server="<name>"` 便于 E2E 精确定位(约定见 develop.md)。

**验证证据**

| 项 | 结果 |
|---|---|
| `npx vitest run src/components/settings/healthModel.test.ts src/components/settings/mcpModel.test.ts src/components/settings/settingsComponents.test.ts` | 3 文件 / **44 条全通过**(纯函数 35 + SSR 渲染冒烟 9;node 环境,无 DOM) |
| `npx vue-tsc --noEmit` | 零错误(含模板表达式检查) |
| 后端只读实测 | `GET /health` → `sandbox: "沙箱返回 HTTP 502: "`(非封闭值域的活证据,按非 ok 渲染 ✓);`POST /mcp/servers/askecho-search/test` → `{"ok":false,…}`(未连通路径 ✓);缺 `transport` 的 `POST /mcp/servers?name=…` → 422 且 `detail` 为字符串(错误条直接展示 ✓);`GET /skills` → 1 条 |
| SSR 整页冒烟 | `SettingsView` 三节锚点 + 三个 section 装配成功,空数据首屏不报错,Skills 空态与 MCP 空态均渲染 |

**未完成 / 待主会话 E2E**

1. **NavRail Health 状态点仍是模块 03 的假数据**:`src/components/layout/**` 属并行子代理文件范围,本模块未越界修改。数据源与 4 行接线配方已写在 develop.md「NavRail 接线」。
2. 需浏览器点击的验收项:抽屉切换草稿保留、422 错误条且草稿不丢、删除后列表移除且 `mcp_config.json` 对应项消失、切后台暂停轮询(Devtools 无请求)。
3. 停 PG 复现 `degraded` 未做(不动用户 PG 容器),等价路径已由单测覆盖。