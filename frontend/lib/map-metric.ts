export type MapMetric = "price" | "growth" | "volume" | "volatility" | "offplan";

type MetricRow = {
  median_psm: number | null;
  yoy_growth_pct: number | null;
  transactions: number;
  time_series_volatility?: number | null;
  share_offplan?: number | null;
};

export function metricValue(row: MetricRow, metric: MapMetric): number | null {
  const value = {
    price: row.median_psm,
    growth: row.yoy_growth_pct,
    volume: row.transactions,
    volatility: row.time_series_volatility,
    offplan: row.share_offplan,
  }[metric];
  return value == null || Number.isNaN(value) ? null : value;
}

function mix(from: [number, number, number], to: [number, number, number], t: number) {
  const clamped = Math.min(1, Math.max(0, t));
  const channels = from.map((channel, index) => Math.round(channel + (to[index] - channel) * clamped));
  return `rgb(${channels[0]}, ${channels[1]}, ${channels[2]})`;
}

export function colorForValue(value: number | null, values: number[], diverging: boolean) {
  if (value == null || values.length === 0) return "#94A3B8";
  if (diverging) {
    const span = Math.max(...values.map((item) => Math.abs(item)), 0.0001);
    const t = Math.max(-1, Math.min(1, value / span));
    if (t >= 0) return mix([148, 163, 184], [45, 212, 191], t);
    return mix([148, 163, 184], [224, 122, 95], -t);
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const t = max === min ? 0.5 : (value - min) / (max - min);
  if (t < 0.5) return mix([45, 212, 191], [79, 140, 255], t / 0.5);
  return mix([79, 140, 255], [232, 165, 152], (t - 0.5) / 0.5);
}
