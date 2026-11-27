// Formatting shared by every page: KSh amounts, dates and times in Kenyan style.

const ksh = new Intl.NumberFormat("en-KE", { maximumFractionDigits: 0 });

export function money(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "–";
  return `KSh ${ksh.format(Math.round(value))}`;
}

const dayFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Africa/Nairobi",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const monthFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Africa/Nairobi",
  month: "long",
  year: "numeric",
});

const shortMonth = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Africa/Nairobi",
  month: "short",
});

const timeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Africa/Nairobi",
  hour: "2-digit",
  minute: "2-digit",
});

function asDate(value: string): Date {
  // "2026-04-01" is a calendar date: read it at noon so no time zone moves it a day
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
}

export function day(value: string | null | undefined): string {
  return value ? dayFormat.format(asDate(value)) : "–";
}

export function month(value: string | null | undefined): string {
  return value ? monthFormat.format(asDate(value)) : "–";
}

export function monthShort(value: string): string {
  return shortMonth.format(asDate(value));
}

/** "4 October 2026" when the day is known, else "October 2026". */
export function meetingWhen(date: string | null | undefined, monthValue: string): string {
  return date ? day(date) : month(monthValue);
}

export function dayAndTime(value: string): string {
  const d = new Date(value);
  return `${dayFormat.format(d)} at ${timeFormat.format(d)}`;
}

export function ago(value: string, now: Date = new Date()): string {
  const minutes = Math.round((now.getTime() - new Date(value).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes === 1) return "1 minute ago";
  if (minutes < 60) return `${minutes} minutes ago`;
  const hours = Math.round(minutes / 60);
  if (hours === 1) return "1 hour ago";
  if (hours < 24) return `${hours} hours ago`;
  const days = Math.round(hours / 24);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n === 1 ? one : many}`;
}
