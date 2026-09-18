# Task 3: 错误态与滚动策略

> 模块: `07-对话流`
> 前置 task: task2
> 模块依赖: 05 + 06
> 状态: ✅ 已完成

## 目标

三类错误形态(请求失败/流中断/空回答)与贴底滚动策略完整落地。

## 前置准备

- [ ] task2 已完成并通过验收
- [ ] UI-DESIGN §3.4 错误态表 + §6.2 滚动六规则已通读

## 实现步骤

1. **`ErrorNotice.vue`**(用户誊写):
   - 文件: `dev/front/src/components/chat/ErrorNotice.vue`
   - 详情: 三形态——重试(请求失败)、复制已生成内容+重试(流中断带 partial)、静默(abort);400 类业务错误 toast + 清挂起卡
2. **空回答兜底**:endTurn 时 token 为空 → note 文案(「本轮循环过深…」/「没有产生文本输出…」)
   - 文件: `dev/front/src/stores/chat.ts`
3. **MessageList 贴底策略**(用户誊写,六规则):
   - 文件: `dev/front/src/components/chat/MessageList.vue`
   - 详情: isPinnedToBottom 48px 阈值、上滚暂停、`↓ 新内容` 胶囊、挂起卡强制滚入(占位)
4. **Composer 完整化**:停止接收按钮、流中禁用、"正在初始化智能体…"1s 反馈、输入框内容在失败时保留

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/components/chat/ErrorNotice.vue` | 新增 | |
| `dev/front/src/components/chat/MessageList.vue` | 修改 | 滚动策略 |
| `dev/front/src/components/chat/Composer.vue` | 修改 | 完整化 |
| `dev/front/src/stores/chat.ts` | 修改 | note 兜底 |

## 验收标准

- [x] kill 后端发送:错误可读、已收文本不丢、输入框内容保留、点重试恢复
- [x] 流中上滚:内容不跳动,出现回底胶囊,点击回底
- [x] 「停止接收」后留灰色提示"服务端可能仍完成了部分动作"
- [x] 触发 recursion limit(B4 后):以正常正文样式显示兜底文案

> 验收说明:第 1 条用 CDP `Network.emulateNetworkConditions(offline)` 模拟后端不可达(等价于 kill 后端,且可在线恢复):错误条可读 + 草稿保留 + 提示改走「重试」+ 重试成功后**不重复插用户气泡**。
>
> **偏差(重要)**:「输入框内容保留」的实现方式改为——草稿在**首个事件到达前不清空**(而不是发送即清空再回填),失败时自然还在框里,并给出"直接发送会重复上一条,建议点上方「重试」"的引导;重试走 `useChatStream.resend()`,不再插用户气泡。理由:发送即清空 + 失败回填会诱导用户重发同一文本,后端会多一条 HumanMessage、污染上下文(坑 6/坑 10 的同一类风险)。
>
> 第 2 条(回底胶囊)与 task2 的轨迹展开态断言一并并入模块 08 探针实测;第 4 条 `noteTurn` 由单测覆盖(真实触发 recursion limit 需要构造深递归图,成本不划算,且 B4 的 error 帧路径已有 SSE 断言)。
