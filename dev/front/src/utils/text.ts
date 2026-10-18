/**
 * 挂起文本的转义还原。
 *
 * 后端模型偶发把换行写成字面量 "\n"(反斜杠+n),Markdown 渲染会原样显示。
 * 后端已在 interrupt 载荷读取处还原;前端再兜一层,兼容旧检查点与已缓存的历史。
 * 只用于 interrupt 文本,助手正文不做替换(正文里的 "\n" 可能是代码示例)。
 */
export function normalizeInterruptText(text: string): string {
  return text
    .replace(/\\r\\n/g, '\n')
    .replace(/\\n/g, '\n')
    .replace(/\\r/g, '\n')
    .replace(/\\t/g, '\t')
}
