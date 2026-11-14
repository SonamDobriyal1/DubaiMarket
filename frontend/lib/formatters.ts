const aed = new Intl.NumberFormat("en-AE", { maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-AE", { maximumFractionDigits: 0 });
const precise = new Intl.NumberFormat("en-AE", { maximumFractionDigits: 1 });

export function formatAed(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return `AED ${aed.format(value)}`;
}

export function formatNumber(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return number.format(value);
}

export function formatPsm(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${aed.format(value)} AED/sqm`;
}

export function formatPercent(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return null;
  const formatted = new Intl.NumberFormat("en-AE", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
    signDisplay: "exceptZero",
  }).format(value);
  return `${formatted}%`;
}

export function formatRatioPercent(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return null;
  return `${precise.format(value * 100)}%`;
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" }).format(date);
}

export function formatCompact(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—";
  if (Math.abs(value) >= 1_000_000_000_000) return `AED ${(value / 1_000_000_000_000).toFixed(2)} trillion`;
  if (Math.abs(value) >= 1_000_000_000) return `AED ${(value / 1_000_000_000).toFixed(2)} billion`;
  return formatAed(value);
}

export function communityAlias(name: string) {
  const folded = name.trim().toLowerCase();
  if (folded === "downtown dubai" || folded === "dubai downtown") return "DownTown Dubai";
  return name.trim();
}
