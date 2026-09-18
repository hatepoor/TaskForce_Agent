/** 相对时间格式化(会话列表用):一周内说"多久前",更早退化为日期,避免"1234 天前"。 */

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

export function fmtRelative(ts: number, now: number = Date.now()): string {
  // 0 / 非法值 = 未知时间(历史消息没有时间戳),不显示
  if (!Number.isFinite(ts) || ts <= 0) return ''

  const diff = now - ts
  if (diff < MIN) return '刚刚' // 含未来时间戳(本机时钟回拨)
  if (diff < HOUR) return `${Math.floor(diff / MIN)} 分钟前`
  if (diff < DAY) return `${Math.floor(diff / HOUR)} 小时前`
  if (diff < 7 * DAY) return `${Math.floor(diff / DAY)} 天前`

  const d = new Date(ts)
  const md = `${d.getMonth() + 1} 月 ${d.getDate()} 日`
  return d.getFullYear() === new Date(now).getFullYear() ? md : `${d.getFullYear()} 年 ${md}`
}

/** 时刻(挂起卡已解决态右对齐的小字,如 14:22)。 */
export function fmtClock(ts: number): string {
  if (!Number.isFinite(ts) || ts <= 0) return ''
  const d = new Date(ts)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}