"use client";

import { useQuery } from "@tanstack/react-query";
import { MarketDataTable } from "@/components/communities/community-table";
import { ErrorState, GlassCard, LoadingSkeleton, PageHeader } from "@/components/shared/surface";
import { api, isApiError } from "@/lib/api/client";
import type { CommunitySummary } from "@/lib/api/types";
import { useState } from "react";

export default function CommunitiesPage() {
  const [kind, setKind] = useState("master_project");
  const query = useQuery({ queryKey: ["communities", kind], queryFn: () => api<{ communities: CommunitySummary[] }>(`/api/communities?kind=${kind}`) });
  return (
    <div>
      <PageHeader title="Communities" subtitle="Every community with at least one qualifying residential sale. Names with no qualifying sales, including The Gardens, are not given a price." />
      <div className="mb-4">
        <select aria-label="Community kind" value={kind} onChange={(event) => setKind(event.target.value)} className="rounded-xl border border-slate-200 bg-white text-slate-800 px-3 py-2 text-sm"><option value="master_project">Master projects</option><option value="official_area">Official areas</option></select>
      </div>
      <GlassCard className="p-5">
        {query.isLoading ? <LoadingSkeleton className="h-64" /> : query.isError ? <ErrorState title="Community list failed" body={isApiError(query.error) ? query.error.message : "Request failed."} /> : <MarketDataTable rows={query.data?.communities ?? []} />}
      </GlassCard>
    </div>
  );
}
