-- PostgreSQL schema for the Dubai residential intelligence outputs.
-- Monetary amounts are AED. Areas are square meters. No geometry is stored
-- unless an external, licensed boundary file is loaded later.

CREATE TABLE IF NOT EXISTS communities (
    community_id TEXT PRIMARY KEY,
    community_kind TEXT NOT NULL CHECK (community_kind IN ('official_area', 'master_project')),
    community_name TEXT NOT NULL,
    residential_primary_sales INTEGER NOT NULL,
    modal_area TEXT,
    modal_area_share DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    instance_date DATE NOT NULL,
    trans_group_en TEXT,
    procedure_name_en TEXT,
    property_type_en TEXT,
    property_sub_type_en TEXT,
    property_usage_en TEXT,
    reg_type_en TEXT,
    area_name_en TEXT,
    master_project_en TEXT,
    building_name_en TEXT,
    project_name_en TEXT,
    bedroom_count DOUBLE PRECISION,
    bedroom_parse_status TEXT,
    has_parking INTEGER,
    procedure_area_sqm DOUBLE PRECISION,
    actual_worth_aed DOUBLE PRECISION,
    price_per_sqm DOUBLE PRECISION,
    rent_value_aed DOUBLE PRECISION,
    eligibility_tier TEXT NOT NULL,
    exclusion_reason TEXT
);

CREATE TABLE IF NOT EXISTS community_market_metrics (
    community_id TEXT NOT NULL REFERENCES communities(community_id),
    period_type TEXT NOT NULL CHECK (period_type IN ('month', 'quarter', 'all')),
    period_label TEXT NOT NULL,
    transactions INTEGER NOT NULL,
    total_value_aed DOUBLE PRECISION,
    median_price_aed DOUBLE PRECISION,
    median_psm DOUBLE PRECISION,
    yoy_median_psm_growth_pct DOUBLE PRECISION,
    qoq_median_psm_growth_pct DOUBLE PRECISION,
    PRIMARY KEY (community_id, period_type, period_label)
);

CREATE TABLE IF NOT EXISTS model_versions (
    model_version TEXT PRIMARY KEY,
    algorithm TEXT NOT NULL,
    target_mode TEXT NOT NULL,
    strategy TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    selection_metric TEXT NOT NULL,
    selection_value DOUBLE PRECISION,
    test_mae_aed DOUBLE PRECISION,
    nominal_interval_coverage DOUBLE PRECISION,
    asking_price_used_as_feature BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS valuation_requests (
    request_id BIGSERIAL PRIMARY KEY,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    community_id TEXT,
    property_type TEXT NOT NULL,
    bedrooms DOUBLE PRECISION,
    size_sqm DOUBLE PRECISION NOT NULL,
    asking_price_aed DOUBLE PRECISION NOT NULL,
    valuation_date DATE NOT NULL,
    model_version TEXT REFERENCES model_versions(model_version)
);

CREATE TABLE IF NOT EXISTS valuation_results (
    request_id BIGINT PRIMARY KEY REFERENCES valuation_requests(request_id),
    estimated_value_aed DOUBLE PRECISION NOT NULL,
    lower_aed DOUBLE PRECISION,
    upper_aed DOUBLE PRECISION,
    nominal_coverage DOUBLE PRECISION,
    price_gap_pct DOUBLE PRECISION,
    classification TEXT NOT NULL,
    reliability_level TEXT NOT NULL
);

COMMENT ON TABLE valuation_results IS
    'Prediction interval for one potential transaction price. Not a confidence interval for a mean and not an investment recommendation.';
