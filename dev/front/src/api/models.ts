/**
 * 模型配置封装(契约 §2.7)。
 * - fetchModelConfig:普通 JSON 端点;返回的 config 是 .env + 覆盖表(= 重启后的生效值);
 * - saveModelConfig:PUT **只发改动项**——缺项=不动,空串=清除该项覆盖(回落 .env),
 *   api_key 传掩码=保持不动(后端规则,见 settings/model_overrides.py)。
 */
import type { ModelConfigResponse, ModelConfigValues } from '@/types/models'

import { request } from './http'

/** GET /models/config — 生效配置 + 覆盖来源 + 待重启标记。 */
export function fetchModelConfig(): Promise<ModelConfigResponse> {
  return request<ModelConfigResponse>('/models/config')
}

/** PUT /models/config — 保存改动项(落盘 .taskforce/model_config.json,重启后端生效)。 */
export function saveModelConfig(
  values: Partial<ModelConfigValues>,
): Promise<ModelConfigResponse> {
  return request<ModelConfigResponse>('/models/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  })
}