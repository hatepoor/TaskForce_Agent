---
status: accepted
---

# HITL 为统一机制,且只发生在主图层

HITL 从"长期记忆确认写入"扩展为系统能力:主智能体遇到不确定情况、或需要用户提供输入(任务澄清、缺失参数、凭据等)时,进入 interrupt 挂起并向用户提问,回答作为消息回到主图继续。关键约束:**所有 interrupt 只发生在主图节点(ask 节点与 memory 节点),子智能体不直接 interrupt**--子智能体发现信息不足时在结果摘要中标注"需要澄清",由 supervisor 决定是否发起问询。理由:(1) 并行 Send fan-out 下多个子分支同时 interrupt 会产生多个 pending interrupts,resume 语义复杂且是 LangGraph 出了名的坑,单一挂起点保证任意时刻最多一个 interrupt;(2) 与"子智能体互不直连、一切经 supervisor"的拓扑原则一致。两类挂起:question(自由文本输入即回答)与 confirm(记忆写入,/confirm yes|no)。已知妥协:ask 的回答(含密码等敏感信息)会明文进入对话历史与 checkpointer,单用户本地部署下接受,README 注明,打码存储留 backlog。
