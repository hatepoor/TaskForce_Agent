/**
 * 模型配置镜像(契约 §2.7 /settings 模型节)。
 * 六个字段可被设置页覆盖,.env 仍是默认值来源;保存后重启后端生效。
 */

/** 可覆盖的六项(llm_* / embedding_* 各三项)。 */
export interface ModelConfigValues {
  llm_base_url: string
  llm_api_key: string
  llm_model: string
  embedding_base_url: string
  embedding_api_key: string
  embedding_model: string
}

export type ModelField = keyof ModelConfigValues

/** GET/PUT /models/config 响应:生效值 + 覆盖来源 + 是否待重启。 */
export interface ModelConfigResponse {
  /** 当前**生效**值;api_key 为掩码(如 `sk-a****wxyz`) */
  config: ModelConfigValues
  /** 由设置页覆盖的字段(盘上那份,重启后接管);未覆盖的走 .env */
  overridden: ModelField[]
  /** 已保存但尚未生效(改动落盘后必须重启后端) */
  restart_required: boolean
}