# Task 1: Health 节 + NavRail 轮询接线

> 模块: `11-系统设置页`
> 前置 task: 无
> 模块依赖: 04
> 状态: 🟡 Health 节已完成;NavRail 接线未落地(文件归属限制,见验收第 2 条)

## 目标

Health 三指标卡 + NavRail 状态点接真数据,轮询策略落地。

## 前置准备

- [x] 模块 04 完成

## 实现步骤

1. **`HealthSection.vue` + `HealthCard.vue`**(线框见 UI-DESIGN §4.4):
   - 文件: `dev/front/src/views/SettingsView.vue`(外壳:左栏节锚点 + 内容区)、`dev/front/src/components/settings/HealthSection.vue`、`HealthCard.vue`
   - 详情: 三卡 + 手动刷新;sandbox 非 ok 即异常渲染,错误文本直出
   - 落地补充: 数据源抽到 `src/components/settings/useHealthPoll.ts`(30s 轮询 / `visibilitychange` 暂停 / KeepAlive 失活暂停 / `onUnmounted` 清理),归一化抽到 `healthModel.ts`(纯函数,可单测)
2. **NavRail 轮询接线**:
   - 文件: `dev/front/src/components/layout/NavRail.vue`
   - 详情: 替换模块 03 的假数据;30s `setInterval`,`visibilityState` 不可见暂停,`onUnmounted` 清理;悬停 tooltip 显示 db/sandbox 明细
   - **未落地**: 该文件属并行子代理的修改范围,本模块不越界;已交付 `useHealthPoll` + `overallState()` / `healthTooltip()`,接线配方见 develop.md「NavRail 接线」(4 行)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/views/SettingsView.vue` | 新增 | 三节外壳(锚点导航 + 内容区) |
| `dev/front/src/components/settings/HealthSection.vue` / `HealthCard.vue` | 新增 | |
| `dev/front/src/components/settings/useHealthPoll.ts` / `healthModel.ts` | 新增 | 轮询数据源 + 归一化纯函数 |
| `dev/front/src/components/layout/NavRail.vue` | **未修改** | 归属限制,接线待做 |

## 验收标准

- [x] sandbox 非 ok 即异常:实测后端当前返回 `sandbox: "沙箱返回 HTTP 502: "`(值域不封闭的活证据),卡片黄点 + 原文本直出,不是红色系统错误;`unreachable` / `unknown` / 任意文本三态由 `healthModel.test.ts` 覆盖
- [ ] NavRail 状态点 30s 刷新,切后台暂停(Devtools 验证无请求)—— **未落地**:`src/components/layout/**` 属并行子代理文件范围;数据源已就绪
- [ ] 停 PG 后 status 变 degraded 且 db 错误文本直出 —— **未实测**(不重启用户的 PG 容器);等价路径由单测覆盖:`degraded` → 黄点、`"error: 连接串拒绝连接"` → 红点且文本原样直出

## 测试

`src/components/settings/healthModel.test.ts`(11 条)+ `settingsComponents.test.ts` 的 HealthCard 渲染冒烟(2 条)。