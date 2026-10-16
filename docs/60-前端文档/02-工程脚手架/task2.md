# Task 2: http 基础封装 + health 打通 + 设计令牌

> 模块: `02-工程脚手架`
> 前置 task: task1
> 模块依赖: 无
> 状态: ✅ 已完成

## 目标

`http.ts` 统一请求层可用,App.vue 临时渲染 `GET /health` 结果证明全链路通;设计令牌与全局样式就位。

## 前置准备

- [ ] task1 已完成并通过验收

## 实现步骤

1. **`src/api/http.ts`**(用户誊写,骨架见 ARCHITECTURE §M1):
   - 文件: `dev/front/src/api/http.ts`
   - 详情: `BASE` 只此一处读 `VITE_API_BASE`;`request<T>` 带 `AbortSignal.timeout(15s)` 默认超时;非 2xx 解析 `detail` 抛 `ApiError`;导出 `errText`(兼容 detail 为 string / object[])
2. **`src/api/health.ts`**:
   - 文件: `dev/front/src/api/health.ts`
   - 详情: `fetchHealth(): Promise<HealthStatus>`,类型 `{status, db, sandbox}`
3. **App.vue 临时调用**:
   - 文件: `dev/front/src/App.vue`
   - 详情: onMounted 调 `fetchHealth`,JSON 展示在页面;失败显示 `errText` 可读错误(停后端验证)
4. **tokens.css + base.css**(tokens 全文抄 UI-DESIGN §5.3,配置类可代写):
   - 文件: `dev/front/src/assets/tokens.css`、`base.css`,接入 `src/main.ts`

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/api/http.ts` | 新增 | 用户誊写 |
| `dev/front/src/api/health.ts` | 新增 | 用户誊写 |
| `dev/front/src/App.vue` | 修改 | 临时 health 展示 |
| `dev/front/src/assets/tokens.css` / `base.css` | 新增 | Claude 代写 |
| `dev/front/src/main.ts` | 修改 | 引入全局样式 |

## 验收标准

- [x] 页面显示 `{status:"ok", db:"ok", sandbox:...}`
- [x] 停后端刷新,显示可读错误(非白屏、非 undefined)
- [x] `npm run build` 成功产出 `dev/front/dist/`
- [x] 后续模块不再出现第二处 BASE 拼接

## 备注

`sandbox` 值域不封闭:类型上就是 `string`,UI 层"非 ok 即异常"(契约 §2.2)。
