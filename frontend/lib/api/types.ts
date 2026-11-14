export type ApiErrorBody = {
  error: { code: string; message: string; details?: unknown };
};

export type Health = { status: "ready" | "degraded"; model_version: string | null };

export type SeriesPoint = {
  period: string;
  transactions: number;
  total_value_aed: number;
  median_psm: number;
  median_price_aed: number;
};

export type MarketSeries = {
  grain: "month" | "quarter";
  transactions: number;
  population: string;
  series: SeriesPoint[];
  registration_mix: { reg_type_en: string; transactions: number }[];
  property_type_mix: { property_type_en: string; transactions: number; median_psm: number }[];
};

export type MarketOverview = {
  population: string;
  transactions: number;
  total_value_aed: number;
  median_price_aed: number;
  median_psm: number;
  date_min: string;
  date_max: string;
  latest_complete_quarter: string;
  registration_mix: { reg_type_en: string; transactions: number; median_psm: number }[];
  property_type_mix: { property_type_en: string; transactions: number; median_price_aed: number; median_psm: number }[];
  rental_valuation_status?: string;
};

export type CommunitySummary = {
  community_id: string;
  community_name: string;
  community_kind: "master_project" | "official_area" | string;
  transactions: number;
  median_price_aed: number | null;
  median_psm: number | null;
  total_value_aed?: number | null;
  yoy_growth_pct: number | null;
  qoq_growth_pct: number | null;
  cross_sectional_dispersion?: number | null;
  time_series_volatility?: number | null;
  share_unit?: number | null;
  share_villa?: number | null;
  share_existing?: number | null;
  share_offplan?: number | null;
  last_transaction: string | null;
  first_transaction?: string | null;
  p25_psm?: number | null;
  p75_psm?: number | null;
  data_confidence_score?: number | null;
  latest_complete_quarter?: string | null;
};

export type CommunityDetail = CommunitySummary & {
  property_types: { property_type: string; transactions: number; median_price_aed: number | null; median_psm: number | null }[];
  bedrooms: { bedrooms: string; transactions: number; median_price_aed: number | null; median_psm: number | null }[];
};

export type TrendPoint = {
  quarter?: string;
  year_month?: string;
  transactions: number;
  median_psm: number | null;
  median_price_aed?: number | null;
  yoy_median_psm_growth_pct?: number | null;
  qoq_median_psm_growth_pct?: number | null;
};

export type CommunityTrends = {
  community_id: string;
  monthly: TrendPoint[];
  quarterly: TrendPoint[];
};

export type RegistryCommunity = {
  community_id: string;
  community_kind: string;
  community_name: string;
  residential_primary_sales: number;
  rows_all_procedures: number;
  modal_area: string | null;
  modal_area_share: number | null;
};

export type MapCommunity = {
  community_id: string;
  community_name: string;
  community_kind: string;
  latitude: number | null;
  longitude: number | null;
  geometry: unknown | null;
  median_psm: number | null;
  transactions: number;
  yoy_growth_pct: number | null;
  cross_sectional_dispersion: number | null;
  time_series_volatility: number | null;
  share_unit: number | null;
  share_villa: number | null;
  last_transaction: string | null;
  location_source?: string | null;
  location_label?: string | null;
};

export type MapPayload = {
  geometry_available: boolean;
  geometry_note: string;
  communities: MapCommunity[];
};

export type ComparableSale = {
  transaction_id: string;
  community: string | null;
  building_name_en: string | null;
  project_name_en: string | null;
  transaction_date: string;
  property_type: string;
  bedrooms: number | null;
  size_sqm: number;
  transaction_price_aed: number;
  price_per_sqm: number;
  registration_type: string | null;
  similarity_score: number;
};

export type ValuationResponse = {
  estimated_market_value_aed: number;
  valuation_interval: { lower_aed: number | null; upper_aed: number | null; nominal_coverage: number };
  asking_price_aed: number;
  asking_minus_estimate_aed: number;
  price_gap_pct: number | null;
  pricing_classification: "Potentially undervalued" | "Fairly priced" | "Potentially overvalued" | "Inconclusive";
  classification_reason: string;
  classification_rule: string;
  community_prior_median_psm: number | null;
  community_prior_median_source: "official_area" | "master_project";
  resolved_location: {
    input: string;
    official_area: string | null;
    master_project: string | null;
    community_id: string;
  };
  comparables: { comparables: ComparableSale[]; n_returned: number; search_rule: string | null; message: string | null };
  market_trend: {
    available: boolean;
    reason?: string;
    latest_quarter?: string;
    median_psm?: number | null;
    transactions?: number;
    qoq_median_psm_growth_pct?: number | null;
    yoy_median_psm_growth_pct?: number | null;
    growth_note?: string;
  };
  reliability: { level: string; reasons: string[]; prior_sales?: number; prior_sales_source?: string; definition: string };
  model_version: string;
  valuation_date: string;
  data_max_date: string;
  stale_market_features: boolean;
  stale_market_features_note: string | null;
  interval_interpretation: string | null;
  asking_price_used_as_model_input: boolean;
};

export type ValuationRequest = {
  community: string;
  property_type: "Unit" | "Villa";
  bedrooms: number;
  size_sqm: number;
  asking_price: number;
  property_subtype?: string;
  building?: string;
  project?: string;
  parking?: 0 | 1;
  registration_type?: "Existing Properties" | "Off-Plan Properties";
  valuation_date?: string;
};

export type ComparisonCommunity = {
  community_id: string;
  community_name: string;
  community_kind: string;
  transactions: number;
  insufficient_sample: boolean;
  yoy_growth_pct: number | null;
  qoq_growth_pct: number | null;
  quarterly: { quarter: string; transactions: number; median_psm: number; median_price_aed: number }[];
  metrics: null | {
    total_value_aed: number;
    median_price_aed: number;
    median_psm: number;
    p25_psm: number;
    p75_psm: number;
    cross_sectional_dispersion: number | null;
    share_unit: number;
    share_villa: number;
    share_existing: number;
    share_offplan: number;
    date_min: string;
    date_max: string;
    growth_note?: string;
  };
};

export type ComparisonResponse = {
  filters: Record<string, string | number | null>;
  comparison_quarter: string | null;
  equivalent_population: string;
  communities: ComparisonCommunity[];
};

export type Methodology = {
  dataset: {
    coverage: {
      raw_rows: number | null;
      deduplicated_rows: number | null;
      primary_residential_sales: number | null;
      date_min: string | null;
      date_max: string | null;
    };
    splits: {
      validation_start: string;
      validation_selection_start: string;
      validation_conformal_start: string;
      test_start: string;
      counts: Record<string, number>;
    };
    rows: Record<string, number>;
  };
  target: string;
  asking_price_used_as_feature: boolean;
  selected_model: string;
  selection_rule: string;
  validation_selection_mae_aed: number;
  test_metrics: {
    mae_aed: number;
    rmse_aed: number;
    r2: number;
    median_absolute_error_aed: number;
    median_absolute_percentage_error: number;
    within_10pct: number;
    within_20pct: number;
    within_30pct: number;
    wape: number;
    wape_denominator: string;
  };
  prediction_interval: {
    nominal_coverage: number;
    test_overall: { empirical_coverage: number; median_width_aed: number; mean_width_aed: number; n: number };
    property_type_coverage?: Record<string, { n: number; empirical_coverage: number }>;
    interpretation: string;
  };
  model_comparison_note: string | null;
  rental: { rental_valuation_status: string; rental_yield_status: string; reason: string };
  limitations: string[];
};

export type FeatureImportance = {
  features: { feature: string; importance: number; method: string; note?: string }[];
  note: string;
};

export type ExplorerResponse = {
  comparison_quarter: string | null;
  communities: CommunitySummary[];
  dispersion_note?: string;
};
