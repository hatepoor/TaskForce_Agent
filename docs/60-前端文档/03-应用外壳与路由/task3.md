# Task 3: 原子组件与 Toast

> 模块: `03-应用外壳与路由`
> 前置 task: task2
> 模块依赖: 02
> 状态: ✅ 已完成

## 目标

五个通用原子组件与全局 Toast 机制就位,后续视图不再各写一套按钮/输入/空态。

## 前置准备

- [ ] task2 已完成并通过验收
- [ ] UI-DESIGN §5.3 token 表已在 tokens.css 生效

## 实现步骤

1. **五个原子组件**(用户誊写,样式全部引用 tokens):
   - 文件: `dev/front/src/components/common/AppButton.vue`(variant: primary/ghost/danger)、`AppInput.vue`、`EmptyState.vue`、`Spinner.vue`、`StatusDot.vue`(ok/warn/err/unknown 四色)
   - 详情: 重点约束——焦点环 `--focus-ring`;danger 只用于删除/错误;`prefers-reduced-motion` 关过渡
2. **`src/stores/ui.ts` + `ToastHost.vue`**:
   - 文件: `dev/front/src/stores/ui.ts`、`dev/front/src/components/layout/ToastHost.vue`
   - 详情: toast 队列 push/3s 自动弹出/最多 3 条;ToastHost 挂 AppShell 右下角
3. **临时验证页**:任一空视图放 5 组件 + 触发一条 toast,确认后删除临时代码

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/common/*.vue`(5 个) | 新增 | 用户誊写 |
| `dev/front/src/stores/ui.ts` | 新增 | 用户誊写 |
| `dev/front/src/components/layout/ToastHost.vue` | 新增 | 用户誊写 |

## 验收标准

- [x] 5 组件在深浅两色主题下均正常(切换系统主题验证)
- [x] toast 3s 消失、超 3 条堆叠正确
- [x] 键盘 Tab 遍历按钮焦点环可见
