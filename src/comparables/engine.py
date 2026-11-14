"""Transparent comparable search. Future transactions are never returned."""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


def find_comparables(
    sales: pd.DataFrame,
    *,
    valuation_date: datetime,
    community_column: str,
    community_value: str,
    property_type: str,
    bedrooms: float | None,
    size_sqm: float,
    registration: str | None = None,
    building: str | None = None,
    project: str | None = None,
    max_return: int = 10,
    min_return: int = 5,
) -> dict:
    if sales.empty or not community_value:
        return _empty("No comparable pool is loaded.")
    pool = sales.loc[sales["instance_date"] < pd.Timestamp(valuation_date)].copy()
    if pool.empty:
        return _empty("No transactions exist before the valuation date.")
    pool = pool.loc[pool[community_column].astype(str).eq(str(community_value))]
    pool = pool.loc[pool["property_type_en"].astype(str).eq(str(property_type))]
    if pool.empty:
        return _empty("No earlier sales share this community and property type.")

    ladder = [
        {"months": 24, "bed_tol": 0, "size_tol": 0.20, "match_reg": True},
        {"months": 24, "bed_tol": 0, "size_tol": 0.20, "match_reg": False},
        {"months": 24, "bed_tol": 1, "size_tol": 0.20, "match_reg": False},
        {"months": 36, "bed_tol": 1, "size_tol": 0.40, "match_reg": False},
        {"months": 60, "bed_tol": 1, "size_tol": 0.40, "match_reg": False},
        {"months": 84, "bed_tol": None, "size_tol": 0.50, "match_reg": False},
    ]
    chosen = None
    used_rule = None
    for step, rule in enumerate(ladder, start=1):
        chosen = _filter_pool(pool, valuation_date, bedrooms, size_sqm, registration, rule)
        used_rule = {"step": step, **rule}
        if len(chosen) >= min_return:
            break
    if chosen is None or chosen.empty:
        return _empty("Insufficient comparable transactions after expanding the search.")

    scored = chosen.copy()
    scored["similarity_score"] = [
        _score(row, bedrooms, size_sqm, registration, building, project, valuation_date)
        for row in scored.itertuples(index=False)
    ]
    scored = scored.sort_values(["similarity_score", "instance_date"], ascending=[False, False]).head(max_return)
    records = []
    for row in scored.itertuples(index=False):
        records.append(
            {
                "transaction_id": row.transaction_id,
                "community": getattr(row, community_column),
                "building_name_en": None if pd.isna(row.building_name_en) else row.building_name_en,
                "project_name_en": None if pd.isna(row.project_name_en) else row.project_name_en,
                "transaction_date": pd.Timestamp(row.instance_date).date().isoformat(),
                "property_type": row.property_type_en,
                "bedrooms": None if pd.isna(row.bedroom_count) else float(row.bedroom_count),
                "size_sqm": float(row.procedure_area),
                "transaction_price_aed": float(row.actual_worth),
                "price_per_sqm": float(row.price_per_sqm),
                "registration_type": row.reg_type_en,
                "similarity_score": round(float(row.similarity_score), 2),
            }
        )
    message = None
    if len(records) < min_return:
        message = (
            f"Only {len(records)} comparable transactions were found after expanding the search. "
            "That is below the preferred minimum of "
            f"{min_return}."
        )
    return {
        "comparables": records,
        "n_returned": len(records),
        "search_rule": used_rule,
        "message": message,
        "scoring": {
            "size": 0.35,
            "bedrooms": 0.25,
            "building": 0.15,
            "project": 0.10,
            "registration": 0.10,
            "recency": 0.05,
            "note": "Weights are a transparent retrieval score, not a probability.",
        },
    }


def _filter_pool(pool, valuation_date, bedrooms, size_sqm, registration, rule):
    start = pd.Timestamp(valuation_date) - pd.DateOffset(months=int(rule["months"]))
    out = pool.loc[pool["instance_date"] >= start]
    if rule["match_reg"] and registration:
        out = out.loc[out["reg_type_en"].astype(str).eq(str(registration))]
    if rule["bed_tol"] is not None and bedrooms is not None:
        beds = out["bedroom_count"]
        out = out.loc[beds.notna() & beds.sub(bedrooms).abs().le(rule["bed_tol"])]
    if rule["size_tol"] is not None and size_sqm > 0:
        low = size_sqm * (1 - rule["size_tol"])
        high = size_sqm * (1 + rule["size_tol"])
        out = out.loc[out["procedure_area"].between(low, high)]
    return out


def _score(row, bedrooms, size_sqm, registration, building, project, valuation_date) -> float:
    size_term = 0.0
    if size_sqm > 0 and row.procedure_area > 0:
        gap = abs(np.log(row.procedure_area) - np.log(size_sqm))
        size_term = float(np.clip(1.0 - gap / np.log(1.5), 0.0, 1.0))
    if bedrooms is None or pd.isna(row.bedroom_count):
        bed_term = 0.4
    else:
        diff = abs(float(row.bedroom_count) - float(bedrooms))
        bed_term = 1.0 if diff == 0 else 0.5 if diff <= 1 else 0.0
    building_term = 1.0 if building and not pd.isna(row.building_name_en) and str(row.building_name_en) == str(building) else 0.0
    project_term = 1.0 if project and not pd.isna(row.project_name_en) and str(row.project_name_en) == str(project) else 0.0
    reg_term = 1.0 if registration and str(row.reg_type_en) == str(registration) else 0.0
    days = max((pd.Timestamp(valuation_date) - pd.Timestamp(row.instance_date)).days, 0)
    recency = float(np.exp(-days / 365.0))
    raw = 0.35 * size_term + 0.25 * bed_term + 0.15 * building_term + 0.10 * project_term + 0.10 * reg_term + 0.05 * recency
    return 100.0 * raw


def _empty(message: str) -> dict:
    return {
        "comparables": [],
        "n_returned": 0,
        "search_rule": None,
        "message": message,
        "scoring": None,
    }
