"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ValuationForm } from "@/components/valuation/valuation-form";
import { ValuationResult } from "@/components/valuation/valuation-panel";
import { ErrorState, GlassCard, LoadingSkeleton, PageHeader, Reveal } from "@/components/shared/surface";
import { api, isApiError } from "@/lib/api/client";
import type { FeatureImportance, Methodology, RegistryCommunity, ValuationRequest, ValuationResponse } from "@/lib/api/types";
import { DistributionChart } from "@/components/charts/market-charts";

export default function ValuationPage() {
  return <Suspense fallback={<LoadingSkeleton className="h-80" />}><ValuationScreen /></Suspense>;
}

function ValuationScreen() {
  const params = useSearchParams();
  const registry = useQuery({ queryKey: ["registry"], queryFn: () => api<{ communities: RegistryCommunity[] }>("/api/communities/registry") });
  const methodology = useQuery({ queryKey: ["methodology"], queryFn: () => api<Methodology>("/api/model/methodology") });
  const features = useQuery({ queryKey: ["features"], queryFn: () => api<FeatureImportance>("/api/model/features") });
  const mutation = useMutation({ mutationFn: (body: ValuationRequest) => api<ValuationResponse>("/api/valuation/predict", { method: "POST", body: JSON.stringify(body) }) });
  const defaultDate = methodology.data?.dataset.coverage.date_max ?? "2025-11-07";
  return (
    <div>
      <PageHeader eyebrow="Valuation terminal" title="Property valuation" subtitle="Estimate a residential transaction value from characteristics known at the valuation date. The asking price is compared afterwards." />
      <div className="grid items-start gap-4 xl:grid-cols-[380px_1fr]">
        <GlassCard className="p-5">
          {registry.isLoading ? <LoadingSkeleton className="h-80" /> : <ValuationForm communities={registry.data?.communities ?? []} defaultDate={defaultDate} initialCommunity={params.get("community") ?? ""} pending={mutation.isPending} onSubmit={(value) => mutation.mutate(value)} />}
        </GlassCard>
        <div>
          {mutation.isPending ? <LoadingSkeleton className="h-96" /> : null}
          {mutation.isError ? <ErrorState title={isApiError(mutation.error) && mutation.error.status === 422 ? "Insufficient qualifying sales data" : "Valuation request failed"} body={isApiError(mutation.error) ? mutation.error.message : "The service did not return an estimate. No fallback value was created."} /> : null}
          {mutation.data ? <Reveal><ValuationResult result={mutation.data} coverage={methodology.data} /></Reveal> : !mutation.isPending && !mutation.isError ? <GlassCard className="p-8 text-sm leading-6 text-slate-500">Submit a property to calculate an estimate, an individual-transaction interval, and earlier comparable sales.</GlassCard> : null}
        </div>
      </div>
      <GlassCard className="mt-4 p-5">
        <h2 className="text-lg font-medium">Model associations</h2>
        <p className="mt-1 mb-3 text-sm text-slate-500">{features.data?.note ?? "Associations describe the fitted model. They are not causes of price."}</p>
        {features.data?.features.length ? <DistributionChart data={features.data.features.map((row) => ({ feature: row.feature, importance: row.importance }))} nameKey="feature" valueKey="importance" caption="Mean absolute SHAP on the log-price scale" /> : <p className="text-sm text-slate-500">Feature associations are not loaded.</p>}
      </GlassCard>
    </div>
  );
}
