"use client";

import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SeriesPoint } from "@/lib/api/types";

const tooltipStyle = { background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 12, color: "#0f172a" };

export function TrendChart({ data, label }: { data: SeriesPoint[]; label: string }) {
  return (
    <div>
      <p className="sr-only">{label}</p>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(15,23,42,0.08)" vertical={false} />
            <XAxis dataKey="period" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={24} />
            <YAxis tick={{ fill: "#64748b", fontSize: 11 }} width={64} />
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [Number(value).toLocaleString("en-AE"), "Median AED/sqm"]} />
            <Line type="monotone" dataKey="median_psm" stroke="#4F8CFF" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function VolumeChart({ data }: { data: SeriesPoint[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid stroke="rgba(15,23,42,0.08)" vertical={false} />
          <XAxis dataKey="period" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={24} />
          <YAxis tick={{ fill: "#64748b", fontSize: 11 }} width={48} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar dataKey="transactions" fill="#2DD4BF" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DistributionChart({ data, nameKey, valueKey, caption }: { data: Array<Record<string, string | number | null | undefined>>; nameKey: string; valueKey: string; caption: string }) {
  const colors = ["#4F8CFF", "#2DD4BF", "#C4B5FD", "#E8A598"];
  return (
    <div>
      <p className="sr-only">{caption}</p>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ left: 16 }}>
            <XAxis type="number" tick={{ fill: "#64748b", fontSize: 11 }} />
            <YAxis type="category" dataKey={nameKey} width={110} tick={{ fill: "#334155", fontSize: 11 }} />
            <Tooltip contentStyle={tooltipStyle} />
            <Bar dataKey={valueKey} radius={[0, 4, 4, 0]}>
              {data.map((_, index) => <Cell key={index} fill={colors[index % colors.length]} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function ComparisonChart({ data }: { data: { period: string; [key: string]: string | number | null }[] }) {
  const keys = Object.keys(data[0] ?? {}).filter((key) => key !== "period");
  const colors = ["#4F8CFF", "#2DD4BF", "#C4B5FD", "#E8A598", "#F6E2B2"];
  return (
    <div className="h-80">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <CartesianGrid stroke="rgba(15,23,42,0.08)" vertical={false} />
          <XAxis dataKey="period" tick={{ fill: "#64748b", fontSize: 11 }} minTickGap={24} />
          <YAxis tick={{ fill: "#64748b", fontSize: 11 }} width={64} />
          <Tooltip contentStyle={tooltipStyle} />
          {keys.map((key, index) => <Line key={key} type="monotone" dataKey={key} stroke={colors[index % colors.length]} dot={false} strokeWidth={2} />)}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
