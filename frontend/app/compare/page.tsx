"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ComparisonChart, DistributionChart } from "@/components/charts/market-charts";
import { EmptyState, ErrorState, GlassCard, PageHeader } from "@/components/shared/surface";
import { Button } from "@/components/ui/primitives";
import { api, isApiError } from "@/lib/api/client";
import type { CommunitySummary, ComparisonResponse } from "@/lib/api/types";
import { formatAed, formatNumber, formatPercent, formatPsm, formatRatioPercent } from "@/lib/formatters";
import { comparisonObservations } from "@/lib/insights";

export default function ComparePage() {
  const communities = useQuery({ queryKey: ["communities", "master"], queryFn: () => api<{ communities: CommunitySummary[] }>("/api/communities?kind=master_project") });
  const [selected, setSelected] = useState<string[]>(["master__dubai-marina", "master__downtown-dubai"]);
  const [propertyType, setPropertyType] = useState("");
  const [registration, setRegistration] = useState("");
  const [bedrooms, setBedrooms] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sizeMin, setSizeMin] = useState("");
  const [sizeMax, setSizeMax] = useState("");
  const mutation = useMutation({
    mutationFn: () => api<ComparisonResponse>("/api/communities/compare", {
      method: "POST",
      body: JSON.stringify({
        communities: selected.map((community_id) => ({ community_id })),
        property_type: propertyType || null,
        registration_type: registration || null,
        bedrooms: bedrooms === "" ? null : Number(bedrooms),
        date_from: dateFrom || null,
        date_to: dateTo || null,
        size_min: sizeMin === "" ? null : Number(sizeMin),
        size_max: sizeMax === "" ? null : Number(sizeMax),
      }),
    }),
  });
  const names = new Map((communities.data?.communities ?? []).map((row) => [row.community_id, row.community_name]));
  const chart = useMemo(() => {
    const result = mutation.data;
    if (!result) return [];
    const periods = new Set<string>();
    result.communities.forEach((community) => community.quarterly.forEach((point) => periods.add(point.quarter)));
    return [...periods].sort().map((period) => {
      const row: { period: string; [key: string]: string | number | null } = { period };
      result.communities.forEach((community) => {
        row[community.community_name] = community.quarterly.find((point) => point.quarter === period)?.median_psm ?? null;
      });
      return row;
    });
  }, [mutation.data]);

  function toggle(id: string) {
    setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length >= 5 ? current : [...current, id]);
  }

  return (
    <div>
      <PageHeader title="Area comparison" subtitle="Compare two to five communities on the same dates, property type, bedrooms, registration, and size range." />
      <GlassCard className="p-5">
        <div className="grid gap-3 md:grid-cols-3">
          <label className="text-sm text-slate-500">From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2 text-slate-900" /></label>
          <label className="text-sm text-slate-500">To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2 text-slate-900" /></label>
          <label className="text-sm text-slate-500">Property type<select value={propertyType} onChange={(event) => setPropertyType(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2"><option value="">All</option><option value="Unit">Unit</option><option value="Villa">Villa</option></select></label>
          <label className="text-sm text-slate-500">Bedrooms<select value={bedrooms} onChange={(event) => setBedrooms(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2"><option value="">All</option>{[0, 1, 2, 3, 4, 5].map((count) => <option key={count} value={count}>{count}</option>)}</select></label>
          <label className="text-sm text-slate-500">Registration<select value={registration} onChange={(event) => setRegistration(event.target.value)} className="mt-1 w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2"><option value="">All</option><option>Existing Properties</option><option>Off-Plan Properties</option></select></label>
          <label className="text-sm text-slate-500">Size range, sqm<span className="mt-1 flex gap-2"><input value={sizeMin} onChange={(event) => setSizeMin(event.target.value)} placeholder="Min" className="w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2" /><input value={sizeMax} onChange={(event) => setSizeMax(event.target.value)} placeholder="Max" className="w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2" /></span></label>
        </div>
        <div className="mt-4 max-h-48 overflow-auto rounded-xl border border-slate-200 p-2">
          {(communities.data?.communities ?? []).map((community) => (
            <label key={community.community_id} className="flex items-center gap-2 px-2 py-1 text-sm">
              <input type="checkbox" checked={selected.includes(community.community_id)} onChange={() => toggle(community.community_id)} />
              {community.community_name}
            </label>
          ))}
        </div>
        <p className="mt-2 text-xs break-words text-slate-500">{selected.length} selected. {selected.map((id) => names.get(id) ?? id).join(", ")}</p>
        <Button className="mt-3" disabled={selected.length < 2 || mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? "Comparing…" : "Compare"}</Button>
      </GlassCard>
      {mutation.isError ? <div className="mt-4"><ErrorState title="Comparison failed" body={isApiError(mutation.error) ? mutation.error.message : "The comparison did not return."} /></div> : null}
      {mutation.data ? (
        <div className="mt-4 space-y-4">
          <p className="text-sm text-slate-500">{mutation.data.equivalent_population} {mutation.data.comparison_quarter ? `Growth uses ${mutation.data.comparison_quarter} against the same quarter a year earlier when both have enough sales.` : "No complete comparison quarter is available."}</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {mutation.data.communities.map((community) => (
              <GlassCard key={community.community_id} className="p-4">
                <h2 className="text-lg font-medium">{community.community_name}</h2>
                <p className="text-xs text-slate-500">{community.community_kind === "official_area" ? "Official area" : "Master project"}</p>
                {community.metrics ? (
                  <div className="mt-3 space-y-1 text-sm">
                    <p>Median price {formatAed(community.metrics.median_price_aed)}</p>
                    <p>Median {formatPsm(community.metrics.median_psm)}</p>
                    <p>Sales {formatNumber(community.transactions)}</p>
                    <p>YoY {formatPercent(community.yoy_growth_pct) ?? "Not reported"}</p>
                    <p>Dispersion {formatRatioPercent(community.metrics.cross_sectional_dispersion) ?? "—"}</p>
                    <p>Existing {formatRatioPercent(community.metrics.share_existing) ?? "—"} · Off-plan {formatRatioPercent(community.metrics.share_offplan) ?? "—"}</p>
                    <p>Unit {formatRatioPercent(community.metrics.share_unit) ?? "—"} · Villa {formatRatioPercent(community.metrics.share_villa) ?? "—"}</p>
                    {community.insufficient_sample ? <p className="text-amber-800">Sample is below the minimum used for growth.</p> : null}
                  </div>
                ) : <p className="mt-3 text-sm text-slate-500">No sales match these filters.</p>}
              </GlassCard>
            ))}
          </div>
          <GlassCard className="p-5">
            <h2 className="mb-3 font-medium">Median price per sqm</h2>
            {chart.length ? <ComparisonChart data={chart} /> : <EmptyState title="No overlapping quarters" body="The filtered sales do not have a quarterly median series." />}
          </GlassCard>
          <GlassCard className="p-5">
            <h2 className="mb-3 font-medium">Transaction volume</h2>
            <DistributionChart data={mutation.data.communities.map((community) => ({ community_name: community.community_name, transactions: community.transactions }))} nameKey="community_name" valueKey="transactions" caption="Filtered transaction counts" />
          </GlassCard>
          <GlassCard className="p-5">
            <h2 className="mb-2 font-medium">What the figures support</h2>
            <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-600">{comparisonObservations(mutation.data.communities).map((note) => <li key={note}>{note}</li>)}</ul>
          </GlassCard>
        </div>
      ) : null}
    </div>
  );
}
