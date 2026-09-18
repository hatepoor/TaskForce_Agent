/**
 * Skills 资源类型镜像(唯一事实源:API-CONTRACT.md §2.5)。
 */

/** GET /skills 单条技能元数据。 */
export interface SkillMeta {
  /** 已通过 ^[a-z0-9-]+$ 校验,可安全用作 key。 */
  name: string
  /** frontmatter 的 description,可能为 ""。 */
  description: string
  /** 服务端本地绝对路径;仅调试展示,不做正式 UI 元素。 */
  dir: string
}

/** GET /skills 响应(每次现扫目录;智能体侧缓存需重启后端才更新)。 */
export interface SkillListResponse {
  skills: SkillMeta[]
}