"use client";

import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { DistributionChart, TrendChart, VolumeChart } from "@/components/charts/market-charts";
import { MarketDataTable } from "@/components/communities/community-table";
import { DataFreshness, EmptyState, ErrorState, GlassCard, LoadingSkeleton, MetricCard, PageHeader } from "@/components/shared/surface";
import { api, isApiError } from "@/lib/api/client";
import type { CommunitySummary, MarketOverview, MarketSeries } from "@/lib/api/types";
import { formatAed, formatCompact, formatDate, formatNumber, formatPsm } from "@/lib/formatters";

export default function DashboardPage() {
  const [grain, setGrain] = useState<"quarter" | "month">("quarter");
  const [propertyType, setPropertyType] = useState("");
  const [registration, setRegistration] = useState("");
  const [fullHistory, setFullHistory] = useState(false);
  const overview = useQuery({ queryKey: ["overview"], queryFn: () => api<MarketOverview>("/api/market/overview") });
  const series = useQuery({
    queryKey: ["series", grain, propertyType, registration],
    queryFn: () => api<MarketSeries>(`/api/market/series?grain=${grain}${propertyType ? `&property_type=${propertyType}` : ""}${registration ? `&registration_type=${encodeURIComponent(registration)}` : ""}`),
  });
  const communities = useQuery({ queryKey: ["communities", "master"], queryFn: () => api<{ communities: CommunitySummary[] }>("/api/communities?kind=master_project") });
  const chart = useMemo(() => {
    const points = series.data?.series ?? [];
    return fullHistory ? points : points.filter((point) => point.period >= (grain === "month" ? "2015-01" : "2015Q1"));
  }, [series.data, fullHistory, grain]);
  const growth = (communities.data?.communities ?? []).filter((row) => row.yoy_growth_pct != null).sort((a, b) => (b.yoy_growth_pct ?? 0) - (a.yoy_growth_pct ?? 0)).slice(0, 8);

  if (overview.isError) return <ErrorState title="Market overview is unavailable" body={isApiError(overview.error) ? overview.error.message : "The analytics service did not respond."} />;

  return (
    <div>
      <PageHeader eyebrow="Historical record" title="Dubai Real Estate Intelligence" subtitle="Understand property value, market dynamics, and transaction behavior through data." aside={<DataFreshness date={formatDate(overview.data?.date_max)} />} />
      <p className="mb-5 max-w-3xl text-sm leading-6 text-slate-500">Figures below describe qualifying residential sales in the transaction extract. They are not a live quote of current asking prices, and they are separate from the model&apos;s test-set error.</p>
      {overview.isLoading ? <div className="grid gap-3 md:grid-cols-3"><LoadingSkeleton className="h-28" /><LoadingSkeleton className="h-28" /><LoadingSkeleton className="h-28" /></div> : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <MetricCard label="Qualifying residential sales" value={formatNumber(overview.data?.transactions)} detail={overview.data?.population} />
          <MetricCard label="Total qualifying value" value={formatCompact(overview.data?.total_value_aed)} detail="Sum of recorded sale consideration, AED" />
          <MetricCard label="Median sale price" value={formatAed(overview.data?.median_price_aed)} />
          <MetricCard label="Median price per sqm" value={formatPsm(overview.data?.median_psm)} />
          <MetricCard label="Communities in the summary" value={formatNumber(communities.data?.communities.length)} detail="Master projects with at least one qualifying sale" />
          <MetricCard label="Latest transaction" value={formatDate(overview.data?.date_max)} detail={`Series begins ${formatDate(overview.data?.date_min)}. Latest complete quarter ${overview.data?.latest_complete_quarter}.`} />
        </div>
      )}
      <GlassCard className="mt-6 p-5">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="text-lg font-medium">Dubai Residential Price Trends</h2>
            <p className="text-sm text-slate-500">Median price per square metre for the filtered qualifying sales.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-sm">
            <select aria-label="Time grain" value={grain} onChange={(event) => setGrain(event.target.value as "quarter" | "month")} className="rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2"><option value="quarter">Quarterly</option><option value="month">Monthly</option></select>
            <select aria-label="Property type" value={propertyType} onChange={(event) => setPropertyType(event.target.value)} className="rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2"><option value="">All types</option><option value="Unit">Unit</option><option value="Villa">Villa</option></select>
            <select aria-label="Registration" value={registration} onChange={(event) => setRegistration(event.target.value)} className="rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2"><option value="">Existing and off-plan</option><option>Existing Properties</option><option>Off-Plan Properties</option></select>
            <button className="rounded-xl border border-slate-200 px-3 py-2" onClick={() => setFullHistory((value) => !value)}>{fullHistory ? "From 2015" : "Full history"}</button>
          </div>
        </div>
        {series.isLoading ? <LoadingSkeleton className="h-80" /> : series.isError ? <ErrorState title="Trend data failed to load" body={isApiError(series.error) ? series.error.message : "Request failed."} /> : chart.length ? <TrendChart data={chart} label="Median residential price per square metre" /> : <EmptyState title="No sales in this filter" body="The selected property type and registration have no qualifying transactions." />}
      </GlassCard>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <GlassCard className="p-5"><h2 className="mb-3 text-lg font-medium">Transaction volume</h2>{chart.length ? <VolumeChart data={chart} /> : <EmptyState title="No volume series" body="Change the filters or the history window." />}</GlassCard>
        <GlassCard className="p-5"><h2 className="mb-3 text-lg font-medium">Existing versus off-plan</h2>{series.data?.registration_mix.length ? <DistributionChart data={series.data.registration_mix} nameKey="reg_type_en" valueKey="transactions" caption="Sales by registration type" /> : <EmptyState title="No registration mix" body="This filter returned no sales." />}</GlassCard>
        <GlassCard className="p-5"><h2 className="mb-3 text-lg font-medium">Property type</h2>{series.data?.property_type_mix.length ? <DistributionChart data={series.data.property_type_mix} nameKey="property_type_en" valueKey="transactions" caption="Sales by property type" /> : <EmptyState title="No property-type mix" body="This filter returned no sales." />}</GlassCard>
        <GlassCard className="p-5">
          <h2 className="mb-1 text-lg font-medium">Historical growth</h2>
          <p className="mb-3 text-xs text-slate-500">Year-over-year median price per sqm where both periods have enough sales. Missing rates are omitted, not shown as zero.</p>
          {growth.length ? <DistributionChart data={growth.map((row) => ({ community_name: row.community_name, yoy_growth_pct: row.yoy_growth_pct }))} nameKey="community_name" valueKey="yoy_growth_pct" caption="Year over year growth for communities with a reported rate" /> : <EmptyState title="Growth is not reported" body="No master project in this summary has both periods above the minimum sample." />}
        </GlassCard>
      </div>
      <GlassCard className="mt-4 p-5">
        <h2 className="mb-1 text-lg font-medium">Community analytics</h2>
        <p className="mb-4 text-xs text-slate-500">Published master-project summary for all qualifying sales. Price dispersion is cross-sectional MAD divided by the median, not time-series volatility. Growth stays blank when a period is too thin.</p>
        {communities.data ? <MarketDataTable rows={communities.data.communities} /> : <LoadingSkeleton className="h-48" />}
      </GlassCard>
    </div>
  );
}
