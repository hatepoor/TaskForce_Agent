# Task 3: MCP 新增表单与连通测试

> 模块: `11-系统设置页`
> 前置 task: task2
> 模块依赖: 04
> 状态: ✅ 已完成

## 目标

MCP 新增表单(transport 联动、草稿保留)与连通性测试完整落地。

## 前置准备

- [x] task2 已完成
- [x] UI-DESIGN §4.2 表单线框与字段差异表已通读

## 实现步骤

1. **`McpServerForm.vue`**(右侧抽屉打开):
   - 文件: `dev/front/src/components/settings/McpServerForm.vue`
   - 详情: 名称正则校验;Stdio/Http 分段切换(**各维护一份草稿不互删**);args 多行按空白切分;env/headers 键值对行编辑器;提交只带当前类型字段 + `transport`;同名覆盖二次确认(父组件用 `ConfirmDialog`,表单内先给黄色提示条)
2. **`McpTestResult.vue`**:
   - 文件: `dev/front/src/components/settings/McpTestResult.vue`
   - 详情: 测试中按钮禁用(前端 30s,`AbortSignal.timeout` 在 `api/mcp.ts`);结果就地展开——工具名列表(防御式:字符串或对象数组)或"未连通"+ 原因;请求层失败(超时/404/500)走 `error` 分支并 toast,超时用 30s 专属话术
3. **422 路径**:后端 detail(字符串)显示在表单顶部错误条,抽屉不关闭、草稿不丢
4. 表单打开时自动聚焦名称框;抽屉内 Esc 关闭(容器级监听,不与上层弹窗抢事件)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/settings/McpServerForm.vue` | 新增 | |
| `dev/front/src/components/settings/McpTestResult.vue` | 新增 | |
| `dev/front/src/components/settings/McpServerItem.vue` | 新增 | 测试按钮直接接通(task2 同批) |

## 验收标准

- [x] 切换 Stdio→Http→Stdio 已填内容保留:`buildConfig` 单测覆盖"切到 http 只发 http 字段、切回 stdio 草稿仍在";UI 点击流待 E2E
- [x] 提交体只有当前类型字段:`mcpModel.test.ts` 4 条(含"stdio 草稿里填了 url 也不发";B6 前后均可,封装层已消化 name 位置)
- [x] 测试假服务器显示"未连通":实测 `POST /mcp/servers/askecho-search/test` → `{"ok":false,"tools":[],"name":"askecho-search"}`;渲染冒烟断言"未连通 + 无法连接…",只给 danger 文案、不弹 toast、不标红色系统错误
- [ ] 非法 transport 构造 422:错误条展示且表单数据不丢 —— 后端形状**已实测**(缺 `transport` → 422,`detail` 为字符串 `配置无效:…`);UI 路径(错误条 + 草稿不丢 + 抽屉不关)待主会话 E2E 点击验证

## 测试

`src/components/settings/mcpModel.test.ts`(24 条,含 tools 防御式归一化 5 条)+ `settingsComponents.test.ts` 的 McpTestResult 渲染冒烟(4 条)。