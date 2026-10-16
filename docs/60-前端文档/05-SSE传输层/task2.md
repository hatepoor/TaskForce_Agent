# Task 2: Vitest 单测(splitFrames / parseFrame)

> 模块: `05-SSE传输层`
> 前置 task: task1
> 模块依赖: 04
> 状态: ✅ 已完成

## 目标

帧解析纯函数获得单测覆盖(前端唯一单测点),测试用例由 Claude 给全文。

## 前置准备

- [ ] task1 已完成并通过验收

## 实现步骤

1. **Claude 编写 `dev/front/src/api/__tests__/sse.spec.ts`**,覆盖用例:
   - 单帧完整解析(四类事件 + unknown)
   - 多帧一次切分
   - 残帧留 buffer(半条 JSON)
   - CRLF(`\r\n\r\n`)归一化
   - 中文跨片:`TextDecoder {stream:true}` 手工模拟劈开三字节字符
   - 坏 JSON 返回 null
2. **用户誊写测试文件并跑通**(测试代码 Claude 负责,誊写属学习)

## 涉及文件

| 文件路径 | 操作类型 | 说明 |
|----------|----------|------|
| `dev/front/src/api/__tests__/sse.spec.ts` | 新增 | Claude 写 |

## 验收标准

- [x] `npm test` 全绿
- [x] 覆盖上述至少 7 类用例
