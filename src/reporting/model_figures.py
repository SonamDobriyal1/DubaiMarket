"""Diagnostic charts for the untouched test period."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px

from src.common import load_config, resolve


def run_model_figures(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    analytics = resolve(cfg["paths"]["analytics"])
    figures = resolve(cfg["paths"]["figures"])
    path = analytics / "test_predictions.parquet"
    if not path.exists():
        print("no test predictions yet", flush=True)
        return
    frame = pd.read_parquet(path)
    frame["instance_date"] = pd.to_datetime(frame["instance_date"])
    sample = frame.sample(n=min(6000, len(frame)), random_state=42)
    sample.to_csv(figures / "data" / "test_prediction_sample.csv", index=False)
    _html(
        px.scatter(sample, x="actual_worth", y="predicted_value_aed", opacity=0.35, title="Test actual versus predicted, sample"),
        figures / "actual_vs_predicted.html",
    )
    residual = frame["predicted_value_aed"] - frame["actual_worth"]
    _html(px.histogram(pd.DataFrame({"residual_aed": residual}), x="residual_aed", nbins=80, title="Test residual distribution"), figures / "residual_distribution.html")
    _html(
        px.scatter(sample, x="predicted_value_aed", y=sample["predicted_value_aed"] - sample["actual_worth"], opacity=0.35, title="Test residual versus predicted, sample"),
        figures / "residual_vs_predicted.html",
    )
    by_type = frame.groupby("property_type_en")["absolute_percentage_error"].median().reset_index()
    _html(px.bar(by_type, x="property_type_en", y="absolute_percentage_error", title="Test median absolute percentage error by type"), figures / "error_by_property_type.html")
    frame["price_band"] = pd.cut(frame["actual_worth"], [0, 5e5, 1e6, 2e6, 5e6, 1e7, np.inf], labels=["<0.5m", "0.5-1m", "1-2m", "2-5m", "5-10m", "10m+"], right=False)
    by_price = frame.groupby("price_band", observed=False)["absolute_percentage_error"].median().reset_index()
    _html(px.bar(by_price, x="price_band", y="absolute_percentage_error", title="Test median absolute percentage error by price band"), figures / "error_by_price_band.html")
    monthly = frame.groupby(frame["instance_date"].dt.to_period("M").astype(str))["absolute_percentage_error"].median().reset_index()
    monthly.columns = ["month", "median_ape"]
    _html(px.line(monthly, x="month", y="median_ape", title="Test median absolute percentage error by month"), figures / "error_over_time.html")
    top = frame.groupby("area_name_en").agg(n=("transaction_id", "size"), median_ae=("absolute_error_aed", "median")).reset_index()
    top = top.loc[top["n"].ge(30)].sort_values("median_ae", ascending=False).head(20)
    _html(px.bar(top, x="median_ae", y="area_name_en", orientation="h", title="Highest test median absolute error, areas with at least 30 sales"), figures / "error_by_community.html")
    print("model figures written", flush=True)


def _html(fig, path):
    fig.update_layout(template="plotly_white", height=560)
    fig.write_html(path, include_plotlyjs="cdn")


if __name__ == "__main__":
    run_model_figures()
