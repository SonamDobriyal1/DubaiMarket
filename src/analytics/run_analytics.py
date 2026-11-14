"""Write community, market, rental, and map artifacts."""

from __future__ import annotations

import pandas as pd

from src.analytics.market import (
    add_scores,
    build_group_metrics,
    last_complete_quarter,
    market_overview,
    rental_feasibility,
    summarize_communities,
)
from src.common import community_key, load_config, resolve, write_json


def run_analytics(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    processed = resolve(cfg["paths"]["processed"])
    analytics = resolve(cfg["paths"]["analytics"])
    reports = resolve(cfg["paths"]["reports"])
    sales = pd.read_parquet(processed / "residential_sales.parquet")
    sales["instance_date"] = pd.to_datetime(sales["instance_date"])
    cleaned = pd.read_parquet(
        processed / "cleaned_transactions.parquet",
        columns=[
            "transaction_id",
            "instance_date",
            "trans_group_en",
            "procedure_name_en",
            "property_usage_en",
            "property_type_en",
            "area_name_en",
            "master_project_en",
            "rent_value",
            "meter_rent_price",
            "actual_worth",
        ],
    )
    asof = last_complete_quarter(sales["instance_date"].max())
    min_n = int(cfg["analytics"]["min_growth_observations"])
    pieces = []
    monthly = []
    quarterly = []
    by_type = []
    by_bed = []
    registry = []
    for column, kind in (("area_name_en", "official_area"), ("master_project_en", "master_project")):
        built = build_group_metrics(sales, column, kind, min_n)
        summary = summarize_communities(built["frame"], built["quarterly"], column, kind, min_n, asof)
        summary = add_scores(summary)
        pieces.append(summary)
        monthly.append(built["monthly"])
        quarterly.append(built["quarterly"])
        by_type.append(built["property_type"])
        by_bed.append(built["bedroom"])
        registry.extend(_registry_rows(cleaned, sales, column, kind))

    summary = pd.concat(pieces, ignore_index=True)
    monthly_df = pd.concat(monthly, ignore_index=True)
    quarterly_df = pd.concat(quarterly, ignore_index=True)
    type_df = pd.concat(by_type, ignore_index=True)
    bed_df = pd.concat(by_bed, ignore_index=True)
    summary.to_parquet(analytics / "community_summary.parquet", index=False)
    monthly_df.to_parquet(analytics / "community_monthly_metrics.parquet", index=False)
    quarterly_df.to_parquet(analytics / "community_quarterly_metrics.parquet", index=False)
    type_df.to_parquet(analytics / "community_property_type_metrics.parquet", index=False)
    bed_df.to_parquet(analytics / "community_bedroom_metrics.parquet", index=False)

    overview = market_overview(sales, asof)
    rental = rental_feasibility(cleaned)
    write_json(analytics / "market_overview.json", overview)
    write_json(analytics / "rental_feasibility.json", rental)
    write_json(reports / "rental_feasibility.json", rental)
    community_payload = {
        "latest_complete_quarter": str(asof),
        "minimum_growth_observations": min_n,
        "score_disclaimer": (
            "Activity, stability, growth, and confidence scores describe the observed sample. "
            "They are not return forecasts or investment recommendations."
        ),
        "communities": json_ready(summary),
    }
    write_json(analytics / "community_analytics.json", community_payload)
    write_json(analytics / "community_registry.json", registry)
    map_payload = {
        "geometry_available": False,
        "geometry_note": (
            "The transaction file contains no coordinates or polygons. "
            "Map positions stay empty unless an external GeoJSON is supplied to the enrichment interface. "
            "No coordinates were invented."
        ),
        "communities": [
            {
                "community_id": row["community_id"],
                "community_name": row["community_name"],
                "community_kind": row["community_kind"],
                "latitude": None,
                "longitude": None,
                "median_psm": row.get("median_psm"),
                "transactions": row.get("transactions"),
                "yoy_growth_pct": row.get("yoy_growth_pct"),
                "qoq_growth_pct": row.get("qoq_growth_pct"),
                "time_series_volatility": row.get("time_series_volatility"),
                "cross_sectional_dispersion": row.get("cross_sectional_dispersion"),
                "share_unit": row.get("share_unit"),
                "share_villa": row.get("share_villa"),
                "last_transaction": None if pd.isna(row.get("last_transaction")) else str(pd.Timestamp(row["last_transaction"]).date()),
                "latest_complete_quarter": row.get("latest_complete_quarter"),
            }
            for row in json_ready(summary)
        ],
    }
    write_json(analytics / "map_communities.json", map_payload)
    write_json(analytics / "data_dictionary.json", data_dictionary())
    print("analytics communities", len(summary), "asof", asof, flush=True)
    return {"communities": int(len(summary)), "asof": str(asof)}


def _registry_rows(cleaned, sales, column, kind):
    all_counts = cleaned.groupby(column).size() if column in cleaned else pd.Series(dtype=int)
    primary = sales.groupby(column).size()
    types = cleaned.groupby([column, "property_type_en"]).size().unstack(fill_value=0) if column in cleaned else pd.DataFrame()
    areas = None
    if kind == "master_project":
        areas = sales.groupby(["master_project_en", "area_name_en"]).size().rename("n").reset_index()
    rows = []
    names = sorted(set(all_counts.index.dropna().astype(str)) | set(primary.index.dropna().astype(str)))
    for name in names:
        residential = int(primary.get(name, 0))
        modal_area, modal_share = None, None
        if areas is not None:
            part = areas.loc[areas["master_project_en"].eq(name)]
            if not part.empty:
                top = part.sort_values("n", ascending=False).iloc[0]
                modal_area = top["area_name_en"]
                modal_share = float(top["n"] / part["n"].sum())
        type_counts = {}
        if not types.empty and name in types.index:
            type_counts = {str(k): int(v) for k, v in types.loc[name].items() if v}
        rows.append(
            {
                "community_id": community_key(kind, name),
                "community_kind": kind,
                "community_name": name,
                "rows_all_procedures": int(all_counts.get(name, 0)),
                "residential_primary_sales": residential,
                "property_type_counts_all_procedures": type_counts,
                "modal_area": modal_area,
                "modal_area_share": modal_share,
            }
        )
    return rows


def json_ready(frame: pd.DataFrame) -> list[dict]:
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            out[column] = out[column].dt.strftime("%Y-%m-%d")
    records = out.to_dict(orient="records")
    cleaned = []
    for record in records:
        item = {}
        for key, value in record.items():
            if pd.isna(value):
                item[key] = None
            elif hasattr(value, "item"):
                item[key] = value.item()
            else:
                item[key] = value
        cleaned.append(item)
    return cleaned


def data_dictionary() -> dict:
    return {
        "population": "Primary rows are residential Unit/Villa sales with procedure Sell or Sell - Pre registration after domain screens.",
        "actual_worth": "Transaction consideration in AED. Target only after eligibility filtering.",
        "procedure_area": "Property area in square meters.",
        "price_per_sqm": "actual_worth / procedure_area. Not a model input.",
        "meter_sale_price": "Source field that matches actual_worth / procedure_area within rounding. Not a model input.",
        "area_name_en": "Official Dubai Land Department area name.",
        "master_project_en": "Developer master-project name such as Dubai Marina or DownTown Dubai. Missing values are preserved.",
        "reg_type_en": "Existing Properties or Off-Plan Properties.",
        "eligibility_tier": "primary, extended_delayed_sell, or excluded.",
        "asking_price": "Not present in the source file and not used to predict market value.",
        "rent_value": "Populated on lease-to-own style mortgage procedures. Not a rental-contract sample.",
        "scores": "Percentile descriptions of observed activity, growth, and quarterly-median variability. Not investment advice.",
    }
