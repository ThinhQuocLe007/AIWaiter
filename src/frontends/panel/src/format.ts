// Small display helpers shared by the panel's boards.

const priceFmt = new Intl.NumberFormat('vi-VN')

export function formatPrice(v: number): string {
  return `${priceFmt.format(v)}đ`
}

// SQLite stores UTC "YYYY-MM-DD HH:MM:SS"; mark it as UTC before parsing.
function parseUtc(ts: string): number {
  return new Date(ts.replace(' ', 'T') + 'Z').getTime()
}

// Minutes elapsed since `ts`, measured against `now` (passed in so callers can tick it).
export function minutesSince(ts: string, now: number): number {
  return Math.max(0, Math.round((now - parseUtc(ts)) / 60000))
}

export function timeAgo(ts: string, now: number): string {
  const mins = minutesSince(ts, now)
  if (mins < 1) return 'vừa xong'
  if (mins < 60) return `${mins} phút trước`
  return `${Math.floor(mins / 60)} giờ trước`
}

// "Đã ngồi" duration label, e.g. "12 phút" / "1 giờ 5 phút".
export function durationLabel(ts: string, now: number): string {
  const mins = minutesSince(ts, now)
  if (mins < 60) return `${mins} phút`
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return m ? `${h} giờ ${m} phút` : `${h} giờ`
}
