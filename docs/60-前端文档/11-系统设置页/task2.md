# Task 2: Skills 节 + MCP 列表与删除

> 模块: `11-系统设置页`
> 前置 task: task1
> 模块依赖: 04
> 状态: ✅ 已完成(task3 同批落地,列表行的测试按钮已直接接通)

## 目标

Skills 只读列表与 MCP 服务器列表/删除完成。

## 前置准备

- [x] task1 已完成

## 实现步骤

1. **`SkillsSection.vue` + `SkillCard.vue`**(视觉见 UI-DESIGN §4.4):
   - 文件: `dev/front/src/components/settings/SkillsSection.vue`、`SkillCard.vue`
   - 详情: 只读;dir 等宽省略 + 复制;顶部"变更需重启后端生效"提示;另加"刷新"按钮(非写操作)
2. **`McpSection.vue` + `McpServerList.vue` + `McpServerItem.vue` + `DeleteMcpDialog.vue`**:
   - 文件: `dev/front/src/components/settings/` 四组件
   - 详情: name + transport 徽标 + 命令行/URL 等宽摘要;测试按钮(task3 已接通);删除确认(明示"下次会话装配不再可用");404 兜底 toast + 刷新列表
3. **可选字段防御**:args/env/headers 缺失时摘要与渲染全部按可选(`summarizeConfig` / `serverEntries` 纯函数)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/settings/SkillsSection.vue` / `SkillCard.vue` | 新增 | |
| `dev/front/src/components/settings/McpSection.vue` / `McpServerList.vue` / `McpServerItem.vue` / `DeleteMcpDialog.vue` | 新增 | |
| `dev/front/src/components/settings/mcpModel.ts` / `ConfirmDialog.vue` | 新增 | 纯逻辑 + 通用确认弹窗(删除/覆盖共用) |

## 验收标准

- [x] Skills 空目录时显示空态说明:SSR 冒烟断言 `skills-empty` 与"重启后端"提示(真实空目录未造,不动用户 skills/)
- [x] MCP 列表正确区分 stdio/http,缺省字段不报错:渲染冒烟覆盖「stdio 无 args」「http 无 headers」;实测数据为带 args + env 的 stdio 服务器,摘要拼命令行不报错
- [ ] 删除后列表移除,`mcp_config.json` 对应项消失 —— **未实测**(属写操作,需真实删除用户 MCP 配置);删除链路(确认弹窗 → `removeServer` → toast → 重拉列表)与 404 兜底已实现,待主会话 E2E

## 测试

`src/components/settings/mcpModel.test.ts`(24 条)+ `settingsComponents.test.ts` 的 McpServerItem 渲染冒烟(2 条)。