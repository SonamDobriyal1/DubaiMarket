"use client";

import { useMemo, useState } from "react";
import type { ComparableSale, Methodology, ValuationResponse } from "@/lib/api/types";
import { formatAed, formatDate, formatNumber, formatPercent, formatPsm } from "@/lib/formatters";
import { GlassCard } from "@/components/shared/surface";

const STATUS: Record<ValuationResponse["pricing_classification"], string> = {
  "Potentially undervalued": "border-emerald-200 bg-emerald-50 text-emerald-900",
  "Fairly priced": "border-slate-200 bg-slate-50 text-slate-900",
  "Potentially overvalued": "border-rose-200 bg-rose-50 text-rose-900",
  Inconclusive: "border-amber-200 bg-amber-50 text-amber-950",
};

export function PricingStatus({ value, reason }: { value: ValuationResponse["pricing_classification"]; reason: string }) {
  return (
    <div className={`rounded-2xl border px-4 py-3 ${STATUS[value]}`}>
      <p className="text-sm font-medium">{value}</p>
      <p className="mt-1 text-sm leading-6 opacity-90">{reason}</p>
      {value === "Inconclusive" ? <p className="mt-2 text-xs">This is not a signal that the asking price is attractive or unattractive.</p> : null}
    </div>
  );
}

export function ValuationRangeChart({ result }: { result: ValuationResponse }) {
  const lower = result.valuation_interval.lower_aed ?? result.estimated_market_value_aed;
  const upper = result.valuation_interval.upper_aed ?? result.estimated_market_value_aed;
  const points = [lower, result.estimated_market_value_aed, upper, result.asking_price_aed];
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = Math.max(max - min, 1);
  const position = (value: number) => ((value - min) / span) * 100;
  return (
    <div>
      <div className="relative h-16 rounded-full bg-slate-100">
        <div className="absolute top-1/2 h-2 -translate-y-1/2 rounded-full bg-[#4F8CFF]/70" style={{ left: `${position(lower)}%`, width: `${Math.max(position(upper) - position(lower), 1)}%` }} />
        <Marker left={position(result.estimated_market_value_aed)} label="Estimate" />
        <Marker left={position(result.asking_price_aed)} label="Asking" tone="ask" />
      </div>
      <div className="mt-3 grid grid-cols-1 gap-1 text-xs text-slate-500 sm:grid-cols-3">
        <span>Lower {formatAed(lower)}</span>
        <span className="sm:text-center">Estimate {formatAed(result.estimated_market_value_aed)}</span>
        <span className="sm:text-right">Upper {formatAed(upper)}</span>
      </div>
    </div>
  );
}

function Marker({ left, label, tone = "estimate" }: { left: number; label: string; tone?: "estimate" | "ask" }) {
  return (
    <div className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2" style={{ left: `${left}%` }}>
      <div className={`h-4 w-4 rounded-full border-2 ${tone === "ask" ? "border-amber-400 bg-amber-400" : "border-white bg-slate-900"}`} />
      <span className="absolute top-5 left-1/2 -translate-x-1/2 text-[10px] tracking-wide text-slate-500 uppercase">{label}</span>
    </div>
  );
}

export function ValuationResult({ result, coverage }: { result: ValuationResponse; coverage?: Methodology }) {
  const source = result.community_prior_median_source === "official_area" ? `Official area${result.resolved_location.official_area ? `: ${result.resolved_location.official_area}` : ""}` : `Master project${result.resolved_location.master_project ? `: ${result.resolved_location.master_project}` : ""}`;
  const empirical = coverage?.prediction_interval.test_overall.empirical_coverage;
  return (
    <div className="space-y-4">
      <GlassCard className="p-5">
        <p className="text-xs tracking-[0.16em] text-slate-500 uppercase">Estimated market value</p>
        <p className="mt-2 font-mono text-3xl tracking-tight break-words sm:text-4xl">{formatAed(result.estimated_market_value_aed)}</p>
        <p className="mt-2 text-sm text-slate-500">Model-estimated transaction value. Asking price was not a model input.</p>
        {result.stale_market_features_note ? <p className="mt-3 text-sm text-amber-800">{result.stale_market_features_note}</p> : null}
      </GlassCard>
      <GlassCard className="p-5">
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-lg font-medium">Valuation interval</h2>
            <p className="mt-1 text-sm text-slate-500">A range for one property&apos;s potential transaction price, not a confidence interval for an average price.</p>
          </div>
          <p className="text-right text-xs text-slate-500">Nominal {Math.round((result.valuation_interval.nominal_coverage ?? 0.9) * 100)}%{empirical != null ? ` · Test coverage ${Math.round(empirical * 1000) / 10}%` : ""}</p>
        </div>
        <ValuationRangeChart result={result} />
      </GlassCard>
      <GlassCard className="grid gap-4 p-5 md:grid-cols-2">
        <div>
          <h2 className="text-lg font-medium">Asking price</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <Row term="Asking price" value={formatAed(result.asking_price_aed)} />
            <Row term="Estimate" value={formatAed(result.estimated_market_value_aed)} />
            <Row term="Difference" value={formatAed(result.asking_minus_estimate_aed)} />
            <Row term="Percentage difference" value={formatPercent(result.price_gap_pct) ?? "—"} />
          </dl>
        </div>
        <PricingStatus value={result.pricing_classification} reason={result.classification_reason} />
      </GlassCard>
      <GlassCard className="p-5">
        <h2 className="text-lg font-medium">Historical market context</h2>
        <p className="mt-1 text-sm text-slate-500">{source}. This is not silently replaced with another geography.</p>
        <dl className="mt-4 grid gap-3 sm:grid-cols-2">
          <Row term="Prior median price per sqm" value={formatPsm(result.community_prior_median_psm)} />
          <Row term="Latest quarter sales" value={result.market_trend.available ? formatNumber(result.market_trend.transactions) : "Unavailable"} />
          <Row term="YoY median change" value={result.market_trend.yoy_median_psm_growth_pct == null ? "Not reported" : formatPercent(result.market_trend.yoy_median_psm_growth_pct) ?? "Not reported"} />
          <Row term="Reliability" value={result.reliability.level} />
        </dl>
        <p className="mt-3 text-xs leading-5 text-slate-500">{result.reliability.definition} {result.reliability.reasons.join(" ")}</p>
      </GlassCard>
      <GlassCard className="p-5">
        <h2 className="text-lg font-medium">Comparable sales</h2>
        {result.comparables.message ? <p className="mt-2 text-sm text-amber-800">{result.comparables.message}</p> : null}
        <ComparableSalesTable rows={result.comparables.comparables} valuationDate={result.valuation_date} />
      </GlassCard>
    </div>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return <div className="flex items-baseline justify-between gap-4 border-b border-slate-100 py-2"><dt className="text-slate-500">{term}</dt><dd className="font-mono text-slate-900">{value}</dd></div>;
}

export function ComparableSalesTable({ rows, valuationDate }: { rows: ComparableSale[]; valuationDate: string }) {
  const [sort, setSort] = useState<keyof ComparableSale>("similarity_score");
  const [open, setOpen] = useState<string | null>(null);
  const ordered = useMemo(() => [...rows].filter((row) => row.transaction_date < valuationDate).sort((a, b) => {
    const left = a[sort] ?? "";
    const right = b[sort] ?? "";
    return left > right ? -1 : 1;
  }), [rows, sort, valuationDate]);
  if (!ordered.length) return <p className="mt-3 text-sm text-slate-500">No comparable sales were returned before the valuation date.</p>;
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm">
        <thead className="text-xs text-slate-500 uppercase"><tr>
          {(["community", "property_type", "bedrooms", "size_sqm", "transaction_date", "transaction_price_aed", "price_per_sqm", "similarity_score"] as const).map((key) => (
            <th key={key} className="pb-2 pr-3"><button onClick={() => setSort(key)}>{key.replaceAll("_", " ")}</button></th>
          ))}
        </tr></thead>
        <tbody>
          {ordered.map((row) => (
            <tr key={row.transaction_id} className="border-t border-slate-100">
              <td className="py-2 pr-3">{row.community}</td>
              <td className="py-2">{row.property_type}</td>
              <td className="py-2">{row.bedrooms ?? "—"}</td>
              <td className="py-2 font-mono">{row.size_sqm.toFixed(0)}</td>
              <td className="py-2">{formatDate(row.transaction_date)}</td>
              <td className="py-2 font-mono">{formatAed(row.transaction_price_aed)}</td>
              <td className="py-2 font-mono">{formatNumber(row.price_per_sqm)}</td>
              <td className="py-2">
                <button className="text-sky-700" onClick={() => setOpen(open === row.transaction_id ? null : row.transaction_id)}>{row.similarity_score.toFixed(2)}</button>
                {open === row.transaction_id ? <p className="mt-1 text-xs text-slate-500">Transaction {row.transaction_id}. Building {row.building_name_en ?? "not recorded"}. Project {row.project_name_en ?? "not recorded"}. {row.registration_type ?? ""}</p> : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
