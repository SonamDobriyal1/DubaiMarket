"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { DistributionChart, TrendChart, VolumeChart } from "@/components/charts/market-charts";
import { DataFreshness, EmptyState, ErrorState, GlassCard, LoadingSkeleton, MetricCard, PageHeader } from "@/components/shared/surface";
import { api, isApiError } from "@/lib/api/client";
import type { CommunityDetail, CommunityTrends } from "@/lib/api/types";
import { formatAed, formatCompact, formatDate, formatNumber, formatPercent, formatPsm, formatRatioPercent } from "@/lib/formatters";

export default function CommunityPage() {
  const params = useParams<{ slug: string }>();
  const id = decodeURIComponent(params.slug);
  const detail = useQuery({ queryKey: ["community", id], queryFn: () => api<CommunityDetail>(`/api/communities/${id}`) });
  const trends = useQuery({ queryKey: ["trends", id], queryFn: () => api<CommunityTrends>(`/api/communities/${id}/trends`), enabled: detail.isSuccess });
  if (detail.isLoading) return <LoadingSkeleton className="h-80" />;
  if (detail.isError || !detail.data) return <ErrorState title="Community not in the qualifying-sales summary" body={isApiError(detail.error) ? detail.error.message : "This community has no published residential-sale metrics."} />;
  const community = detail.data;
  const quarterly = (trends.data?.quarterly ?? []).filter((point) => point.median_psm != null).map((point) => ({ period: point.quarter ?? "", transactions: point.transactions, total_value_aed: 0, median_psm: point.median_psm ?? 0, median_price_aed: point.median_price_aed ?? 0 }));
  const monthly = (trends.data?.monthly ?? []).map((point) => ({ period: point.year_month ?? "", transactions: point.transactions, total_value_aed: 0, median_psm: point.median_psm ?? 0, median_price_aed: point.median_price_aed ?? 0 }));
  const growth = (trends.data?.quarterly ?? []).filter((point) => point.yoy_median_psm_growth_pct != null).map((point) => ({ quarter: point.quarter ?? "", yoy_median_psm_growth_pct: point.yoy_median_psm_growth_pct }));
  return (
    <div>
      <PageHeader title={community.community_name} subtitle={community.community_kind === "official_area" ? "Official area statistics. These are not a master-project alias." : "Master-project statistics. The official area is not substituted unless the record says so."} aside={<DataFreshness date={formatDate(community.last_transaction)} />} />
      <p className="mb-4 text-sm text-slate-500">{formatNumber(community.transactions)} qualifying sales from {formatDate(community.first_transaction)} to {formatDate(community.last_transaction)}.</p>
      <div className="mb-4 flex flex-wrap gap-3 text-sm">
        <Link className="text-sky-700" href={`/compare?community=${community.community_id}`}>Compare this community</Link>
        <Link className="text-sky-700" href={`/explorer?community=${community.community_id}`}>Explore</Link>
        <Link className="text-sky-700" href={`/valuation?community=${encodeURIComponent(community.community_name)}`}>Value a property here</Link>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <MetricCard label="Median sale price" value={formatAed(community.median_price_aed)} />
        <MetricCard label="Median price per sqm" value={formatPsm(community.median_psm)} />
        <MetricCard label="Transaction count" value={formatNumber(community.transactions)} />
        <MetricCard label="Total value" value={formatCompact(community.total_value_aed)} />
        <MetricCard label="YoY growth" value={formatPercent(community.yoy_growth_pct) ?? "Not reported"} detail="Blank when either period is below the minimum sample." />
        <MetricCard label="Price dispersion" value={formatRatioPercent(community.cross_sectional_dispersion) ?? "—"} detail="MAD of price per sqm divided by the median. Not time-series volatility." />
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <GlassCard className="p-5"><h2 className="mb-3 font-medium">Price per sqm</h2>{quarterly.length ? <TrendChart data={quarterly} label="Quarterly median price per sqm" /> : <EmptyState title="No price series" body="Quarterly medians are unavailable." />}</GlassCard>
        <GlassCard className="p-5"><h2 className="mb-3 font-medium">Monthly volume</h2>{monthly.length ? <VolumeChart data={monthly} /> : <EmptyState title="No monthly volume" body="Monthly counts are unavailable." />}</GlassCard>
        <GlassCard className="p-5"><h2 className="mb-3 font-medium">Property type</h2>{community.property_types?.length ? <DistributionChart data={community.property_types} nameKey="property_type" valueKey="transactions" caption="Transactions by property type" /> : <EmptyState title="No type split" body="Property-type counts were not returned." />}</GlassCard>
        <GlassCard className="p-5"><h2 className="mb-3 font-medium">Bedrooms</h2>{community.bedrooms?.length ? <DistributionChart data={community.bedrooms} nameKey="bedrooms" valueKey="transactions" caption="Transactions by bedroom count" /> : <EmptyState title="No bedroom split" body="Bedroom counts were not returned." />}</GlassCard>
        <GlassCard className="p-5">
          <h2 className="mb-3 font-medium">Existing and off-plan</h2>
          <DistributionChart data={[{ name: "Existing", transactions: Math.round((community.share_existing ?? 0) * (community.transactions ?? 0)) }, { name: "Off-plan", transactions: Math.round((community.share_offplan ?? 0) * (community.transactions ?? 0)) }]} nameKey="name" valueKey="transactions" caption="Existing versus off-plan sales" />
        </GlassCard>
        <GlassCard className="p-5">
          <h2 className="mb-1 font-medium">Price spread</h2>
          <p className="mb-3 text-xs text-slate-500">Observed 25th percentile, median, and 75th percentile of price per sqm. This is not a histogram of individual sales.</p>
          <p className="font-mono text-sm">{formatPsm(community.p25_psm)} · {formatPsm(community.median_psm)} · {formatPsm(community.p75_psm)}</p>
        </GlassCard>
        <GlassCard className="p-5 xl:col-span-2">
          <h2 className="mb-1 font-medium">Year-over-year change</h2>
          <p className="mb-3 text-xs text-slate-500">Quarters without enough sales in both years are omitted.</p>
          {growth.length ? <DistributionChart data={growth} nameKey="quarter" valueKey="yoy_median_psm_growth_pct" caption="Reported year over year growth" /> : <EmptyState title="Growth is not reported" body="Neither the latest comparison nor earlier quarters cleared the sample minimum." />}
        </GlassCard>
      </div>
      <GlassCard className="mt-4 p-5 text-sm leading-6 text-slate-600">
        <h2 className="mb-2 font-medium text-slate-900">Coverage</h2>
        <p>Time-series volatility {community.time_series_volatility == null ? "is not reported because there are not enough quarterly changes." : `is ${community.time_series_volatility.toFixed(3)}, the standard deviation of quarterly median changes.`} Cross-sectional dispersion remains a separate snapshot of how sale prices per sqm differ from each other.</p>
      </GlassCard>
    </div>
  );
}
