# Task 2: memory 确认卡与 unknown 兜底

> 模块: `08-挂起交互`
> 前置 task: task1
> 模块依赖: 07
> 状态: ✅ 已完成

## 目标

memory 型挂起确认闭环 + unknown 类型安全兜底。

## 前置准备

- [ ] task1 已完成并通过验收
- [ ] 后端可复现 memory 挂起(对话中说"记住…")

## 实现步骤

1. **`MemoryConfirmCard.vue`**(用户誊写,视觉见 UI-DESIGN §3.3):
   - 文件: `dev/front/src/components/chat/MemoryConfirmCard.vue`
   - 详情: 提案引用块;「忽略」默认焦点 + 「记入记忆」主按钮;确认 → `resolvePending({approved})` 折叠为 `⊘ 未记入` 或 `✓ 已记入` → `submitConfirm(true/false)`
2. **unknown 兜底卡**:
   - 文件: `dev/front/src/components/chat/InterruptCard.vue`
   - 详情: kind=unknown → 禁用输入 + "检测到未知类型的挂起" + 「新开会话」按钮,不提供恢复入口
3. **联动验证**:确认"记入"后,模块 10(记忆页)接口能查到该条(source=confirmed)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/chat/MemoryConfirmCard.vue` | 新增 | 用户誊写 |
| `dev/front/src/components/chat/InterruptCard.vue` | 修改 | unknown 分支 |

## 验收标准

- [x] 说"记住我喜欢用 uv":提案卡出现,内容为 proposal 原文
- [x] 点「记入记忆」:折叠为已记入;记忆接口出现该条且 source=confirmed
- [x] 点「忽略」:折叠为未记入;记忆接口无该条
- [x] 默认焦点在「忽略」,直接回车不会写入
- [x] 伪造 unknown kind(Devtools 改 store):只显示兜底卡,无恢复入口

> 验收说明:headless 探针实测(真实后端 + 真实模型)。**第 1 条措辞需修正**:「记住 X」在后端是 T3 **显式直写**(`source=explicit`,不 interrupt),不会出确认卡;探针改用**自主提案**措辞(「顺便说一句,我平时都用 uv 管理 Python 依赖,不太喜欢 pip」)才触发 `interrupt({"proposal":...})`,卡面即为 proposal 原文。第 3 条另跑一次定向探针:「忽略」→ 折叠为 `⊘ 未记入长期记忆`,且 `/memory` 条目数不变。第 5 条用 CDP 取 `#app.__vue_app__` 的 pinia store 注入 `sub:"unknown"` 的挂起项实测。探针写入的真实记忆条目已于验证后删除。
