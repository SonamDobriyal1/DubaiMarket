"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { DubaiMap } from "@/components/maps/dubai-map";
import { ErrorState } from "@/components/shared/surface";
import { api, isApiError } from "@/lib/api/client";
import type { CommunitySummary, ExplorerResponse, MapPayload, RegistryCommunity } from "@/lib/api/types";
import { formatAed, formatNumber, formatPercent, formatPsm, formatRatioPercent } from "@/lib/formatters";
import { colorForValue, metricValue, type MapMetric } from "@/lib/map-metric";

const METRICS: { id: MapMetric; label: string }[] = [
  { id: "price", label: "Price" },
  { id: "growth", label: "Growth" },
  { id: "volume", label: "Volume" },
  { id: "volatility", label: "Volatility" },
  { id: "offplan", label: "Off-plan" },
];

export default function ExplorerPage() {
  const [kind, setKind] = useState<"master_project" | "official_area">("master_project");
  const [query, setQuery] = useState("");
  const [propertyType, setPropertyType] = useState("");
  const [registration, setRegistration] = useState("");
  const [bedrooms, setBedrooms] = useState("");
  const [metric, setMetric] = useState<MapMetric>("price");
  const [selected, setSelected] = useState("master__dubai-marina");
  const filtered = Boolean(propertyType || registration || bedrooms);
  const map = useQuery({ queryKey: ["map", kind], queryFn: () => api<MapPayload>(`/api/map/communities?kind=${kind}`) });
  const base = useQuery({ queryKey: ["communities", kind], queryFn: () => api<{ communities: CommunitySummary[] }>(`/api/communities?kind=${kind}`), enabled: !filtered });
  const explorer = useQuery({
    queryKey: ["explorer", kind, propertyType, registration, bedrooms],
    enabled: filtered,
    queryFn: () => api<ExplorerResponse>(`/api/market/explorer?kind=${kind}${propertyType ? `&property_type=${propertyType}` : ""}${registration ? `&registration_type=${encodeURIComponent(registration)}` : ""}${bedrooms ? `&bedrooms=${bedrooms}` : ""}`),
  });
  const registry = useQuery({ queryKey: ["registry"], queryFn: () => api<{ communities: RegistryCommunity[] }>("/api/communities/registry") });
  const metrics = filtered ? explorer.data?.communities ?? [] : base.data?.communities ?? [];
  const metricById = useMemo(() => new Map(metrics.map((row) => [row.community_id, row])), [metrics]);
  const needle = query.trim().toLowerCase();
  const located = useMemo(() => {
    return (map.data?.communities ?? []).flatMap((community) => {
      if (community.latitude == null || community.longitude == null) return [];
      const stats = metricById.get(community.community_id);
      if (!stats) return [];
      const nameMatches = !needle || stats.community_name.toLowerCase().includes(needle) || (needle === "downtown dubai" && stats.community_name === "DownTown Dubai");
      if (!nameMatches) return [];
      return [{ ...stats, latitude: community.latitude, longitude: community.longitude, location_label: community.location_label ?? null }];
    });
  }, [map.data, metricById, needle]);
  const coloredValues = located.map((row) => metricValue(row, metric)).filter((value): value is number => value != null);
  const pins = located.map((row) => ({
    community_id: row.community_id,
    community_name: row.community_name,
    latitude: row.latitude,
    longitude: row.longitude,
    color: colorForValue(metricValue(row, metric), coloredValues, metric === "growth"),
  }));
  const cards = [...located].sort((a, b) => b.transactions - a.transactions).slice(0, 12);
  const current = located.find((row) => row.community_id === selected) ?? null;
  const gardens = (registry.data?.communities ?? []).find((row) => row.community_name === "The Gardens");
  const showGardens = gardens != null && gardens.residential_primary_sales === 0 && (needle.includes("garden") || needle === "");

  return (
    <div className="relative -mx-4 -my-6 h-[calc(100dvh-3.25rem)] overflow-hidden sm:h-[calc(100dvh-4.25rem)] md:-mx-8 md:-my-8">
      {map.isLoading ? <div className="h-full animate-pulse bg-[#d7e3ea]" /> : map.data ? <DubaiMap payload={map.data} pins={pins} selectedId={current?.community_id} onSelect={setSelected} /> : <div className="flex h-full items-center justify-center bg-[#e7eef2] p-8"><ErrorState title="Map data failed" body={isApiError(map.error) ? map.error.message : "No map payload."} /></div>}

      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="pointer-events-auto mx-2 mt-2 flex justify-center xl:absolute xl:top-4 xl:left-1/2 xl:mx-0 xl:mt-0 xl:-translate-x-1/2">
          <div className="flex rounded-full bg-white/95 p-1 shadow-lg">
            <span className="rounded-full bg-slate-900 px-3 py-1.5 text-sm text-white sm:px-4">Explore</span>
            <Link href={current ? `/valuation?community=${encodeURIComponent(current.community_name)}` : "/valuation"} className="rounded-full px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 sm:px-4">Value</Link>
            <Link href="/compare" className="rounded-full px-3 py-1.5 text-sm text-slate-600 hover:text-slate-900 sm:px-4">Compare</Link>
          </div>
        </div>

        <div className="pointer-events-auto mx-2 mt-2 w-[calc(100%-1rem)] overflow-x-auto xl:absolute xl:top-[4.25rem] xl:left-1/2 xl:mx-0 xl:mt-0 xl:w-auto xl:max-w-[calc(100%-2rem)] xl:-translate-x-1/2">
          <div className="flex w-max gap-1 rounded-full bg-white/95 p-1 shadow-lg">
            {METRICS.map((item) => (
              <button key={item.id} onClick={() => setMetric(item.id)} className={`rounded-full px-3 py-1.5 text-sm whitespace-nowrap ${metric === item.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="pointer-events-auto mx-2 mt-2 flex flex-col gap-2 xl:absolute xl:top-4 xl:left-4 xl:mx-0 xl:mt-0 xl:w-80">
          <input aria-label="Find a community" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search a community" className="w-full rounded-full border border-white/70 bg-white/95 px-4 py-2 text-sm text-slate-800 shadow-lg outline-none" />
          <div className="flex flex-wrap gap-1">
            <select aria-label="Geography" value={kind} onChange={(event) => setKind(event.target.value as "master_project" | "official_area")} className="max-w-full rounded-full bg-white/95 px-3 py-1.5 text-xs text-slate-700 shadow"><option value="master_project">Master projects</option><option value="official_area">Official areas</option></select>
            <select aria-label="Property type filter" value={propertyType} onChange={(event) => setPropertyType(event.target.value)} className="max-w-full rounded-full bg-white/95 px-3 py-1.5 text-xs text-slate-700 shadow"><option value="">All types</option><option value="Unit">Unit</option><option value="Villa">Villa</option></select>
            <select aria-label="Registration filter" value={registration} onChange={(event) => setRegistration(event.target.value)} className="max-w-full rounded-full bg-white/95 px-3 py-1.5 text-xs text-slate-700 shadow"><option value="">All registrations</option><option>Existing Properties</option><option>Off-Plan Properties</option></select>
            <select aria-label="Bedrooms filter" value={bedrooms} onChange={(event) => setBedrooms(event.target.value)} className="max-w-full rounded-full bg-white/95 px-3 py-1.5 text-xs text-slate-700 shadow"><option value="">All bedrooms</option>{[0, 1, 2, 3, 4, 5].map((count) => <option key={count} value={count}>{count === 0 ? "Studio" : `${count} bed`}</option>)}</select>
          </div>
        </div>

        {current ? (
          <aside className="pointer-events-auto absolute top-24 right-4 hidden w-[320px] rounded-2xl bg-white/95 p-4 text-slate-800 shadow-xl xl:block">
            <Insight community={current} filtered={filtered} />
          </aside>
        ) : null}

        <div className="pointer-events-auto absolute inset-x-0 bottom-0 bg-gradient-to-t from-white/90 to-transparent px-2 pt-6 pb-2 sm:px-4 sm:pb-3">
          {current ? (
            <div className="mb-2 rounded-2xl bg-white/95 px-3 py-2 text-slate-800 shadow-lg xl:hidden">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">{current.community_name}</p>
                  <p className="text-xs text-slate-500">{formatNumber(current.transactions)} sales · {formatPsm(current.median_psm)} · YoY {formatPercent(current.yoy_growth_pct) ?? "not reported"}</p>
                </div>
              </div>
              <div className="mt-1 flex flex-wrap gap-3 text-xs">
                <Link className="text-sky-700" href={`/communities/${current.community_id}`}>Community history</Link>
                <Link className="text-sky-700" href={`/valuation?community=${encodeURIComponent(current.community_name)}`}>Value a property</Link>
              </div>
            </div>
          ) : null}
          {showGardens ? <p className={`mb-2 max-w-xl text-xs text-slate-600 ${needle === "" ? "hidden xl:block" : ""}`}>The Gardens has no qualifying primary residential sales, so it is not pinned and has no sale price.</p> : null}
          {filtered && metric === "volatility" ? <p className="mb-2 text-xs text-slate-600">Time-series volatility is omitted while a filter is on, so those pins stay neutral.</p> : null}
          <div className="flex snap-x gap-3 overflow-x-auto pb-1">
            {cards.map((row) => {
              const color = pins.find((pin) => pin.community_id === row.community_id)?.color ?? "#94A3B8";
              const active = current?.community_id === row.community_id;
              return (
                <button key={row.community_id} onClick={() => setSelected(row.community_id)} className={`min-w-44 shrink-0 snap-start rounded-2xl bg-white p-3 text-left shadow-lg sm:min-w-56 ${active ? "ring-2 ring-slate-900" : ""}`}>
                  <span className="block h-1.5 w-10 rounded-full" style={{ background: color }} />
                  <p className="mt-2 truncate text-sm font-semibold text-slate-900">{row.community_name}</p>
                  <p className="text-xs text-slate-500">{formatNumber(row.transactions)} registered sales</p>
                  <p className="mt-2 font-mono text-base text-slate-900 sm:text-lg">{metricText(row, metric)}</p>
                  <p className="text-[11px] tracking-wide text-slate-400 uppercase">{metricCaption(metric)}</p>
                </button>
              );
            })}
          </div>
          <p className="mt-2 line-clamp-2 max-w-3xl text-[11px] leading-4 text-slate-500 xl:line-clamp-none">{map.data?.geometry_note}</p>
        </div>
      </div>
    </div>
  );
}

function Insight({ community, filtered, compact = false }: { community: CommunitySummary & { location_label?: string | null }; filtered: boolean; compact?: boolean }) {
  return (
    <div className="space-y-3">
      <div>
        <p className="text-[11px] tracking-[0.16em] text-slate-400 uppercase">{community.community_kind === "official_area" ? "Official area" : "Master project"}{filtered ? " · filtered sales" : ""}</p>
        <h2 className="text-xl font-semibold text-slate-900">{community.community_name}</h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">Medians of registered primary residential sales. This is not an appraisal of a specific unit.</p>
      </div>
      <div className={`grid grid-cols-2 gap-2 ${compact ? "" : ""}`}>
        <Stat label="Median price" value={formatAed(community.median_price_aed)} />
        <Stat label="Median AED/sqm" value={formatPsm(community.median_psm)} />
        <Stat label="Sales" value={formatNumber(community.transactions)} />
        <Stat label="YoY median AED/sqm" value={formatPercent(community.yoy_growth_pct) ?? "Not reported"} />
        {compact ? null : <Stat label="QoQ median AED/sqm" value={formatPercent(community.qoq_growth_pct) ?? "Not reported"} />}
        {compact ? null : <Stat label="Off-plan share" value={formatRatioPercent(community.share_offplan) ?? "—"} />}
        {compact ? null : <Stat label="Price dispersion" value={formatRatioPercent(community.cross_sectional_dispersion) ?? "—"} />}
        {compact ? null : <Stat label="Volatility" value={community.time_series_volatility == null ? "Not reported" : community.time_series_volatility.toFixed(3)} />}
      </div>
      {community.location_label ? <p className="text-[11px] leading-4 text-slate-500">Map position: {community.location_label}. This is an OpenStreetMap place centroid, not a Land Department coordinate.</p> : null}
      <div className="flex flex-wrap gap-3 text-sm">
        <Link className="text-sky-700" href={`/communities/${community.community_id}`}>Community history</Link>
        <Link className="text-sky-700" href={`/valuation?community=${encodeURIComponent(community.community_name)}`}>Value a property</Link>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-2.5 py-2">
      <p className="text-[10px] tracking-wide text-slate-400 uppercase">{label}</p>
      <p className="mt-1 font-mono text-xs break-words text-slate-900 sm:text-sm">{value}</p>
    </div>
  );
}

function metricText(row: CommunitySummary, metric: MapMetric) {
  if (metric === "price") return formatPsm(row.median_psm);
  if (metric === "growth") return formatPercent(row.yoy_growth_pct) ?? "Not reported";
  if (metric === "volume") return `${formatNumber(row.transactions)} sales`;
  if (metric === "volatility") return row.time_series_volatility == null ? "Not reported" : row.time_series_volatility.toFixed(3);
  return formatRatioPercent(row.share_offplan) ?? "—";
}

function metricCaption(metric: MapMetric) {
  if (metric === "price") return "Median AED/sqm";
  if (metric === "growth") return "YoY median AED/sqm";
  if (metric === "volume") return "Registered sales";
  if (metric === "volatility") return "Quarterly volatility";
  return "Off-plan share";
}
