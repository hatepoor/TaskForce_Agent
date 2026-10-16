# 4. SSE 客户端设计(下):领域层与错误处理

> 一句话: 领域层 src/composables/useChatStream.ts 与 SSE 错误处理约定
> 体系: 前端文档 · ARCHITECTURE · SSE 设计分片
> 上游: [README](./README.md)
> 下游: [05-状态管理设计.md](./05-状态管理设计.md)
> 细节见: [手册索引](./README.md)

### 4.3 领域层:`src/composables/useChatStream.ts`

把传输事件翻译成 store 动作,管理"当前轮次"生命周期。**唯一允许调用 `sseFetch` 的地方。**

```ts
import { ref } from 'vue'
import { sseFetch, type SseHandlers } from '@/api/sse'
import { useChatStore } from '@/stores/chat'

export function useChatStream() {
  const chat = useChatStore()
  const controller = ref<AbortController | null>(null)

  async function run(path: string, body: unknown) {
    if (chat.isStreaming) return                  // 单轮互斥,store 层兜底
    const ac = new AbortController()
    controller.value = ac
    chat.beginTurn()

    const handlers: SseHandlers = {
      onToken: (t) => chat.appendToken(t),
      onRoute: (r) => chat.pushRoute(r),
      onInterrupt: (i) => chat.setPending(i),     // B3 信封:{kind, text}
      onUsage: (u) => chat.attachUsage(u),
      onErrorEvent: (e) => chat.failTurn(e.message),   // 流内 error 帧(B4)
      onError: (e) => chat.failTurn(e.message, e.kind === 'http' ? e.status : undefined),
      onDone: () => chat.endTurn(),               // 挂起也走这里:轮次结束,pending 非空
    }
    await sseFetch(path, body, handlers, ac.signal)
    chat.flushTokens()
    controller.value = null
  }

  return {
    send: (text: string) => run('/chat', { thread_id: chat.currentThreadId, text }),
    submitAnswer: (text: string) => run('/chat/answer', { thread_id: chat.currentThreadId, text }),
    submitConfirm: (approved: boolean) => run('/chat/confirm', { thread_id: chat.currentThreadId, approved }),
    /** 仅停前端消费;服务端那轮仍会跑完(§7 坑 7),文案用「停止接收」 */
    abort: () => controller.value?.abort(),
  }
}
```

**调用侧示例(`AskCard.vue`):**

```vue
<script setup lang="ts">
import { ref } from 'vue'
import { useChatStore } from '@/stores/chat'
import { useChatStream } from '@/composables/useChatStream'

const chat = useChatStore()
const { submitAnswer } = useChatStream()
const draft = ref('')

async function submit() {
  const text = draft.value.trim()
  if (!text || chat.isStreaming) return
  chat.resolvePending({ answer: text })   // 先落本地状态,卡片立刻变"已提交"
  draft.value = ''
  await submitAnswer(text)                // 后端 400(挂起已失效)时 failTurn 提示
}
</script>
```

### 4.4 错误处理约定

| 场景 | 判定 | 前端行为 |
|---|---|---|
| 后端未启动 / 连接被拒 | fetch 抛非 AbortError | 助手气泡转错误态「无法连接后端,请确认 uvicorn 已启动」,**保留输入框内容** |
| 非 2xx | `res.ok === false` | 400 → 业务提示(detail 原文,可能"挂起已在别处恢复")并清挂起卡;404 → 刷新对应列表;422 → 校验详情;其他 → detail 原文 |
| 响应无 body | `res.body == null` | 「响应没有可读流」,通常是代理层把流吃了 |
| 流中途断开 | `reader.read()` 抛错 | 本轮标 error,已渲染文本保留 + 「(连接中断,输出可能不完整)」 |
| 单帧解析失败 | `parseFrame` 返回 null | 丢弃计数,**绝不因一帧坏掉中断整条流** |
| 用户主动中止 | AbortError | 不算错误:标 `aborted`,留"服务端可能仍完成了部分动作"提示 |
| 流结束无任何 token | `onDone` 时 token 为空 | 补兜底文案(§7 坑 6) |

**超时策略**:SSE 不设总超时。改用**静默看门狗**:每收到任意帧重置计时器,连续 120s 无帧才判卡死。首轮惰性装配图 + MCP 可能几十秒,UI 必须在 1s 内给出"正在初始化智能体…"反馈。
