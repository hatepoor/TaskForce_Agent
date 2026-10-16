# Task 1: ask 问询卡与恢复闭环

> 模块: `08-挂起交互`
> 前置 task: 无
> 模块依赖: 07
> 状态: ✅ 已完成

## 目标

ask 型挂起:问询卡渲染、作答恢复、已答折叠、400 失效处理。

## 前置准备

- [ ] 模块 07 全部验收通过
- [ ] **模块 01 task3(B3)已验收**(信封 `{kind:"ask", text}`)
- [ ] 后端可复现 ask 挂起(故意让子智能体 need_clarification 的问题)

## 实现步骤

1. **`InterruptCard.vue` 容器 + `AskInterruptCard.vue`**(用户誊写,视觉见 UI-DESIGN §3.3):
   - 文件: `dev/front/src/components/chat/InterruptCard.vue`、`AskInterruptCard.vue`
   - 详情: kind 分派;问题文本 + 输入框(空输入禁提交、自动聚焦);提交 → `resolvePending({answer})` 原地折叠 → `submitAnswer(text)`,新流追加同轮次
2. **挂起期约束接线**:
   - 文件: `dev/front/src/components/chat/Composer.vue`
   - 详情: pending 非空时禁用 + hint"请先回答上方问题";卡片 scrollIntoView
3. **400 失效路径**:后端 400 → 卡片标 failed + toast detail + `loadThreads` 刷新状态

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/chat/InterruptCard.vue` | 新增 | 容器 |
| `dev/front/src/components/chat/AskInterruptCard.vue` | 新增 | 用户誊写 |
| `dev/front/src/components/chat/Composer.vue` | 修改 | 挂起禁用 |

## 验收标准

- [x] 触发 ask:卡片出现、自动聚焦、Composer 禁用
- [x] 回答后:卡片原地折叠为 `✓ 已补充回答 · "…"` 一行,回答内容流式续在同一轮次
- [x] 双标签页场景:第二处提交收 400,卡片标失效且有可读提示
- [x] 空输入不能提交

> 验收说明:前两项与第 4 项由 headless 探针实测(真实后端 + 真实模型)。第 3 项的 400 路径由 `stores/chat.test.ts` 的「400 失败」用例覆盖(卡片标 failed + toast 原文 + 刷新会话列表);**未做双标签页实测**(需要同一挂起被两处竞争消费,成本不划算)。另实测:作答后若信息仍不足,后端会**再问一轮**,属合法推进而非异常。
