// Every time in the app is New York time, whatever zone the browser is in.
const NY = 'America/New_York'
const hm = new Intl.DateTimeFormat('en-GB', { timeZone: NY, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })
const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: NY, year: 'numeric', month: '2-digit', day: '2-digit' })
const md = new Intl.DateTimeFormat('en-GB', { timeZone: NY, day: 'numeric', month: 'short' })

/** `HH:mm` in ET for a UTC timestamp in seconds. */
export const nyTime = (sec: number) => hm.format(sec * 1000)

/** `YYYY-MM-DD` in ET. */
export const nyDate = (sec: number) => ymd.format(sec * 1000)

/** `3 Nov`, for axis ticks. */
export const nyDay = (sec: number) => md.format(sec * 1000)

/** `YYYY-MM-DD HH:mm` in ET for an ISO time from the API. */
export const nyDateTime = (iso: string) => {
  const sec = Date.parse(iso) / 1000
  return `${nyDate(sec)} ${nyTime(sec)}`
}

/** UTC seconds for an ISO time from the API. */
export const toSec = (iso: string) => Math.floor(Date.parse(iso) / 1000)

/** A `datetime-local` value as an ISO time with no zone; the API reads it as New York time. */
export const toNaiveIso = (local: string) => (local.length === 16 ? `${local}:00` : local)
