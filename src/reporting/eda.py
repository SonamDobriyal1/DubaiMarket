"""Aggregate charts for the primary residential sales population."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.common import load_config, resolve


def run_eda(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    sales = pd.read_parquet(resolve(cfg["paths"]["processed"]) / "residential_sales.parquet")
    sales["instance_date"] = pd.to_datetime(sales["instance_date"])
    figures = resolve(cfg["paths"]["figures"])
    data_dir = figures / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    sales["year_month"] = sales["instance_date"].dt.to_period("M").astype(str)
    sales["quarter"] = sales["instance_date"].dt.to_period("Q").astype(str)
    monthly = (
        sales.groupby("year_month")
        .agg(transactions=("transaction_id", "size"), total_value_aed=("actual_worth", "sum"), median_psm=("price_per_sqm", "median"), median_price=("actual_worth", "median"))
        .reset_index()
    )
    monthly.to_csv(data_dir / "monthly_market.csv", index=False)
    _html(px.line(monthly, x="year_month", y="transactions", title="Monthly residential sale count"), figures / "transaction_timeline.html")
    _html(px.bar(monthly, x="year_month", y="transactions", title="Monthly sales volume"), figures / "monthly_sales_volume.html")
    quarterly = sales.groupby("quarter").agg(median_psm=("price_per_sqm", "median"), transactions=("transaction_id", "size")).reset_index()
    quarterly.to_csv(data_dir / "quarterly_psm.csv", index=False)
    _html(px.line(quarterly, x="quarter", y="median_psm", title="Quarterly median AED per sqm"), figures / "quarterly_median_psm.html")

    area = sales.groupby("area_name_en").agg(transactions=("transaction_id", "size"), median_psm=("price_per_sqm", "median"), median_price=("actual_worth", "median")).reset_index()
    ranked = area.loc[area["transactions"].ge(50)].sort_values("median_psm", ascending=False)
    ranked.to_csv(data_dir / "area_rankings.csv", index=False)
    _html(px.bar(ranked.head(20), x="median_psm", y="area_name_en", orientation="h", title="Highest median AED/sqm, official areas with at least 50 sales"), figures / "community_price_rank.html")
    _html(px.bar(area.sort_values("transactions", ascending=False).head(20), x="transactions", y="area_name_en", orientation="h", title="Highest transaction counts by official area"), figures / "community_volume_rank.html")

    types = sales["property_type_en"].value_counts().rename_axis("property_type").reset_index(name="transactions")
    types.to_csv(data_dir / "property_type.csv", index=False)
    _html(px.bar(types, x="property_type", y="transactions", title="Residential property type"), figures / "property_type_breakdown.html")
    beds = sales["bedroom_count"].map(lambda v: "missing" if pd.isna(v) else str(int(v))).value_counts().rename_axis("bedrooms").reset_index(name="transactions")
    beds.to_csv(data_dir / "bedrooms.csv", index=False)
    _html(px.bar(beds, x="bedrooms", y="transactions", title="Bedroom count, with missing kept separate"), figures / "bedroom_distribution.html")
    reg = sales.groupby("reg_type_en").agg(transactions=("transaction_id", "size"), median_psm=("price_per_sqm", "median")).reset_index()
    reg.to_csv(data_dir / "registration_mix.csv", index=False)
    _html(px.bar(reg, x="reg_type_en", y="transactions", title="Existing versus off-plan transaction count"), figures / "existing_vs_offplan.html")

    log_price = np.log10(sales["actual_worth"].clip(lower=1))
    hist = pd.DataFrame({"log10_price": log_price})
    _html(px.histogram(hist, x="log10_price", nbins=60, title="Sale price distribution, log10 AED"), figures / "price_histogram.html")
    sample = sales.sample(n=min(8000, len(sales)), random_state=42)
    sample[["procedure_area", "actual_worth", "property_type_en"]].to_csv(data_dir / "size_price_sample.csv", index=False)
    _html(px.scatter(sample, x="procedure_area", y="actual_worth", color="property_type_en", opacity=0.35, title="Size versus price, 8,000-row sample", log_y=True), figures / "size_vs_price.html")
    box_sample = sales.sample(n=min(15000, len(sales)), random_state=42)
    _html(px.box(box_sample, x="property_type_en", y="price_per_sqm", title="AED per sqm by property type, 15,000-row sample"), figures / "psm_boxplot.html")

    numeric = sales[["procedure_area", "actual_worth", "price_per_sqm", "bedroom_count", "has_parking", "transaction_year", "transaction_month"]].apply(pd.to_numeric, errors="coerce")
    corr = numeric.corr(method="pearson")
    spearman = numeric.corr(method="spearman")
    corr.to_csv(data_dir / "pearson_correlation.csv")
    spearman.to_csv(data_dir / "spearman_correlation.csv")
    _html(px.imshow(corr, text_auto=".2f", title="Pearson correlation, descriptive only"), figures / "correlation_heatmap.html")

    top = area.sort_values("transactions", ascending=False).head(15)["area_name_en"]
    q = sales.loc[sales["area_name_en"].isin(top)].groupby(["area_name_en", "quarter"]).agg(median_psm=("price_per_sqm", "median"), n=("transaction_id", "size")).reset_index()
    q["yoy"] = q.groupby("area_name_en")["median_psm"].pct_change(4) * 100
    q.loc[q["n"].lt(20), "yoy"] = np.nan
    q.to_csv(data_dir / "community_growth_heatmap.csv", index=False)
    pivot = q.pivot(index="area_name_en", columns="quarter", values="yoy")
    _html(px.imshow(pivot, title="Year-over-year median AED/sqm change, blank when a quarter has fewer than 20 sales"), figures / "community_growth_heatmap.html")
    dispersion = sales.groupby("area_name_en")["price_per_sqm"].apply(lambda s: float((s - s.median()).abs().median() / s.median()) if s.median() else np.nan)
    vol = pd.DataFrame({"area_name_en": dispersion.index, "cross_sectional_dispersion": dispersion.values, "transactions": area.set_index("area_name_en").loc[dispersion.index, "transactions"].values})
    vol = vol.loc[vol["transactions"].ge(50)]
    vol.to_csv(data_dir / "community_dispersion.csv", index=False)
    _html(px.scatter(vol, x="transactions", y="cross_sectional_dispersion", hover_name="area_name_en", title="Cross-sectional AED/sqm dispersion, not a time-series volatility claim"), figures / "community_volatility.html")
    print("eda figures", figures, flush=True)


def _html(fig, path):
    fig.update_layout(template="plotly_white", height=560, margin=dict(l=40, r=20, t=60, b=40))
    fig.write_html(path, include_plotlyjs="cdn")


if __name__ == "__main__":
    run_eda()
