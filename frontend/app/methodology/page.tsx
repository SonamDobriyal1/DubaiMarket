"use client";

import { useQuery } from "@tanstack/react-query";
import { ErrorState, GlassCard, LoadingSkeleton, PageHeader } from "@/components/shared/surface";
import { api, isApiError } from "@/lib/api/client";
import type { Methodology } from "@/lib/api/types";
import { formatAed, formatDate, formatNumber } from "@/lib/formatters";

export default function MethodologyPage() {
  const query = useQuery({ queryKey: ["methodology"], queryFn: () => api<Methodology>("/api/model/methodology") });
  if (query.isLoading) return <LoadingSkeleton className="h-96" />;
  if (query.isError || !query.data) return <ErrorState title="Methodology is unavailable" body={isApiError(query.error) ? query.error.message : "The model record could not be loaded."} />;
  const data = query.data;
  const test = data.test_metrics;
  const interval = data.prediction_interval;
  const villa = interval.property_type_coverage?.Villa;
  return (
    <article className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Transparency" title="Methodology" subtitle="How the residential valuation is built, what the untouched test measured, and where the record stops." />
      <Section title="Data">
        <p>The source is a Dubai Land Department transaction extract. It contains {formatNumber(data.dataset.coverage.raw_rows)} raw rows and {formatNumber(data.dataset.coverage.deduplicated_rows)} transactions after exact identifier deduplication. The valuation population is {formatNumber(data.dataset.coverage.primary_residential_sales)} primary residential unit and villa sales from {formatDate(data.dataset.coverage.date_min)} to {formatDate(data.dataset.coverage.date_max)}.</p>
        <p>Eligible sales are ordinary existing-property sales and off-plan pre-registrations. Mortgages, gifts, grants, and procedures that only contain the word sell are outside the model. The displayed history ends on {formatDate(data.dataset.coverage.date_max)}. A later valuation date reuses that history and is marked stale. It is not a forecast of current conditions.</p>
      </Section>
      <Section title="Processing">
        <p>Repeated transaction identifiers were exact copies and were collapsed. Missing building, project, metro, and landmark labels stay missing rather than being treated as absent amenities. Property size and sale value are not imputed. Domain screens remove non-positive sizes and prices and values outside wide physical bounds. High-priced sales inside those bounds stay in the training data.</p>
      </Section>
      <Section title="Model">
        <p>The deployed model is {data.selected_model}. It is one unified residential model with a natural-log price target. Historical community, building, and project statistics use only earlier months. The chronological split trains through {data.dataset.splits.validation_start}, selects on a later validation slice, calibrates intervals on a further slice, and scores an untouched test from {data.dataset.splits.test_start}. Asking price is not a feature.</p>
        <p>{data.selection_rule}</p>
      </Section>
      <Section title="Documented test performance">
        <p>These figures describe error on the untouched test period. They are not live market KPIs and they are not a guarantee for the next sale.</p>
        <ul className="mt-3 space-y-1 font-mono text-sm">
          <li>MAE {formatAed(test.mae_aed)}</li>
          <li>RMSE {formatAed(test.rmse_aed)}</li>
          <li>R² {test.r2.toFixed(3)}</li>
          <li>Median absolute error {formatAed(test.median_absolute_error_aed)}</li>
          <li>Median absolute percentage error {(test.median_absolute_percentage_error * 100).toFixed(1)}%</li>
          <li>Within ±10% {(test.within_10pct * 100).toFixed(1)}%</li>
          <li>Within ±20% {(test.within_20pct * 100).toFixed(1)}%</li>
          <li>Within ±30% {(test.within_30pct * 100).toFixed(1)}%</li>
        </ul>
      </Section>
      <Section title="Prediction intervals">
        <p>The nominal interval is {Math.round(interval.nominal_coverage * 100)}%. On the test period it covered {(interval.test_overall.empirical_coverage * 100).toFixed(1)}% of sales. The median width was {formatAed(interval.test_overall.median_width_aed)}. {villa ? `Villa coverage was ${(villa.empirical_coverage * 100).toFixed(1)}% on ${formatNumber(villa.n)} test villas.` : "A separate villa coverage figure was not returned."}</p>
        <p>{interval.interpretation}</p>
      </Section>
      <Section title="Model selection">
        <p>{data.model_comparison_note ?? "The comparison note is not available in the current artifacts."}</p>
        <p>Validation-selection MAE for the deployed model was {formatAed(data.validation_selection_mae_aed)}. The test result was not allowed to replace that choice.</p>
      </Section>
      <Section title="Limitations">
        <ul className="list-disc space-y-2 pl-5">{data.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
        <p className="mt-3">Rental valuation is {data.rental.rental_valuation_status}. Rental yield is {data.rental.rental_yield_status}. {data.rental.reason}</p>
        <p>No community coordinates were inferred. Map geometry stays empty until a verified GeoJSON file is supplied. Scores and pricing labels are descriptive. They are not investment recommendations.</p>
      </Section>
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <GlassCard className="mb-4 p-5"><h2 className="text-xl font-medium">{title}</h2><div className="mt-3 space-y-3 text-sm leading-7 text-slate-600">{children}</div></GlassCard>;
}
