"""Community and market metrics computed only from observed transactions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import community_key, write_json


def last_complete_quarter(max_date: pd.Timestamp) -> pd.Period:
    period = pd.Timestamp(max_date).to_period("Q")
    if pd.Timestamp(max_date).normalize() < period.end_time.normalize():
        period -= 1
    return period


def _growth(current, previous, current_n, previous_n, minimum: int):
    if pd.isna(current) or pd.isna(previous) or previous <= 0:
        return np.nan
    if current_n < minimum or previous_n < minimum:
        return np.nan
    return (current / previous - 1.0) * 100.0


def build_group_metrics(sales: pd.DataFrame, group_col: str, kind: str, min_n: int) -> dict[str, pd.DataFrame]:
    frame = sales.loc[sales[group_col].notna()].copy()
    frame["quarter"] = frame["instance_date"].dt.to_period("Q").astype(str)
    frame["year_month"] = frame["instance_date"].dt.to_period("M").astype(str)
    frame["year"] = frame["instance_date"].dt.year
    frame["bedroom_band"] = frame["bedroom_count"].map(lambda v: "missing" if pd.isna(v) else str(int(v)))

    quarterly = (
        frame.groupby([group_col, "quarter"], dropna=False)
        .agg(
            transactions=("transaction_id", "size"),
            total_value_aed=("actual_worth", "sum"),
            median_price_aed=("actual_worth", "median"),
            median_psm=("price_per_sqm", "median"),
            mean_psm=("price_per_sqm", "mean"),
            std_psm=("price_per_sqm", "std"),
        )
        .reset_index()
    )
    quantiles = (
        frame.groupby([group_col, "quarter"])["price_per_sqm"].quantile([0.25, 0.75]).unstack().reset_index()
    )
    quantiles = quantiles.rename(columns={0.25: "p25_psm", 0.75: "p75_psm"})
    quarterly = quarterly.merge(quantiles, on=[group_col, "quarter"], how="left")
    quarterly["quarter_start"] = pd.PeriodIndex(quarterly["quarter"], freq="Q").to_timestamp()
    quarterly = quarterly.sort_values([group_col, "quarter_start"])
    quarterly["qoq_median_psm_growth_pct"] = _calendar_growth(quarterly, group_col, 1, min_n)
    quarterly["yoy_median_psm_growth_pct"] = _calendar_growth(quarterly, group_col, 4, min_n)
    quarterly["community_kind"] = kind
    quarterly = quarterly.rename(columns={group_col: "community_name"})
    quarterly["community_id"] = quarterly["community_name"].map(lambda name: community_key(kind, name))

    monthly = (
        frame.groupby([group_col, "year_month"], dropna=False)
        .agg(
            transactions=("transaction_id", "size"),
            total_value_aed=("actual_worth", "sum"),
            median_price_aed=("actual_worth", "median"),
            median_psm=("price_per_sqm", "median"),
        )
        .reset_index()
        .rename(columns={group_col: "community_name"})
    )
    monthly["community_kind"] = kind
    monthly["community_id"] = monthly["community_name"].map(lambda name: community_key(kind, name))

    by_type = (
        frame.groupby([group_col, "property_type_en"], dropna=False)
        .agg(
            transactions=("transaction_id", "size"),
            total_value_aed=("actual_worth", "sum"),
            median_price_aed=("actual_worth", "median"),
            median_psm=("price_per_sqm", "median"),
            mean_psm=("price_per_sqm", "mean"),
        )
        .reset_index()
        .rename(columns={group_col: "community_name", "property_type_en": "property_type"})
    )
    by_type["community_kind"] = kind
    by_type["community_id"] = by_type["community_name"].map(lambda name: community_key(kind, name))

    by_bed = (
        frame.groupby([group_col, "bedroom_band"], dropna=False)
        .agg(
            transactions=("transaction_id", "size"),
            median_price_aed=("actual_worth", "median"),
            median_psm=("price_per_sqm", "median"),
        )
        .reset_index()
        .rename(columns={group_col: "community_name", "bedroom_band": "bedrooms"})
    )
    by_bed["community_kind"] = kind
    by_bed["community_id"] = by_bed["community_name"].map(lambda name: community_key(kind, name))
    return {"quarterly": quarterly, "monthly": monthly, "property_type": by_type, "bedroom": by_bed, "frame": frame}


def _calendar_growth(frame: pd.DataFrame, group_col: str, lag_quarters: int, minimum: int) -> pd.Series:
    work = frame.copy()
    work["_period"] = pd.PeriodIndex(work["quarter"], freq="Q")
    work["_previous_period"] = work["_period"] - lag_quarters
    lookup = work[[group_col, "_period", "median_psm", "transactions"]].rename(
        columns={"_period": "_previous_period", "median_psm": "_prev_psm", "transactions": "_prev_n"}
    )
    merged = work.merge(lookup, on=[group_col, "_previous_period"], how="left")
    values = [
        _growth(current, prior, current_n, prior_n, minimum)
        for current, prior, current_n, prior_n in zip(
            merged["median_psm"], merged["_prev_psm"], merged["transactions"], merged["_prev_n"]
        )
    ]
    return pd.Series(values, index=frame.index)


def summarize_communities(frame: pd.DataFrame, quarterly: pd.DataFrame, group_col: str, kind: str, min_n: int, asof: pd.Period) -> pd.DataFrame:
    summary = (
        frame.groupby(group_col)
        .agg(
            transactions=("transaction_id", "size"),
            total_value_aed=("actual_worth", "sum"),
            median_price_aed=("actual_worth", "median"),
            mean_price_aed=("actual_worth", "mean"),
            median_psm=("price_per_sqm", "median"),
            mean_psm=("price_per_sqm", "mean"),
            std_psm=("price_per_sqm", "std"),
            first_transaction=("instance_date", "min"),
            last_transaction=("instance_date", "max"),
        )
        .reset_index()
        .rename(columns={group_col: "community_name"})
    )
    psm_q = frame.groupby(group_col)["price_per_sqm"].quantile([0.25, 0.75]).unstack().reset_index()
    psm_q = psm_q.rename(columns={group_col: "community_name", 0.25: "p25_psm", 0.75: "p75_psm"})
    summary = summary.merge(psm_q, on="community_name", how="left")
    mad = (
        frame.groupby(group_col)["price_per_sqm"]
        .apply(lambda s: float((s - s.median()).abs().median()))
        .rename("mad_psm")
        .reset_index()
        .rename(columns={group_col: "community_name"})
    )
    summary = summary.merge(mad, on="community_name", how="left")
    summary["cross_sectional_dispersion"] = summary["mad_psm"] / summary["median_psm"]
    mix = _mix(frame, group_col).rename(columns={group_col: "community_name"})
    summary = summary.merge(mix, on="community_name", how="left")

    q = quarterly.copy()
    q["period"] = pd.PeriodIndex(q["quarter"], freq="Q")
    window_start = asof - 3
    recent = q.loc[(q["community_name"].notna()) & (q["period"] <= asof) & (q["period"] >= window_start)]
    recent_totals = recent.groupby("community_name").agg(
        trailing_4q_transactions=("transactions", "sum"),
        trailing_4q_value_aed=("total_value_aed", "sum"),
        trailing_4q_median_psm=("median_psm", "median"),
    )
    summary = summary.merge(recent_totals, left_on="community_name", right_index=True, how="left")
    current = q.loc[q["period"].eq(asof), ["community_name", "median_psm", "transactions", "yoy_median_psm_growth_pct", "qoq_median_psm_growth_pct"]]
    current = current.rename(columns={
        "median_psm": "latest_complete_quarter_median_psm",
        "transactions": "latest_complete_quarter_transactions",
        "yoy_median_psm_growth_pct": "yoy_growth_pct",
        "qoq_median_psm_growth_pct": "qoq_growth_pct",
    })
    summary = summary.merge(current, on="community_name", how="left")
    summary["time_series_volatility"] = [
        _time_volatility(q.loc[q["community_name"].eq(name)], min_n) for name in summary["community_name"]
    ]
    summary["community_kind"] = kind
    summary["community_id"] = summary["community_name"].map(lambda name: community_key(kind, name))
    summary["latest_complete_quarter"] = str(asof)
    summary["yoy_suppressed_below_n"] = min_n
    return summary


def _mix(frame: pd.DataFrame, group_col: str) -> pd.DataFrame:
    counts = frame.groupby([group_col, "property_type_en"]).size().unstack(fill_value=0)
    reg = frame.groupby([group_col, "reg_type_en"]).size().unstack(fill_value=0)
    total = frame.groupby(group_col).size()
    out = pd.DataFrame(index=total.index)
    out["share_unit"] = counts.get("Unit", 0) / total
    out["share_villa"] = counts.get("Villa", 0) / total
    out["share_existing"] = reg.get("Existing Properties", 0) / total
    out["share_offplan"] = reg.get("Off-Plan Properties", 0) / total
    return out.reset_index()


def _time_volatility(quarters: pd.DataFrame, minimum: int) -> float:
    usable = quarters.loc[quarters["transactions"].ge(minimum)].sort_values("quarter_start")
    if len(usable) < 7:
        return np.nan
    changes = usable["median_psm"].pct_change()
    changes = changes.dropna()
    if len(changes) < 6:
        return np.nan
    return float(changes.std())


def add_scores(summary: pd.DataFrame) -> pd.DataFrame:
    out = summary.copy()
    activity_base = np.log1p(out["trailing_4q_transactions"].fillna(0))
    out["market_activity_score"] = activity_base.rank(pct=True) * 100.0
    liquid = out["trailing_4q_transactions"].fillna(0)
    out["liquidity_proxy_sales_per_year"] = liquid
    stability_source = out["time_series_volatility"]
    out["pricing_stability_score"] = (1.0 - stability_source.rank(pct=True)) * 100.0
    out.loc[stability_source.isna(), "pricing_stability_score"] = np.nan
    growth = out["yoy_growth_pct"]
    out["growth_score"] = growth.rank(pct=True) * 100.0
    out.loc[growth.isna(), "growth_score"] = np.nan
    n = out["transactions"].fillna(0)
    out["data_confidence_score"] = np.clip(100.0 * np.log1p(n) / np.log1p(500), 0, 100)
    out["score_disclaimer"] = (
        "Scores are percentile descriptions of observed transaction activity, growth, "
        "and quarterly-median variability. They are not investment recommendations or forecasts."
    )
    return out


def market_overview(sales: pd.DataFrame, asof: pd.Period) -> dict:
    frame = sales.copy()
    frame["year_month"] = frame["instance_date"].dt.to_period("M").astype(str)
    frame["quarter"] = frame["instance_date"].dt.to_period("Q").astype(str)
    monthly = (
        frame.groupby("year_month")
        .agg(transactions=("transaction_id", "size"), total_value_aed=("actual_worth", "sum"), median_psm=("price_per_sqm", "median"), median_price_aed=("actual_worth", "median"))
        .reset_index()
    )
    quarterly = (
        frame.groupby("quarter")
        .agg(transactions=("transaction_id", "size"), total_value_aed=("actual_worth", "sum"), median_psm=("price_per_sqm", "median"), median_price_aed=("actual_worth", "median"))
        .reset_index()
    )
    shares = frame.groupby("area_name_en").size() / len(frame)
    reg = frame.groupby("reg_type_en").agg(transactions=("transaction_id", "size"), total_value_aed=("actual_worth", "sum"), median_psm=("price_per_sqm", "median"))
    types = frame.groupby("property_type_en").agg(transactions=("transaction_id", "size"), median_price_aed=("actual_worth", "median"), median_psm=("price_per_sqm", "median"))
    return {
        "population": "Primary residential dwelling sales after the documented eligibility and domain screens.",
        "transactions": int(len(frame)),
        "total_value_aed": float(frame["actual_worth"].sum()),
        "median_price_aed": float(frame["actual_worth"].median()),
        "mean_price_aed": float(frame["actual_worth"].mean()),
        "median_psm": float(frame["price_per_sqm"].median()),
        "date_min": str(frame["instance_date"].min().date()),
        "date_max": str(frame["instance_date"].max().date()),
        "latest_complete_quarter": str(asof),
        "hhi_transaction_count_by_official_area": float((shares**2).sum()),
        "top_10_area_transaction_share": float(shares.sort_values(ascending=False).head(10).sum()),
        "registration_mix": reg.reset_index().to_dict(orient="records"),
        "property_type_mix": types.reset_index().to_dict(orient="records"),
        "monthly": monthly.to_dict(orient="records"),
        "quarterly": quarterly.to_dict(orient="records"),
    }


def rental_feasibility(cleaned: pd.DataFrame) -> dict:
    rent = cleaned.loc[cleaned["rent_value"].notna()].copy()
    groups = rent["trans_group_en"].value_counts(dropna=False).to_dict() if len(rent) else {}
    procedures = rent["procedure_name_en"].value_counts(dropna=False).to_dict() if len(rent) else {}
    sales_rent = int((rent["trans_group_en"].eq("Sales")).sum()) if len(rent) else 0
    return {
        "rent_value_non_null_after_dedup": int(len(rent)),
        "meter_rent_price_non_null_after_dedup": int(cleaned["meter_rent_price"].notna().sum()),
        "trans_group_counts": {str(k): int(v) for k, v in groups.items()},
        "procedure_counts": {str(k): int(v) for k, v in procedures.items()},
        "sales_rows_with_rent_value": sales_rent,
        "date_min": None if rent.empty else str(pd.to_datetime(rent["instance_date"]).min().date()),
        "date_max": None if rent.empty else str(pd.to_datetime(rent["instance_date"]).max().date()),
        "communities_with_a_rent_value": int(rent["area_name_en"].nunique()) if len(rent) else 0,
        "rental_valuation_status": "unavailable",
        "rental_yield_status": "unavailable",
        "reason": (
            "Non-null rent fields are attached to lease-to-own and related mortgage procedures, "
            "not to a general set of rental contracts. They are not used to estimate market rent or yield. "
            f"Sales rows carrying rent_value after deduplication: {sales_rent}."
        ),
    }


def compare_communities(sales: pd.DataFrame, community_ids: list[dict], filters: dict, min_n: int) -> dict:
    """community_ids items: {kind, name}. Filters apply equally to every community."""
    frame = _apply_filters(sales, filters)
    asof = _filter_asof(frame, filters, sales)
    results = []
    for item in community_ids:
        column = "master_project_en" if item["kind"] == "master_project" else "area_name_en"
        part = frame.loc[frame[column].astype(str).eq(str(item["name"]))]
        results.append(_comparison_block(part, item, min_n, asof))
    return {
        "filters": filters,
        "comparison_quarter": None if asof is None else str(asof),
        "equivalent_population": "The same date, type, bedroom, registration, and size filters are applied to every community.",
        "communities": results,
    }


def market_series(sales: pd.DataFrame, filters: dict, grain: str) -> dict:
    """Dubai-wide series from the in-memory primary sales table. Same filters for every point."""
    frame = _apply_filters(sales, filters)
    period = "year_month" if grain == "month" else "quarter"
    freq = "M" if grain == "month" else "Q"
    if frame.empty:
        points = []
    else:
        work = frame.copy()
        work[period] = work["instance_date"].dt.to_period(freq).astype(str)
        grouped = (
            work.groupby(period, sort=True)
            .agg(
                transactions=("transaction_id", "size"),
                total_value_aed=("actual_worth", "sum"),
                median_psm=("price_per_sqm", "median"),
                median_price_aed=("actual_worth", "median"),
            )
            .reset_index()
        )
        points = [
            {
                "period": row[period],
                "transactions": int(row["transactions"]),
                "total_value_aed": float(row["total_value_aed"]),
                "median_psm": float(row["median_psm"]),
                "median_price_aed": float(row["median_price_aed"]),
            }
            for row in grouped.to_dict(orient="records")
        ]
    registration = []
    types = []
    if not frame.empty:
        registration = [
            {"reg_type_en": str(name), "transactions": int(count)}
            for name, count in frame.groupby("reg_type_en").size().items()
        ]
        types = [
            {
                "property_type_en": str(name),
                "transactions": int(len(part)),
                "median_psm": float(part["price_per_sqm"].median()),
            }
            for name, part in frame.groupby("property_type_en")
        ]
    return {
        "grain": grain,
        "filters": filters,
        "transactions": int(len(frame)),
        "population": "Primary residential dwelling sales after the same eligibility screens as the market overview.",
        "series": points,
        "registration_mix": registration,
        "property_type_mix": types,
    }


def filtered_explorer(sales: pd.DataFrame, filters: dict, kind: str, min_n: int) -> dict:
    """Community table under one shared filter. Used when the published summary would not match the filter."""
    frame = _apply_filters(sales, filters)
    column = "master_project_en" if kind == "master_project" else "area_name_en"
    frame = frame.loc[frame[column].notna()]
    asof = _filter_asof(frame, filters, sales)
    if frame.empty:
        return {"comparison_quarter": None if asof is None else str(asof), "filters": filters, "communities": []}
    work = frame.copy()
    work["quarter"] = work["instance_date"].dt.to_period("Q").astype(str)
    rows = []
    for name, part in work.groupby(column, sort=False):
        psm = part["price_per_sqm"]
        median = float(psm.median())
        mad = float((psm - median).abs().median())
        by_quarter_n = part.groupby("quarter").size()
        by_quarter_psm = part.groupby("quarter")["price_per_sqm"].median()
        yoy = qoq = None
        if asof is not None:
            yoy = _plain(_growth(by_quarter_psm.get(str(asof)), by_quarter_psm.get(str(asof - 4)), int(by_quarter_n.get(str(asof), 0)), int(by_quarter_n.get(str(asof - 4), 0)), min_n))
            qoq = _plain(_growth(by_quarter_psm.get(str(asof)), by_quarter_psm.get(str(asof - 1)), int(by_quarter_n.get(str(asof), 0)), int(by_quarter_n.get(str(asof - 1), 0)), min_n))
        rows.append(
            {
                "community_id": community_key(kind, str(name)),
                "community_name": str(name),
                "community_kind": kind,
                "transactions": int(len(part)),
                "total_value_aed": float(part["actual_worth"].sum()),
                "median_price_aed": float(part["actual_worth"].median()),
                "median_psm": median,
                "cross_sectional_dispersion": None if median == 0 else mad / median,
                "share_unit": float(part["property_type_en"].eq("Unit").mean()),
                "share_villa": float(part["property_type_en"].eq("Villa").mean()),
                "share_existing": float(part["reg_type_en"].eq("Existing Properties").mean()),
                "share_offplan": float(part["reg_type_en"].eq("Off-Plan Properties").mean()),
                "yoy_growth_pct": yoy,
                "qoq_growth_pct": qoq,
                "last_transaction": str(part["instance_date"].max().date()),
                "time_series_volatility": None,
            }
        )
    rows.sort(key=lambda row: row["transactions"], reverse=True)
    return {
        "comparison_quarter": None if asof is None else str(asof),
        "filters": filters,
        "dispersion_note": "cross_sectional_dispersion is the median absolute deviation of price per sqm divided by the median. It is not a time-series volatility.",
        "communities": rows,
    }


def _filter_asof(frame: pd.DataFrame, filters: dict, sales: pd.DataFrame):
    del sales
    if frame.empty and not filters.get("date_to"):
        return None
    if filters.get("date_to"):
        end = pd.Timestamp(filters["date_to"])
    elif frame.empty:
        return None
    else:
        end = frame["instance_date"].max()
    if pd.isna(end):
        return None
    return last_complete_quarter(end)


def _plain(value):
    if value is None or (isinstance(value, float) and np.isnan(value)) or (isinstance(value, np.floating) and np.isnan(value)):
        return None
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return value


def _apply_filters(sales: pd.DataFrame, filters: dict) -> pd.DataFrame:
    frame = sales
    if filters.get("date_from"):
        frame = frame.loc[frame["instance_date"] >= pd.Timestamp(filters["date_from"])]
    if filters.get("date_to"):
        frame = frame.loc[frame["instance_date"] <= pd.Timestamp(filters["date_to"])]
    if filters.get("property_type"):
        frame = frame.loc[frame["property_type_en"].eq(filters["property_type"])]
    if filters.get("bedrooms") is not None:
        frame = frame.loc[frame["bedroom_count"].eq(filters["bedrooms"])]
    if filters.get("registration_type"):
        frame = frame.loc[frame["reg_type_en"].eq(filters["registration_type"])]
    if filters.get("size_min") is not None:
        frame = frame.loc[frame["procedure_area"].ge(filters["size_min"])]
    if filters.get("size_max") is not None:
        frame = frame.loc[frame["procedure_area"].le(filters["size_max"])]
    return frame


def _comparison_block(part: pd.DataFrame, item: dict, min_n: int, asof=None) -> dict:
    block = {
        "community_id": community_key(item["kind"], item["name"]),
        "community_name": item["name"],
        "community_kind": item["kind"],
        "transactions": int(len(part)),
        "insufficient_sample": bool(len(part) < min_n),
        "quarterly": [],
        "yoy_growth_pct": None,
        "qoq_growth_pct": None,
    }
    if part.empty:
        block["metrics"] = None
        return block
    psm = part["price_per_sqm"]
    median = float(psm.median())
    mad = float((psm - median).abs().median())
    block["metrics"] = {
        "total_value_aed": float(part["actual_worth"].sum()),
        "median_price_aed": float(part["actual_worth"].median()),
        "median_psm": median,
        "p25_psm": float(psm.quantile(0.25)),
        "p75_psm": float(psm.quantile(0.75)),
        "cross_sectional_dispersion": None if median == 0 else mad / median,
        "share_unit": float(part["property_type_en"].eq("Unit").mean()),
        "share_villa": float(part["property_type_en"].eq("Villa").mean()),
        "share_existing": float(part["reg_type_en"].eq("Existing Properties").mean()),
        "share_offplan": float(part["reg_type_en"].eq("Off-Plan Properties").mean()),
        "date_min": str(part["instance_date"].min().date()),
        "date_max": str(part["instance_date"].max().date()),
    }
    if len(part) < min_n:
        block["metrics"]["growth_note"] = f"Growth is not reported because the filtered sample has fewer than {min_n} sales."
    work = part.copy()
    work["quarter"] = work["instance_date"].dt.to_period("Q").astype(str)
    quarterly = (
        work.groupby("quarter", sort=True)
        .agg(transactions=("transaction_id", "size"), median_psm=("price_per_sqm", "median"), median_price_aed=("actual_worth", "median"))
        .reset_index()
    )
    block["quarterly"] = [
        {
            "quarter": row.quarter,
            "transactions": int(row.transactions),
            "median_psm": float(row.median_psm),
            "median_price_aed": float(row.median_price_aed),
        }
        for row in quarterly.itertuples(index=False)
    ]
    if asof is not None:
        counts = quarterly.set_index("quarter")["transactions"]
        medians = quarterly.set_index("quarter")["median_psm"]
        block["yoy_growth_pct"] = _plain(
            _growth(medians.get(str(asof)), medians.get(str(asof - 4)), int(counts.get(str(asof), 0)), int(counts.get(str(asof - 4), 0)), min_n)
        )
        block["qoq_growth_pct"] = _plain(
            _growth(medians.get(str(asof)), medians.get(str(asof - 1)), int(counts.get(str(asof), 0)), int(counts.get(str(asof - 1), 0)), min_n)
        )
    return block


def attach_external_geometry(records: list[dict], geojson_path: str | None) -> tuple[list[dict], bool]:
    """Attach coordinates only from a supplied GeoJSON. Never invent geometry."""
    for record in records:
        record["latitude"] = None
        record["longitude"] = None
        record["geometry"] = None
    if not geojson_path:
        return records, False
    path = geojson_path
    try:
        import json
        from pathlib import Path

        file_path = Path(path)
        if not file_path.exists():
            return records, False
        payload = json.loads(file_path.read_text())
    except Exception:
        return records, False
    lookup = {}
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        name = props.get("community_name") or props.get("name")
        if name:
            lookup[str(name).casefold()] = feature.get("geometry")
    matched = False
    for record in records:
        geometry = lookup.get(str(record["community_name"]).casefold())
        if geometry:
            record["geometry"] = geometry
            matched = True
    return records, matched
