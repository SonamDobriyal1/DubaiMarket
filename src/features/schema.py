"""Prediction-time feature contract.

Asking price, actual_worth, meter_sale_price, rent fields, party counts, and
transaction identifiers are intentionally absent.
"""

from __future__ import annotations

CATEGORICAL_FEATURES = [
    "area_name_en",
    "master_project_en",
    "property_type_en",
    "property_sub_type_en",
    "reg_type_en",
    "nearest_landmark_grouped",
    "nearest_metro_grouped",
    "nearest_mall_grouped",
    "building_name_grouped",
    "project_name_grouped",
]

NUMERIC_FEATURES = [
    "bedroom_count",
    "bedroom_missing",
    "is_penthouse",
    "is_studio",
    "procedure_area",
    "log_procedure_area",
    "has_parking",
    "parking_missing",
    "transaction_year",
    "transaction_month",
    "transaction_quarter",
    "months_since_2000",
    "month_sin",
    "month_cos",
    "area_prior_median_psm",
    "area_prior_count",
    "area_prior_dispersion",
    "area_trail12_count",
    "area_trail12_median_psm",
    "area_qoq_growth",
    "area_type_prior_median_psm",
    "area_bed_prior_median_psm",
    "master_prior_median_psm",
    "master_prior_count",
    "building_prior_shrunk_psm",
    "building_prior_count",
    "project_prior_shrunk_psm",
    "project_prior_count",
]

FORBIDDEN_FEATURES = [
    "actual_worth",
    "meter_sale_price",
    "price_per_sqm",
    "psm_recalculated",
    "rent_value",
    "meter_rent_price",
    "no_of_parties_role_1",
    "no_of_parties_role_2",
    "no_of_parties_role_3",
    "asking_price",
    "transaction_id",
    "procedure_id",
    "procedure_name_en",
    "load_timestamp",
]

TARGET = "actual_worth"
SIZE_BANDS = [0, 50, 80, 120, 200, 400, float("inf")]
SIZE_BAND_LABELS = ["<50", "50-80", "80-120", "120-200", "200-400", "400+"]
PRICE_BANDS = [0, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000, float("inf")]
PRICE_BAND_LABELS = ["<0.5m", "0.5-1m", "1-2m", "2-5m", "5-10m", "10m+"]
