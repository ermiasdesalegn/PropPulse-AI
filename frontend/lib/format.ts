export function money(value: number | string | null | undefined, currency = "ETB"): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  return `${currency} ${n.toLocaleString("en-US", { maximumFractionDigits: n % 1 === 0 ? 0 : 2 })}`;
}

export function compactMoney(value: number | string | null | undefined, currency = "ETB"): string {
  if (value === null || value === undefined || value === "") return "—";
  return `${currency} ${Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value))}`;
}

export function dateTime(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    timeZone,
    weekday: "short",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function dateOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = seconds / 60;
  if (minutes < 60) return `${Math.floor(minutes)}m ago`;
  const hours = minutes / 60;
  if (hours < 24) return `${Math.floor(hours)}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function todayISO(): string {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

export function clientName(c: { full_name?: string | null; telegram_username?: string | null } | null | undefined) {
  if (!c) return "Unknown";
  return c.full_name || (c.telegram_username ? `@${c.telegram_username}` : "Unnamed lead");
}
