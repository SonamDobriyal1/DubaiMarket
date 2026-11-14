"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { CommunitySummary } from "@/lib/api/types";
import { formatDate, formatNumber, formatPercent, formatPsm, formatRatioPercent } from "@/lib/formatters";

type SortKey = "community_name" | "median_psm" | "transactions" | "yoy_growth_pct" | "cross_sectional_dispersion" | "last_transaction";

export function MarketDataTable({ rows, empty }: { rows: CommunitySummary[]; empty?: string }) {
  const [sort, setSort] = useState<SortKey>("transactions");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [query, setQuery] = useState("");
  const visible = useMemo(() => {
    const filtered = rows.filter((row) => row.community_name.toLowerCase().includes(query.trim().toLowerCase()));
    return [...filtered].sort((a, b) => {
      const left = a[sort] ?? "";
      const right = b[sort] ?? "";
      const result = left > right ? 1 : left < right ? -1 : 0;
      return direction === "asc" ? result : -result;
    });
  }, [rows, query, sort, direction]);

  function toggle(key: SortKey) {
    if (sort === key) setDirection(direction === "asc" ? "desc" : "asc");
    else {
      setSort(key);
      setDirection(key === "community_name" ? "asc" : "desc");
    }
  }

  if (!rows.length) return <p className="text-sm text-slate-500">{empty ?? "No communities match this view."}</p>;

  return (
    <div>
      <input aria-label="Filter communities" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter this table" className="mb-3 w-full rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2 text-sm md:max-w-xs" />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <caption className="sr-only">Community analytics</caption>
          <thead className="text-xs tracking-wide text-slate-500 uppercase">
            <tr>{header("Community", "community_name")}{header("Median AED/sqm", "median_psm")}{header("Sales", "transactions")}{header("YoY growth", "yoy_growth_pct")}{header("Price dispersion", "cross_sectional_dispersion")}{header("Last sale", "last_transaction")}</tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.community_id} className="border-t border-slate-100">
                <td className="py-3 pr-3"><Link className="text-sky-800 hover:text-sky-900" href={`/communities/${row.community_id}`}>{row.community_name}</Link><p className="text-xs text-slate-500">{row.community_kind === "official_area" ? "Official area" : "Master project"}</p></td>
                <td className="py-3 font-mono">{formatPsm(row.median_psm)}</td>
                <td className="py-3 font-mono">{formatNumber(row.transactions)}</td>
                <td className="py-3">{formatPercent(row.yoy_growth_pct) ?? "Not reported"}</td>
                <td className="py-3">{formatRatioPercent(row.cross_sectional_dispersion) ?? "—"}</td>
                <td className="py-3">{formatDate(row.last_transaction)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  function header(label: string, key: SortKey) {
    return <th className="pb-2"><button className="text-left hover:text-slate-900" onClick={() => toggle(key)}>{label}</button></th>;
  }
}
