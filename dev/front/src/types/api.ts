/**
 * API 层通用类型(契约镜像辅助)。
 *
 * - `ApiError`:统一错误类,运行时实现位于 `@/api/http`(此处为类型再导出,
 *   便于类型层单点引用;需要 `instanceof` 时从 `@/api/http` 导入);
 * - `Result<T>`:泛型结果包装,仅供需要显式表达"成功载荷 / 失败原因"的调用点选用
 *   ——后端端点没有统一信封,各资源模块直接返回各自形状。
 */

export type { ApiError } from '@/api/http'

/** 泛型结果包装(判别联合,便于按 ok 收窄)。 */
export type Result<T> = { ok: true; data: T } | { ok: false; error: string }