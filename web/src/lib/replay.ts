import type { Bar } from '../api/types'

export function closedBars(bars: Bar[], cutoff: number): Bar[] {
  return bars.filter((bar) => bar.close_time !== undefined && bar.close_time <= cutoff)
}
