/**
 * Skills 资源封装(契约 §2.5):只读列表。
 */
import type { SkillListResponse } from '@/types/skills'

import { request } from './http'

/** GET /skills — 技能元数据列表(每次现扫目录;技能变更需重启后端生效)。 */
export function listSkills(): Promise<SkillListResponse> {
  return request<SkillListResponse>('/skills')
}