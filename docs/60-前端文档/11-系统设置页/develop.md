# 系统设置页

> 编号: `11`
> 英文标识: `settings-view`
> 状态: ✅ 已完成(2026-09-17 代码落盘 + 单测/渲染冒烟通过;NavRail 接线与浏览器端到端见下方未完成项)
> 最后更新: 2026-09-17

## 前置依赖

| 依赖模块 | 依赖内容 | 期望接口/契约 |
|----------|----------|---------------|
| [04-API层与类型镜像](../04-API层与类型镜像/develop.md) | `api/health.ts`、`api/skills.ts`、`api/mcp.ts` | 三资源封装 |
| [01-后端契约改造](../01-后端契约改造/develop.md) | B6/B8(建议;未落地按契约现状实现) | name 位置、422/404 语义 |
| [03-应用外壳与路由](../03-应用外壳与路由/develop.md) | `NavRail` Health 点、原子组件 | StatusDot |

---

## 概述

SettingsView 三节:Health 状态面板(含 NavRail 轮询接线)、Skills 只读列表、MCP 服务器管理(列表/新增表单/测试/删除)。管理页里体量最大的模块。

## 功能清单

- **Health**:三指标卡(status/db/sandbox)+ 手动刷新 + NavRail 30s 轮询(不可见暂停)
- **Skills**:只读卡片(name/description/dir 复制),"变更需重启后端生效"提示
- **MCP**:服务器列表(stdio/http 徽标)、新增表单(transport 切换联动、草稿保留)、测试连通(ok:false 正常呈现)、删除确认

## 对外暴露接口

| 接口/导出 | 类型 | 说明 |
|-----------|------|------|
| `SettingsView` 及 Mcp/Skills/Health 三节组件 | 组件 | 挂 `/settings` 路由 |
| NavRail Health 轮询 | 逻辑 | 复用本模块 health 数据源(见下"NavRail 接线") |

## 模块开发规范

### 本模块关键约束

- `sandbox` **非 ok 即异常**(值域不封闭),原文本直接展示
- MCP 表单:**切换 transport 不丢草稿**;提交只带当前类型字段且必带 `transport`;name 前端正则 `^[a-z0-9_-]+$` 校验;同名覆盖前二次确认
- MCP test 前端 30s 超时 + 按钮禁用(后端内部 10s);`ok:false` 显示"未连通",不是红色系统错误
- health 轮询 30s,`document.visibilityState` 不可见时暂停

---

## 实现落点(2026-09-17)

### 文件清单

| 文件 | 职责 |
|------|------|
| `src/views/SettingsView.vue` | 页面外壳:左栏三节锚点(sticky)+ 内容区(MCP → Skills → Health) |
| `src/components/settings/useHealthPoll.ts` | **health 唯一数据源**:30s 轮询 / 不可见暂停 / KeepAlive 失活暂停 / `onUnmounted` 双清 |
| `src/components/settings/healthModel.ts` | 纯函数:三态归一化、三卡模型、聚合状态点、tooltip 文案 |
| `src/components/settings/HealthSection.vue` / `HealthCard.vue` | 三指标卡 + 手动刷新 + 错误条 |
| `src/components/settings/SkillsSection.vue` / `SkillCard.vue` | 只读列表、dir 复制、"重启后端生效"提示、空态 |
| `src/components/settings/McpSection.vue` | MCP 状态持有者:列表 / 新增抽屉 / 删除 / 覆盖确认 / toast |
| `src/components/settings/McpServerList.vue` / `McpServerItem.vue` | 列表与单行(name + transport 徽标 + 摘要 + 测试/删除),测试状态行内自持 |
| `src/components/settings/McpServerForm.vue` | 右侧抽屉表单:两份 transport 草稿、键值对行编辑器、错误条、必填校验 |
| `src/components/settings/McpTestResult.vue` | 测试结果就地展开(工具名列表 / 未连通 / 请求层失败) |
| `src/components/settings/ConfirmDialog.vue` / `DeleteMcpDialog.vue` | 通用确认弹窗与删除专用文案 |
| `src/components/settings/mcpModel.ts` | 纯函数:草稿、校验、提交体、摘要、重名判定、tools 防御式归一化、弹窗文案 |
| `src/components/settings/*.test.ts` | 44 条:纯函数 35 条 + SSR 渲染冒烟 9 条 |

### 实现要点与取舍

- **轮询失败不刷屏**:`useHealthPoll().refresh()` 把错误文案**返回**给调用方——手动刷新失败弹 toast,30s 后台轮询失败只落 `error` 就地展示(否则后端一挂就每 30s 弹一次)。
- **KeepAlive 感知**:AppShell 对视图用 `<KeepAlive>`,仅靠 `onUnmounted` 会在切走后继续后台轮询;故额外接 `onActivated` / `onDeactivated` 暂停与恢复,并保留 `visibilitychange` 处理(切后台零请求、回前台立即补一次)。
- **状态归一化两处不精确匹配**:`sandbox` 非 ok 一律黄点 + 原文本直出;`db` 非 ok 一律红点 + 异常文本直出。聚合给导航轨用 `worstState`(err > warn > unknown > ok)。
- **MCP 测试的两种失败分开**:`ok:false`(正常业务返回)只渲染"未连通 + 无法连接…",**不弹 toast、不标红系统错误**;请求层异常(30s 超时 / 404 / 500)才走 `error` 分支并 toast,超时另给 30s 话术(不复用 `errText` 的 15s 默认提示)。
- **表单提交**由 `buildConfig` 收口:只带当前 transport 字段 + 必带 `transport`;空 args/env/headers 整个不发。切换 transport 只改 `draft.transport`,两份子草稿并存 → 来回切不丢内容。
- **二次确认两处**:删除(`DeleteMcpDialog`,文案点明"下次会话装配不再可用")与同名覆盖(`ConfirmDialog`,父组件在 `isDuplicateName` 命中时挂起提交)。
- 抽屉/弹窗按 Esc 关闭:抽屉用容器级 `@keydown`(不放 document 级监听,避免与上层弹窗抢事件);弹窗用 document 级监听并在关闭/卸载时移除。

### 测试装置约定(E2E 用)

- 稳定 `data-testid`:`settings-view` / `settings-anchor-{mcp|skills|health}` / `mcp-section` / `mcp-add` / `mcp-row` / `mcp-test` / `mcp-delete` / `mcp-delete-confirm` / `mcp-overwrite-confirm` / `mcp-form-*` / `mcp-test-result` / `skills-section` / `skill-card` / `skills-refresh` / `health-section` / `health-refresh` / `health-card-{status|db|sandbox}`。
- 同一 testid 在 `v-for` 内会重复:MCP 行与按钮额外带 **`data-server="<name>"`**,定位写成 `[data-server="filesystem"] [data-testid="mcp-test"]`。

### NavRail 接线(本模块**未落地**,见未完成项)

`src/components/layout/NavRail.vue` 属并行子代理的文件范围,本模块只交付数据源。接线配方(4 行):

```ts
import { computed } from 'vue'
import { healthTooltip, overallState } from '@/components/settings/healthModel'
import { useHealthPoll } from '@/components/settings/useHealthPoll'

const { data } = useHealthPoll() // NavRail 常驻挂载,onMounted / visibilitychange 路径即可
const health = computed(() => ({ state: overallState(data.value), tip: healthTooltip(data.value) }))
```

模板里把 `health.state` / `health.tip` 替换掉现有假数据常量,并删掉"假数据,模块 11 接真轮询"的文案与 `TODO(模块 11)` 注释。

### 未完成 / 未实测

- **NavRail Health 状态点仍是假数据**(task1 第 2 条验收未勾):文件归属限制,见上。数据源与接线配方已就绪。
- **需浏览器点击的项**(抽屉切换草稿、422 错误条不丢数据、删除后列表移除且 `mcp_config.json` 对应项消失、切后台无请求)由主会话 E2E 统一验;本模块只做到单测 + SSR 冒烟 + 后端只读实测。
- **停 PG 复现 degraded** 未做(不动用户的 PG 容器),等价路径由 `healthModel` 单测覆盖。

### 后端实测样本(2026-09-17,只读探测)

```
GET  /health              → {"status":"ok","db":"ok","sandbox":"沙箱返回 HTTP 502: "}
POST /mcp/servers/askecho-search/test → {"ok":false,"tools":[],"name":"askecho-search"}
POST /mcp/servers?name=__probe__ {"command":"npx"} → 422 {"detail":"配置无效:…Unable to extract tag using discriminator 'transport'…"}
GET  /skills              → 1 条(hello-world)
```

第一行是"`sandbox` 值域不封闭"的活证据:实际值既不是 `unreachable` 也不是 `unknown`,按非 ok 渲染为黄点 + 原文本直出。第三行确认 422 的 `detail` 是**字符串**(非 Pydantic 数组),错误条直接展示即可。