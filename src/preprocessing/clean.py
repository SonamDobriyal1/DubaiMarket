"""Eligibility policy, normalization, and documented row filters."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.common import normalize_text
from src.preprocessing.schema import ARABIC_COLUMNS, ENGLISH_PARALLEL

BEDROOM_RE = re.compile(r"^(\d+)\s*b/r$")


def parse_bedrooms(value) -> tuple[float, bool, str]:
    """Return bedroom count, penthouse flag, and parse status.

    Studio is zero bedrooms. Ambiguous labels stay missing rather than being guessed.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan, False, "missing"
    try:
        if pd.isna(value):
            return np.nan, False, "missing"
    except TypeError:
        pass
    text = re.sub(r"\s+", " ", str(value).strip()).casefold()
    if text in {"", "nan", "none"}:
        return np.nan, False, "missing"
    if text == "studio":
        return 0.0, False, "studio"
    match = BEDROOM_RE.fullmatch(text)
    if match:
        return float(match.group(1)), False, "bedroom_count"
    if text == "penthouse":
        return np.nan, True, "penthouse_unspecified"
    return np.nan, False, "ambiguous"


@dataclass
class FilterLog:
    rows: list[dict] = field(default_factory=list)

    def add(self, step: str, before: int, after: int, reason: str) -> None:
        self.rows.append(
            {
                "step": step,
                "rows_before": int(before),
                "rows_removed": int(before - after),
                "rows_after": int(after),
                "reason": reason,
            }
        )

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def _record_arabic_and_drop(df: pd.DataFrame, log: FilterLog) -> tuple[pd.DataFrame, dict]:
    redundancy = {}
    drop_cols = []
    for arabic, english in ENGLISH_PARALLEL.items():
        if arabic not in df.columns or english not in df.columns:
            continue
        forward = int(df.groupby(english, dropna=False)[arabic].nunique(dropna=False).max())
        backward = int(df.groupby(arabic, dropna=False)[english].nunique(dropna=False).max())
        one_to_one = forward == 1 and backward == 1
        redundancy[arabic] = {
            "english_column": english,
            "one_to_one": one_to_one,
            "max_arabic_per_english": forward,
            "max_english_per_arabic": backward,
        }
        if one_to_one:
            drop_cols.append(arabic)
    before = df.shape[1]
    if drop_cols:
        df = df.drop(columns=drop_cols)
    log.add(
        "drop_redundant_arabic_columns",
        before,
        df.shape[1],
        "Dropped Arabic label columns that are one-to-one with the English columns. "
        f"Dropped: {', '.join(drop_cols) if drop_cols else 'none'}. "
        "This step changes column count, not row count. Raw file is unchanged.",
    )
    # The filter log is row-oriented. Store a column note without pretending rows were removed.
    log.rows[-1]["rows_before"] = int(len(df))
    log.rows[-1]["rows_after"] = int(len(df))
    log.rows[-1]["rows_removed"] = 0
    log.rows[-1]["columns_before"] = before
    log.rows[-1]["columns_after"] = int(df.shape[1])
    return df, redundancy


def deduplicate(df: pd.DataFrame, log: FilterLog) -> pd.DataFrame:
    before = len(df)
    conflict_columns = ["actual_worth", "procedure_area", "procedure_name_en", "instance_date"]
    nunq = df.groupby("transaction_id")[conflict_columns].nunique(dropna=False)
    conflicts = int((nunq > 1).any(axis=1).sum())
    if conflicts:
        raise RuntimeError(
            f"{conflicts} transaction_id values disagree on price, area, procedure, or date. "
            "Refusing to drop them automatically."
        )
    df = df.drop_duplicates(subset=["transaction_id"], keep="first").reset_index(drop=True)
    log.add(
        "deduplicate_transaction_id",
        before,
        len(df),
        "Exact duplicate copies of transaction_id were removed after confirming price, area, "
        "procedure, and date do not conflict inside an id. One copy is kept. This is a data-quality "
        "step, not a market-segment filter.",
    )
    return df


def normalize_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.copy()
    text_columns = [
        "area_name_en",
        "building_name_en",
        "project_name_en",
        "master_project_en",
        "nearest_landmark_en",
        "nearest_metro_en",
        "nearest_mall_en",
        "property_type_en",
        "property_sub_type_en",
        "property_usage_en",
        "reg_type_en",
        "procedure_name_en",
        "trans_group_en",
        "rooms_en",
    ]
    changes = {}
    for column in text_columns:
        if column not in df.columns:
            continue
        original = df[column]
        normalized = original.map(normalize_text)
        comparable_original = original.map(lambda v: None if pd.isna(v) else str(v))
        changes[column] = int((comparable_original.fillna("__NA__") != pd.Series(normalized, index=df.index).fillna("__NA__")).sum())
        df[column] = normalized

    parsed = df["rooms_en"].map(parse_bedrooms)
    df["bedroom_count"] = [item[0] for item in parsed]
    df["is_penthouse"] = [bool(item[1]) for item in parsed]
    df["bedroom_parse_status"] = [item[2] for item in parsed]
    df["bedroom_missing"] = df["bedroom_count"].isna().astype(int)

    parking = pd.to_numeric(df["has_parking"], errors="coerce")
    unexpected_parking = int((~parking.isna() & ~parking.isin([0, 1])).sum())
    df["has_parking"] = parking.where(parking.isin([0, 1]))
    df["parking_missing"] = df["has_parking"].isna().astype(int)

    df["instance_date"] = pd.to_datetime(df["instance_date"], errors="coerce")
    df["procedure_area"] = pd.to_numeric(df["procedure_area"], errors="coerce")
    df["actual_worth"] = pd.to_numeric(df["actual_worth"], errors="coerce")
    df["meter_sale_price"] = pd.to_numeric(df["meter_sale_price"], errors="coerce")
    df["rent_value"] = pd.to_numeric(df["rent_value"], errors="coerce")
    df["meter_rent_price"] = pd.to_numeric(df["meter_rent_price"], errors="coerce")

    valid_psm = df["procedure_area"].gt(0) & df["actual_worth"].notna()
    recalculated = pd.Series(np.nan, index=df.index, dtype=float)
    recalculated.loc[valid_psm] = df.loc[valid_psm, "actual_worth"] / df.loc[valid_psm, "procedure_area"]
    df["psm_recalculated"] = recalculated
    # Prefer the recalculated ratio so later screens use one definition.
    # Keep the source column unchanged.
    df["price_per_sqm"] = df["psm_recalculated"].where(df["psm_recalculated"].notna(), df["meter_sale_price"])

    df["transaction_year"] = df["instance_date"].dt.year
    df["transaction_month"] = df["instance_date"].dt.month
    df["transaction_quarter"] = df["instance_date"].dt.quarter
    df["transaction_year_month"] = df["instance_date"].dt.to_period("M").astype(str)
    df["year_month_index"] = df["transaction_year"] * 12 + df["transaction_month"]
    df["months_since_2000"] = (df["transaction_year"] - 2000) * 12 + df["transaction_month"]
    month = df["transaction_month"]
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    changes["unexpected_parking_values"] = unexpected_parking
    changes["unparsed_dates"] = int(df["instance_date"].isna().sum())
    return df, changes


def assign_eligibility(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    policy = cfg["eligibility"]
    primary = set(policy["primary_procedures"])
    extended = set(policy["extended_procedures"])
    dwelling = set(policy["dwelling_subtypes"])
    allow_missing_subtype = bool(policy["allow_missing_subtype"])

    reasons = pd.Series("eligible_primary", index=df.index, dtype="object")
    sales = df["trans_group_en"].eq(policy["trans_group"])
    reasons = reasons.where(sales, "not_sales_group")

    procedure = df["procedure_name_en"]
    primary_proc = procedure.isin(primary)
    extended_proc = procedure.isin(extended)
    procedure_ok = primary_proc | extended_proc
    reasons = reasons.where(~sales | procedure_ok, "procedure_not_arm_length_dwelling_sale")

    residential = df["property_usage_en"].isin(policy["usage"])
    reasons = reasons.where(~sales | ~procedure_ok | residential, "not_residential_usage")

    dwelling_type = df["property_type_en"].isin(policy["property_types"])
    reasons = reasons.where(
        ~sales | ~procedure_ok | ~residential | dwelling_type,
        "property_type_not_unit_or_villa",
    )

    subtype = df["property_sub_type_en"]
    subtype_ok = subtype.isin(dwelling) | (allow_missing_subtype & subtype.isna())
    reasons = reasons.where(
        ~sales | ~procedure_ok | ~residential | ~dwelling_type | subtype_ok,
        "non_dwelling_subtype",
    )

    dated = df["instance_date"].notna()
    reasons = reasons.where(reasons.ne("eligible_primary") | dated, "unparsed_transaction_date")

    positive = df["procedure_area"].gt(0) & df["actual_worth"].gt(0)
    reasons = reasons.where(reasons.ne("eligible_primary") | positive, "non_positive_size_or_worth")

    # Extended delayed sales are eligible for the analytical extended set, not the primary model.
    reasons = reasons.where(~(reasons.eq("eligible_primary") & extended_proc), "eligible_delayed_sell")

    df = df.copy()
    df["exclusion_reason"] = reasons
    df["eligibility_tier"] = np.select(
        [reasons.eq("eligible_primary"), reasons.eq("eligible_delayed_sell")],
        ["primary", "extended_delayed_sell"],
        default="excluded",
    )
    return df


def apply_domain_outlier_rules(df: pd.DataFrame, cfg: dict, log: FilterLog, step_prefix: str) -> pd.DataFrame:
    """Apply physical inconsistency rules. High but plausible luxury prices stay."""
    rules = cfg["outliers"]
    before = len(df)
    area = df["procedure_area"]
    psm = df["price_per_sqm"]
    unit = df["property_type_en"].eq("Unit")
    villa = df["property_type_en"].eq("Villa")

    too_small = (unit & area.lt(rules["unit_area_min"])) | (villa & area.lt(rules["villa_area_min"]))
    too_large = (unit & area.gt(rules["unit_area_max"])) | (villa & area.gt(rules["villa_area_max"]))
    psm_low = psm.lt(rules["min_psm"])
    psm_high = psm.gt(rules["max_psm"])
    bad_target = ~df["procedure_area"].gt(0) | ~df["actual_worth"].gt(0) | psm.isna()

    reason = pd.Series(pd.NA, index=df.index, dtype="object")
    reason = reason.mask(bad_target, "non_positive_or_missing_price_or_area")
    reason = reason.mask(reason.isna() & too_small, "area_below_dwelling_minimum")
    reason = reason.mask(reason.isna() & too_large, "area_above_dwelling_maximum")
    reason = reason.mask(reason.isna() & psm_low, "psm_below_inconsistency_floor")
    reason = reason.mask(reason.isna() & psm_high, "psm_above_inconsistency_ceiling")

    removed = reason.notna()
    kept = df.loc[~removed].copy()
    log.add(
        f"{step_prefix}_domain_outlier_rules",
        before,
        len(kept),
        "Removed non-positive prices or areas, unit sizes outside "
        f"[{rules['unit_area_min']}, {rules['unit_area_max']}] sqm, villa sizes outside "
        f"[{rules['villa_area_min']}, {rules['villa_area_max']}] sqm, and AED/sqm outside "
        f"[{rules['min_psm']}, {rules['max_psm']}]. "
        f"Breakdown: {reason.value_counts(dropna=True).to_dict()}. "
        "The AED/sqm ceiling is an inconsistency screen. Transactions below it, including high luxury prices, are retained.",
    )
    return kept


def casefold_collisions(series: pd.Series) -> list[dict]:
    text = series.dropna().astype(str)
    grouped = text.groupby(text.str.casefold()).agg(lambda s: sorted(set(s)))
    collisions = []
    for key, names in grouped.items():
        if len(names) > 1:
            collisions.append({"casefold": key, "labels": names})
    return collisions


def prepare_transactions(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, FilterLog, dict]:
    log = FilterLog()
    log.add(
        "raw_load",
        len(df),
        len(df),
        "Supplied file loaded. No rows removed. The brief's 52,216-row description does not match this file.",
    )
    df, redundancy = _record_arabic_and_drop(df, log)
    df = deduplicate(df, log)
    df, normalization = normalize_frame(df)
    log.add(
        "normalize_text_dates_bedrooms_parking",
        len(df),
        len(df),
        "Whitespace collapsed, dates parsed, bedrooms parsed, parking limited to 0/1. "
        f"Text cells changed: { {k: v for k, v in normalization.items() if k in ('area_name_en','building_name_en','project_name_en','master_project_en')} }. "
        f"Unparsed dates: {normalization['unparsed_dates']}. Unexpected parking values: {normalization['unexpected_parking_values']}. "
        "No rows removed at this step.",
    )
    before_dates = len(df)
    # Do not drop undated rows from the analytical file; eligibility marks them.
    df = assign_eligibility(df, cfg)
    log.add(
        "assign_eligibility_flags",
        before_dates,
        len(df),
        "Flags assigned and no rows dropped. Primary tier: trans_group Sales, procedure Sell or "
        "Sell - Pre registration, usage Residential, type Unit or Villa, dwelling subtype "
        "(Flat, Villa, Stacked Townhouses, Hotel Apartment, or missing), positive area and worth, parsed date. "
        "Delayed Sell meeting the same property rules is tier extended_delayed_sell. "
        "Mortgages, gifts, grants, lease-to-own, development registrations, sale on payment plan, "
        "land, buildings, and non-residential usages are excluded from the valuation population.",
    )

    primary = df.loc[df["eligibility_tier"].eq("primary")].copy()
    extended = df.loc[df["eligibility_tier"].isin(["primary", "extended_delayed_sell"])].copy()
    log.add(
        "select_primary_residential_sales",
        len(df),
        len(primary),
        "Primary valuation frame. Excluded rows remain in cleaned_transactions with exclusion_reason.",
    )
    primary = apply_domain_outlier_rules(primary, cfg, log, "primary")
    extended_clean = apply_domain_outlier_rules(
        extended, cfg, log, "extended"
    )
    meta = {
        "arabic_redundancy": redundancy,
        "normalization": normalization,
        "casefold_collisions": {
            "project_name_en": casefold_collisions(df["project_name_en"]),
            "master_project_en": casefold_collisions(df["master_project_en"]),
            "building_name_en": casefold_collisions(df["building_name_en"]),
            "area_name_en": casefold_collisions(df["area_name_en"]),
        },
        "eligibility_counts": df["eligibility_tier"].value_counts().to_dict(),
        "exclusion_counts": df["exclusion_reason"].value_counts().to_dict(),
        "bedroom_parse_counts_primary": primary["bedroom_parse_status"].value_counts().to_dict(),
    }
    return df, primary, extended_clean, log, meta
