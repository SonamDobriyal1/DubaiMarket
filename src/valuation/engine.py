"""Build a one-row feature vector and return a valuation response."""

from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pandas as pd

from src.common import MISSING, OTHER, community_key, normalize_text
from src.features.historical import METRIC_SUFFIXES
from src.features.schema import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from src.models.predict import predict_interval
from src.preprocessing.clean import parse_bedrooms
from src.valuation.policy import classify_asking_price, reliability_indicator

ALIASES = {
    "downtown dubai": "DownTown Dubai",
    "dubai downtown": "DownTown Dubai",
}


def load_registry(path) -> list[dict]:
    return json.loads(path.read_text())


def resolve_location(requested: str, registry: list[dict], official_area: str | None, modal_share_min: float) -> dict:
    text = normalize_text(requested) or ""
    canonical = ALIASES.get(text.casefold(), text)
    folded = canonical.casefold()
    matches = [row for row in registry if str(row["community_name"]).casefold() == folded]
    if not matches:
        raise LookupError(f"Community '{requested}' is not in the transaction registry.")
    if len(matches) > 1:
        kinds = sorted({row["community_kind"] for row in matches})
        master = [row for row in matches if row["community_kind"] == "master_project"]
        chosen = master[0] if len(master) == 1 else None
        if chosen is None:
            raise LookupError(
                f"Community '{requested}' matches more than one record ({', '.join(kinds)}). "
                "Pass an official area or the exact master-project name."
            )
    else:
        chosen = matches[0]
    if int(chosen.get("residential_primary_sales", 0)) < 30:
        raise LookupError(
            f"{chosen['community_name']} has {chosen.get('residential_primary_sales', 0)} "
            "primary residential dwelling sales. That is below the minimum of 30, so no valuation is returned."
        )
    area = normalize_text(official_area) if official_area else None
    master = chosen["community_name"] if chosen["community_kind"] == "master_project" else None
    if chosen["community_kind"] == "official_area":
        area = chosen["community_name"]
    elif area is None and chosen.get("modal_area_share") is not None and chosen["modal_area_share"] >= modal_share_min:
        area = chosen.get("modal_area")
    return {"registry": chosen, "area_name_en": area, "master_project_en": master}


def _lookup(table: pd.DataFrame, key_col: str, key, month_index: int) -> pd.Series | None:
    if table is None or key is None or (isinstance(key, float) and np.isnan(key)):
        return None
    part = table.loc[table[key_col].astype(str).eq(str(key)) & table["year_month_index"].le(int(month_index))]
    if part.empty:
        return None
    return part.loc[part["year_month_index"].idxmax()]


def build_feature_row(subject: dict, history: dict, rare_maps: dict, shrinkage_k: float) -> pd.DataFrame:
    valuation_date = pd.Timestamp(subject["valuation_date"])
    month_index = int(valuation_date.year * 12 + valuation_date.month)
    raw_bedrooms = subject.get("bedrooms_raw")
    if isinstance(raw_bedrooms, (int, float)) and not isinstance(raw_bedrooms, bool) and pd.notna(raw_bedrooms):
        bedrooms = float(raw_bedrooms)
        penthouse = False
    else:
        bedrooms, penthouse, _status = parse_bedrooms(raw_bedrooms)
    area = subject.get("area_name_en")
    master = subject.get("master_project_en")
    property_type = subject["property_type"]
    subtype = subject.get("property_subtype")
    registration = subject.get("registration_type")
    building = subject.get("building")
    project = subject.get("project")
    row = {
        "transaction_id": "subject",
        "instance_date": valuation_date,
        "area_name_en": area,
        "master_project_en": master,
        "property_type_en": property_type,
        "property_sub_type_en": subtype,
        "reg_type_en": registration,
        "building_name_en": building,
        "project_name_en": project,
        "nearest_landmark_en": subject.get("nearest_landmark"),
        "nearest_metro_en": subject.get("nearest_metro"),
        "nearest_mall_en": subject.get("nearest_mall"),
        "bedroom_count": bedrooms,
        "bedroom_missing": int(pd.isna(bedrooms)),
        "is_penthouse": float(penthouse),
        "is_studio": np.nan if pd.isna(bedrooms) else float(bedrooms == 0),
        "procedure_area": float(subject["size_sqm"]),
        "log_procedure_area": float(np.log(subject["size_sqm"])) if subject["size_sqm"] and subject["size_sqm"] > 0 else np.nan,
        "has_parking": subject.get("parking"),
        "parking_missing": int(subject.get("parking") is None),
        "transaction_year": int(valuation_date.year),
        "transaction_month": int(valuation_date.month),
        "transaction_quarter": int(valuation_date.quarter),
        "months_since_2000": int((valuation_date.year - 2000) * 12 + valuation_date.month),
        "month_sin": float(np.sin(2 * np.pi * valuation_date.month / 12)),
        "month_cos": float(np.cos(2 * np.pi * valuation_date.month / 12)),
        "year_month_index": month_index,
    }
    join_month = month_index - 1
    area_hist = _lookup(history.get("area"), "area_name_en", area, join_month)
    for suffix in METRIC_SUFFIXES:
        column = f"area_{suffix}"
        row[column] = np.nan if area_hist is None or column not in area_hist else area_hist[column]
    master_hist = _lookup(history.get("master"), "master_project_en", master, join_month)
    for suffix in ("prior_median_psm", "prior_count", "qoq_growth", "trail12_count"):
        column = f"master_{suffix}"
        row[column] = np.nan if master_hist is None or column not in master_hist else master_hist[column]
    type_key = None if area is None or property_type is None else f"{area}||{property_type}"
    type_hist = _lookup(history.get("area_type"), "area_type_key", type_key, join_month)
    for suffix in ("prior_median_psm", "prior_count"):
        column = f"area_type_{suffix}"
        row[column] = np.nan if type_hist is None or column not in type_hist else type_hist[column]
    bed_label = "missing" if pd.isna(bedrooms) else str(int(bedrooms))
    bed_key = None if area is None else f"{area}||{bed_label}"
    bed_hist = _lookup(history.get("area_bed"), "area_bed_key", bed_key, join_month)
    for suffix in ("prior_median_psm", "prior_count"):
        column = f"area_bed_{suffix}"
        row[column] = np.nan if bed_hist is None or column not in bed_hist else bed_hist[column]
    building_key = None if area is None or building is None else f"{area}||{building}"
    building_hist = _lookup(history.get("building"), "building_key", building_key, join_month)
    project_key = None if area is None or project is None else f"{area}||{project}"
    project_hist = _lookup(history.get("project"), "project_key", project_key, join_month)
    row.update(_shrunk("building", building_hist, row.get("area_prior_median_psm"), shrinkage_k))
    row.update(_shrunk("project", project_hist, row.get("area_prior_median_psm"), shrinkage_k))
    frame = pd.DataFrame([row])
    frame = _apply_groups(frame, rare_maps)
    for column in NUMERIC_FEATURES:
        if column not in frame:
            frame[column] = np.nan
    return frame


def _shrunk(prefix: str, hist: pd.Series | None, area_level, k: float) -> dict:
    if hist is None:
        return {f"{prefix}_prior_count": np.nan, f"{prefix}_prior_shrunk_psm": np.nan}
    count = hist.get(f"{prefix}_prior_count", np.nan)
    level = hist.get(f"{prefix}_prior_median_psm", np.nan)
    if pd.isna(count) or pd.isna(level) or count <= 0:
        return {f"{prefix}_prior_count": count, f"{prefix}_prior_shrunk_psm": np.nan}
    if pd.notna(area_level):
        weight = count / (count + k)
        shrunk = weight * level + (1 - weight) * area_level
    elif count >= 5:
        shrunk = level
    else:
        shrunk = np.nan
    return {f"{prefix}_prior_count": count, f"{prefix}_prior_shrunk_psm": shrunk}


def _apply_groups(frame: pd.DataFrame, rare_maps: dict) -> pd.DataFrame:
    from src.features.build import RARE_SOURCE

    out = frame.copy()
    for column in ("area_name_en", "master_project_en", "property_type_en", "property_sub_type_en", "reg_type_en"):
        out[column] = out[column].map(lambda v: MISSING if pd.isna(v) or str(v).strip() == "" else str(v))
    for grouped, source in RARE_SOURCE.items():
        allowed = set(rare_maps.get(grouped, []))
        value = out.at[0, source] if source in out else None

        def _map(item, allowed=allowed):
            if item is None or (isinstance(item, float) and np.isnan(item)) or str(item).strip() == "":
                return MISSING
            text = str(item)
            return text if text in allowed else OTHER

        out[grouped] = [_map(value)]
    return out


def stale_history(valuation_date, data_max_date) -> bool:
    valuation = pd.Timestamp(valuation_date)
    latest = pd.Timestamp(data_max_date)
    return (valuation.year * 12 + valuation.month) > (latest.year * 12 + latest.month + 1)


def valuate(subject: dict, bundle: dict, history: dict, registry: list[dict], sales: pd.DataFrame, quarterly: pd.DataFrame, cfg: dict) -> dict:
    from src.comparables.engine import find_comparables

    location = resolve_location(
        subject["community"],
        registry,
        subject.get("official_area"),
        float(cfg["valuation"]["modal_area_share_min"]),
    )
    valuation_date = pd.Timestamp(subject.get("valuation_date") or bundle["data_max_date"])
    if valuation_date < pd.Timestamp("1990-01-01"):
        raise ValueError("Valuation date is outside the supported range.")
    enriched = {
        **subject,
        "valuation_date": valuation_date,
        "area_name_en": location["area_name_en"],
        "master_project_en": location["master_project_en"],
        "property_type": _canonical_type(subject["property_type"]),
        "property_subtype": subject.get("property_subtype"),
        "registration_type": subject.get("registration_type"),
        "bedrooms_raw": subject.get("bedrooms"),
    }
    features = build_feature_row(enriched, history, bundle["rare_maps"], float(cfg["history"]["shrinkage_k"]))
    point, lower, upper = predict_interval(bundle, features)
    predicted = float(point[0])
    lo = float(lower[0]) if np.isfinite(lower[0]) else None
    hi = float(upper[0]) if np.isfinite(upper[0]) else None
    decision = classify_asking_price(
        float(subject["asking_price"]),
        predicted,
        lo if lo is not None else np.nan,
        hi if hi is not None else np.nan,
        float(cfg["intervals"]["max_informative_relative_width"]),
    )
    area_count = features.at[0, "area_prior_count"]
    master_count = features.at[0, "master_prior_count"]
    if pd.notna(area_count):
        support_count, support_source = float(area_count), "official_area"
    else:
        support_count = None if pd.isna(master_count) else float(master_count)
        support_source = "master_project"
    reliability = reliability_indicator(
        support_count,
        decision.get("relative_interval_width"),
        support_source,
    )
    community_column = "master_project_en" if location["master_project_en"] else "area_name_en"
    community_value = location["master_project_en"] or location["area_name_en"]
    comps = find_comparables(
        sales,
        valuation_date=valuation_date.to_pydatetime(),
        community_column=community_column,
        community_value=community_value,
        property_type=enriched["property_type"],
        bedrooms=None if pd.isna(features.at[0, "bedroom_count"]) else float(features.at[0, "bedroom_count"]),
        size_sqm=float(subject["size_sqm"]),
        registration=subject.get("registration_type"),
        building=subject.get("building"),
        project=subject.get("project"),
    )
    trend = _trend(quarterly, location)
    area_median = features.at[0, "area_prior_median_psm"]
    master_median = features.at[0, "master_prior_median_psm"]
    if pd.notna(area_median):
        community_median, median_source = float(area_median), "official_area"
    else:
        community_median = None if pd.isna(master_median) else float(master_median)
        median_source = "master_project"
    return {
        "estimated_market_value_aed": predicted,
        "valuation_interval": {"lower_aed": lo, "upper_aed": hi, "nominal_coverage": bundle["conformal"]["nominal_coverage"]},
        "asking_price_aed": float(subject["asking_price"]),
        "asking_minus_estimate_aed": float(subject["asking_price"]) - predicted,
        "price_gap_pct": decision["price_gap_pct"],
        "pricing_classification": decision["classification"],
        "classification_reason": decision["reason"],
        "classification_rule": decision["rule"],
        "community_prior_median_psm": community_median,
        "community_prior_median_source": median_source,
        "resolved_location": {
            "input": subject["community"],
            "official_area": location["area_name_en"],
            "master_project": location["master_project_en"],
            "community_id": location["registry"]["community_id"],
        },
        "comparables": comps,
        "market_trend": trend,
        "reliability": reliability,
        "model_version": bundle["model_version"],
        "valuation_date": valuation_date.date().isoformat(),
        "data_max_date": bundle["data_max_date"],
        "stale_market_features": stale_history(valuation_date, bundle["data_max_date"]),
        "stale_market_features_note": (
            "Historical price features stop at the last observed transaction month. "
            "A valuation date after that month reuses those features and does not invent later price movement."
            if stale_history(valuation_date, bundle["data_max_date"])
            else None
        ),
        "interval_interpretation": bundle["conformal"].get("segment_rule"),
        "asking_price_used_as_model_input": False,
    }


def _canonical_type(value: str) -> str:
    text = (normalize_text(value) or "").casefold()
    if text in {"apartment", "flat", "unit"}:
        return "Unit"
    if text == "villa":
        return "Villa"
    if text in {"unit", "villa"}:
        return value
    raise ValueError("property_type must be Unit or Villa (apartment and flat are accepted as Unit).")


def _trend(quarterly: pd.DataFrame, location: dict) -> dict:
    if quarterly is None or quarterly.empty:
        return {"available": False, "reason": "Quarterly community metrics are not loaded."}
    community_id = location["registry"]["community_id"]
    part = quarterly.loc[quarterly["community_id"].eq(community_id)].sort_values("quarter")
    if part.empty:
        return {"available": False, "reason": "No quarterly history for the resolved community."}
    latest = part.iloc[-1]
    return {
        "available": True,
        "latest_quarter": str(latest["quarter"]),
        "median_psm": None if pd.isna(latest["median_psm"]) else float(latest["median_psm"]),
        "transactions": int(latest["transactions"]),
        "qoq_median_psm_growth_pct": None if pd.isna(latest["qoq_median_psm_growth_pct"]) else float(latest["qoq_median_psm_growth_pct"]),
        "yoy_median_psm_growth_pct": None if pd.isna(latest["yoy_median_psm_growth_pct"]) else float(latest["yoy_median_psm_growth_pct"]),
        "growth_note": "Growth is null when either quarter has fewer than the configured minimum sales.",
    }
