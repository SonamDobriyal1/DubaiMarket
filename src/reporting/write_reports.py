"""Write the narrative reports from computed artifacts. No figures are typed in by hand."""

from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd

from src.common import load_config, resolve


def write_reports(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    interim = resolve(cfg["paths"]["interim"])
    processed = resolve(cfg["paths"]["processed"])
    analytics = resolve(cfg["paths"]["analytics"])
    reports = resolve(cfg["paths"]["reports"])
    reports.mkdir(parents=True, exist_ok=True)
    for name in ("missing_values.csv", "duplicate_analysis.csv", "transaction_type_summary.csv", "filter_log.csv"):
        source = interim / name
        if source.exists():
            shutil.copy(source, reports / name)

    audit = json.loads((reports / "dataset_audit.json").read_text())
    summary = json.loads((interim / "preprocessing_summary.json").read_text())
    filters = pd.read_csv(interim / "filter_log.csv")
    sales = pd.read_parquet(processed / "residential_sales.parquet", columns=[
        "instance_date", "actual_worth", "price_per_sqm", "procedure_area", "property_type_en",
        "reg_type_en", "area_name_en", "master_project_en", "bedroom_count", "transaction_year",
    ])
    sales["instance_date"] = pd.to_datetime(sales["instance_date"])
    registry = json.loads((analytics / "community_registry.json").read_text())
    rental = json.loads((analytics / "rental_feasibility.json").read_text())
    overview = json.loads((analytics / "market_overview.json").read_text())
    feature_meta = json.loads((processed / "feature_metadata.json").read_text())
    evaluation = json.loads((analytics / "model_evaluation.json").read_text()) if (analytics / "model_evaluation.json").exists() else None
    comparison = pd.read_csv(analytics / "model_comparison.csv") if (analytics / "model_comparison.csv").exists() else None

    (reports / "data_quality_report.md").write_text(_quality(audit, summary, filters, rental))
    (reports / "preprocessing_report.md").write_text(_preprocessing(summary, filters, cfg))
    (reports / "eda_report.md").write_text(_eda(sales, overview))
    (reports / "feature_engineering.md").write_text(_features(feature_meta))
    (reports / "dubai_market_intelligence.md").write_text(_market(overview, sales))
    (reports / "community_analytics.md").write_text(_communities(analytics, registry))
    (reports / "api_documentation.md").write_text(_api())
    if evaluation is not None and comparison is not None:
        (reports / "model_comparison.md").write_text(_model_comparison(comparison, evaluation))
        (reports / "model_evaluation.md").write_text(_model_evaluation(evaluation))
        (reports / "prediction_intervals.md").write_text(_intervals(evaluation))
        (reports / "methodology.md").write_text(_methodology(audit, summary, feature_meta, evaluation, rental))
        (reports / "production_readiness.md").write_text(_readiness(evaluation, rental, audit))
    else:
        note = "Model artifacts are not available yet. Re-run report generation after training.\n"
        for name in ("model_comparison.md", "model_evaluation.md", "prediction_intervals.md", "methodology.md", "production_readiness.md"):
            (reports / name).write_text(note)
    print("reports written", reports, flush=True)


def _quality(audit, summary, filters, rental) -> str:
    identity = audit["meter_sale_price_identity"]
    dup = audit["duplicates"]
    lines = [
        "# Data quality report",
        "",
        f"The supplied file has **{audit['n_rows']:,} rows** and **{audit['n_columns']} columns**, using about {audit['memory_mebibytes']:.0f} MiB in memory. The project brief's figure of 52,216 rows does not describe this file.",
        "",
        f"Parsed transaction dates run from {audit['date_min_parsed']} to {audit['date_max_parsed']}. {audit['n_unparsed_dates']} date strings did not parse as Gregorian dates. Their raw values are {audit['unparsed_date_examples']}. They are mortgage records and are excluded from the residential sale population.",
        "",
        "## Duplicates",
        "",
        f"There are {dup['n_unique_transaction_id']:,} distinct `transaction_id` values and {dup['n_exact_duplicate_extra_rows']:,} extra exact copies. Conflicting ids on price, area, procedure, and date: {dup['ids_with_conflicting_values']}. {dup['conclusion']}",
        "",
        "## Target and units",
        "",
        identity["conclusion"],
        f"Rows with a relative difference above 1%: {identity['n_relative_diff_gt_1pct']}. Maximum absolute difference: {identity['abs_diff_max']:.4f}.",
        "",
        audit["units_interpretation"]["evidence"],
        "",
        audit["target_assessment"]["reason"],
        "",
        "## What a user cannot supply at prediction time",
        "",
        "These fields are excluded from the market-value model: " + ", ".join(f"`{c}`" for c in audit["unavailable_at_prediction_time"]) + ".",
        "",
        "`meter_sale_price` is a restatement of the target divided by area. Asking price is not in the file and is not a feature.",
        "",
        "## Rental fields",
        "",
        f"After deduplication, {rental['rent_value_non_null_after_dedup']:,} rows have `rent_value`. Transaction groups: {rental['trans_group_counts']}.",
        rental["reason"],
        "",
        "## Filters",
        "",
        _filter_table(filters),
        "",
        f"Cleaned rows: {summary['cleaned_rows']:,}. Primary residential sales: {summary['primary_rows']:,}. Primary plus delayed sales: {summary['extended_rows']:,}.",
        "",
        "Non-residential usages, mortgages, gifts, land, and buildings remain in `cleaned_transactions.parquet` with an exclusion reason. They are not silently deleted from the analytical file.",
    ]
    return "\n".join(lines) + "\n"


def _preprocessing(summary, filters, cfg) -> str:
    rules = cfg["outliers"]
    return "\n".join([
        "# Preprocessing report",
        "",
        "The eligibility policy keeps arm's-length residential dwelling sales and leaves every other row in the cleaned file with a reason.",
        "",
        "Primary procedures are `Sell` and `Sell - Pre registration`. `Delayed Sell` is retained only in the extended file because it is a real consideration with deferred registration, not an ordinary spot sale. Development registrations, sale-on-payment-plan, lease-to-own, gifts, grants, and every mortgage procedure are out of the valuation population.",
        "",
        "Property scope is Residential usage and Unit or Villa. Subtypes kept are Flat, Villa, Stacked Townhouses, Hotel Apartment, and missing subtype. Office, shop, and other non-dwelling subtypes are excluded even if the usage field says Residential.",
        "",
        f"Domain screens remove unit area outside [{rules['unit_area_min']}, {rules['unit_area_max']}] sqm, villa area outside [{rules['villa_area_min']}, {rules['villa_area_max']}] sqm, and AED per sqm outside [{rules['min_psm']}, {rules['max_psm']}]. The upper AED/sqm bound is an inconsistency ceiling. High prices below it stay in the model.",
        "",
        _filter_table(filters),
        "",
        f"Primary date span: {summary['date_min_primary']} to {summary['date_max_primary']}.",
        "",
        "Whitespace was collapsed. Case-only label variants were not merged, because a case difference can be a different project. User input matching is case-insensitive and returns an error when it is ambiguous.",
        "",
        "Bedroom labels: Studio is 0. `N B/R` is N. Penthouse, single room, office, shop, and other non-count labels stay missing, with a penthouse flag when the label is PENTHOUSE.",
        "",
    ])


def _eda(sales, overview) -> str:
    by_year = sales.groupby(sales["instance_date"].dt.year).size()
    reg = sales.groupby("reg_type_en")["actual_worth"].agg(["size", "median"])
    return "\n".join([
        "# Exploratory analysis",
        "",
        "All figures below use the primary residential sale population after the documented screens. Associations are descriptive.",
        "",
        f"Transactions: {overview['transactions']:,}. Total value: {overview['total_value_aed']:,.0f} AED. Median price: {overview['median_price_aed']:,.0f} AED. Mean price: {overview['mean_price_aed']:,.0f} AED. Median AED per sqm: {overview['median_psm']:,.0f}.",
        "",
        f"Dates: {overview['date_min']} to {overview['date_max']}. The latest complete quarter used for growth is {overview['latest_complete_quarter']}, because the file ends before the end of the following quarter.",
        "",
        f"Official-area concentration: top 10 areas account for {overview['top_10_area_transaction_share']:.1%} of primary sales. The Herfindahl index of area transaction shares is {overview['hhi_transaction_count_by_official_area']:.3f}.",
        "",
        "Registration mix:",
        "",
        reg.to_string(),
        "",
        "Year counts for the primary population are in the modeling table and the monthly chart data at `reports/figures/data/monthly_market.csv`.",
        "",
        f"Earliest primary-sale year in this frame: {int(by_year.index.min())} ({int(by_year.iloc[0]):,} sales). Latest year: {int(by_year.index.max())} ({int(by_year.iloc[-1]):,} sales).",
        "",
        "Interactive charts, when generated, are HTML files in `reports/figures/`. Scatter and box charts use random samples and say so in the title. Rankings of median AED per sqm require at least 50 sales so a handful of transactions cannot define the top or bottom of the market.",
        "",
        "Price rises with size, but not linearly, and AED per sqm differs by community, type, and existing versus off-plan. Those are associations in the registered sales, not effects of changing one attribute while holding the market constant.",
        "",
    ])


def _features(meta) -> str:
    return "\n".join([
        "# Feature engineering",
        "",
        meta["history_rule"],
        "",
        f"Categorical features: {', '.join(meta['categorical_features'])}.",
        "",
        f"Numeric features: {', '.join(meta['numeric_features'])}.",
        "",
        "Forbidden inputs, which are not in either list: " + ", ".join(meta["forbidden_features"]) + ".",
        "",
        meta["splits"]["rule"],
        "",
        "Split counts: " + json.dumps(meta["splits"]["counts"]) + ".",
        "",
        f"Validation starts {meta['splits']['validation_start']}. Selection slice starts {meta['splits']['validation_selection_start']}. Conformal slice starts {meta['splits']['validation_conformal_start']}. Test starts {meta['splits']['test_start']}. Inner training tail starts {meta['splits']['train_inner_tail_start']}.",
        "",
        "Building and project history is shrunk toward the official-area median. The shrinkage weight is n/(n+10). A level with no prior sales stays missing. Trees keep missing numeric values. The linear model and the random forest use training-set medians plus, for the linear model, smoothed target encodings fit on training rows only.",
        "",
        "Same-month sales are not visible to a row. A valuation in month M uses the latest history month strictly before M.",
        "",
    ])


def _market(overview, sales) -> str:
    return "\n".join([
        "# Dubai market intelligence",
        "",
        "This report covers primary residential dwelling sales only. It is not the full DLD transaction tape. Mortgages, gifts, commercial sales, and land are excluded from these totals.",
        "",
        f"From {overview['date_min']} to {overview['date_max']} the primary population contains {overview['transactions']:,} sales, {overview['total_value_aed']:,.0f} AED of registered consideration, a median price of {overview['median_price_aed']:,.0f} AED, and a median of {overview['median_psm']:,.0f} AED per sqm.",
        "",
        f"The mean price is {overview['mean_price_aed']:,.0f} AED, above the median, which is the usual right skew of sale prices. Medians are the headline location statistics.",
        "",
        f"Top 10 official areas by count: {overview['top_10_area_transaction_share']:.1%} of sales. HHI: {overview['hhi_transaction_count_by_official_area']:.3f}.",
        "",
        "Existing and off-plan mixes, and the monthly and quarterly series, are in `data/analytics/market_overview.json` and the Plotly files under `reports/figures/`.",
        "",
        "Marketing names such as Dubai Marina are master projects. Marsa Dubai is the official area that contains almost all Dubai Marina master-project sales. The two fields are both retained. The product does not rename one as the other unless the user selects that master project and its sales are at least 99% inside one official area.",
        "",
        f"Mean procedure area: {sales['procedure_area'].mean():.1f} sqm. Median procedure area: {sales['procedure_area'].median():.1f} sqm.",
        "",
    ])


def _communities(analytics, registry) -> str:
    summary = pd.read_parquet(analytics / "community_summary.parquet")
    named = ["Dubai Marina", "DownTown Dubai", "The Greens", "Al Furjan", "The Gardens"]
    lines = [
        "# Community analytics",
        "",
        "Growth rates use median AED per sqm and are reported only when both periods have at least 20 sales. Blank growth is an insufficient sample, not a zero change.",
        "",
        "Cross-sectional dispersion is the median absolute deviation of AED per sqm divided by the median. It describes how spread out prices are in the sample. Time-series volatility is the standard deviation of quarter-to-quarter changes in the quarterly median, and it is blank when there are fewer than six usable changes. A high price level is not labeled as high volatility.",
        "",
        "Activity, stability, growth, and data-confidence scores are percentile or log-sample descriptions. They are not investment recommendations.",
        "",
        "## Requested names",
        "",
    ]
    for name in named:
        hits = [row for row in registry if row["community_name"] == name]
        if not hits:
            lines.append(f"- {name}: no registry row.")
            continue
        for hit in hits:
            lines.append(
                f"- {hit['community_kind']} `{hit['community_name']}`: {hit['residential_primary_sales']:,} primary residential sales "
                f"out of {hit['rows_all_procedures']:,} deduplicated rows. Property types across all procedures: {hit['property_type_counts_all_procedures']}."
            )
    lines += [
        "",
        _gardens_sentence(registry),
        "",
        f"Community summary rows: {len(summary):,} across official areas and master projects. Latest complete quarter on those rows: {summary['latest_complete_quarter'].iloc[0]}.",
        "",
        "Detail is in `data/analytics/community_summary.parquet` and the monthly, quarterly, property-type, and bedroom metric files.",
        "",
    ]
    return "\n".join(lines)


def _gardens_sentence(registry) -> str:
    hits = [row for row in registry if row["community_name"] == "The Gardens"]
    if not hits:
        return "The Gardens does not appear as a community name in the deduplicated file."
    sales = sum(int(row["residential_primary_sales"]) for row in hits)
    if sales < 30:
        return (
            f"The Gardens has {sales} primary residential dwelling sales across its registry rows. "
            "The valuation API refuses communities below 30 such sales instead of returning an unsupported estimate."
        )
    return f"The Gardens has {sales} primary residential dwelling sales."


def _model_comparison(comparison, evaluation) -> str:
    show = comparison.copy()
    lines = [
        "# Model comparison",
        "",
        evaluation["selection_rule"],
        "",
        f"Selected candidate: `{evaluation['candidate_name']}` ({evaluation['selected_model']}). Validation-selection MAE: {evaluation['validation_selection_mae_aed']:,.0f} AED.",
        "",
        "Test metrics were computed after that choice. They did not choose the winner.",
        "",
        "CatBoost's untouched-test MAE under the precommitted calibration is lower than the selected model's. The selection rule ranks validation MAE, so the deployed model was not replaced after the test scores were known.",
        "",
        "The ridge `train_seconds` value records the scoring call that followed the fit, not the fit itself. The random-forest seconds include that model's fit.",
        "",
        _markdown_table(show),
        "",
        "WAPE uses the sum of absolute actual prices as the denominator. Median absolute percentage error is the median of |error| / actual.",
        "",
        "The IQR sensitivity row, when present, refits the chosen algorithm after dropping training rows outside a wide within-type MAD fence and scores the same validation rows. It is not the production training set.",
        "",
    ]
    return "\n".join(lines)


def _model_evaluation(evaluation) -> str:
    test = evaluation["test_metrics"]
    return "\n".join([
        "# Model evaluation",
        "",
        f"Test rows: {evaluation['n_test']:,}. Train rows: {evaluation['n_train']:,}.",
        "",
        f"Test MAE {test['mae_aed']:,.0f} AED, RMSE {test['rmse_aed']:,.0f} AED, R² {test['r2']:.3f}, median absolute error {test['median_absolute_error_aed']:,.0f} AED.",
        "",
        f"WAPE {test['wape']:.3f} (denominator: {test['wape_denominator']}). Median absolute percentage error {test['median_absolute_percentage_error']:.3f}.",
        "",
        f"Share of test predictions within 10% / 20% / 30%: {test['within_10pct']:.1%} / {test['within_20pct']:.1%} / {test['within_30pct']:.1%}.",
        "",
        f"Log-price MAE {test['mae_log']:.3f}, RMSE {test['rmse_log']:.3f}.",
        "",
        "Segment metrics, including communities and price bands with at least 30 test sales and a within-20% rate under 40%, are flagged `unreliable` in `data/analytics/segment_metrics.csv`. Segments under 30 sales are `low_sample` rather than labeled unreliable.",
        "",
        "Feature importance is an association between a feature and the model's prediction. It is not a causal effect of changing that feature.",
        "",
        "Backtests:",
        "",
        json.dumps(evaluation.get("backtests"), indent=2, default=str),
        "",
        "IQR sensitivity:",
        "",
        json.dumps(evaluation.get("iqr_sensitivity"), indent=2, default=str),
        "",
    ])


def _intervals(evaluation) -> str:
    interval = evaluation["interval"]
    overall = interval.get("overall", {})
    return "\n".join([
        "# Prediction interval validation",
        "",
        interval.get("interpretation", ""),
        "",
        f"Nominal coverage: {interval.get('nominal_coverage')}. Method: {interval.get('method')}.",
        "",
        "Calibration window: " + json.dumps(interval.get("calibration_window")) + ".",
        "",
        f"Test empirical coverage: {overall.get('empirical_coverage')}. Mean width: {overall.get('mean_width_aed')} AED. Median width: {overall.get('median_width_aed')} AED. Test interval rows: {overall.get('n')}.",
        "",
        "Segment coverage is in the same JSON under `segments`. A nominal 90% interval does not promise 90% coverage inside every community or for an individual property.",
        "",
        "The interval is a range for one property's potential transaction price. It is not a confidence interval for the average price of similar properties.",
        "",
    ])


def _methodology(audit, summary, feature_meta, evaluation, rental) -> str:
    return "\n".join([
        "# Methodology",
        "",
        f"Source file: `{audit['source_path']}` with {audit['n_rows']:,} rows, {summary['cleaned_rows']:,} after exact-id deduplication, and {summary['primary_rows']:,} primary residential sales from {summary['date_min_primary']} to {summary['date_max_primary']}.",
        "",
        "The model predicts `actual_worth` for a residential unit or villa sale. Asking price is applied only after prediction, to compute the gap and the interval-based classification.",
        "",
        feature_meta["history_rule"],
        "",
        evaluation["selection_rule"],
        "",
        f"Deployed model: {evaluation['selected_model']}. Test MAE: {evaluation['test_metrics']['mae_aed']:,.0f} AED.",
        "",
        rental["reason"],
        "",
        "No coordinates were created. Map payloads leave latitude, longitude, and geometry null unless an external GeoJSON is joined by name.",
        "",
    ])


def _readiness(evaluation, rental, audit) -> str:
    return "\n".join([
        "# Production readiness and limitations",
        "",
        "The API serves the frozen model, leakage-safe history tables, and precomputed community metrics. It validates inputs, returns structured errors, caches the model in memory, and applies a simple per-IP rate limit.",
        "",
        "Limitations:",
        "",
        "- The file is a DLD transaction extract, not a listing database, and it ends on " + str(audit["date_max_parsed"]) + ". A later valuation date reuses the last observed history and is flagged stale. It does not forecast a 2026 price path.",
        "- Off-plan pre-registration prices and existing resales are different economic events. The comparison includes separate models, and the deployed choice is the one that won the precommitted validation rule.",
        "- Prediction intervals are for one transaction. Empirical test coverage is an average. It is not a guarantee for every community.",
        "- " + rental["reason"],
        "- Scores and classifications are not investment advice and are not statements that a property will sell at the estimate.",
        "- Luxury sales below the inconsistency ceiling were retained. A sensitivity model that applies a wide MAD fence is reported and not automatically promoted.",
        "- Duplicate transaction ids were exact copies. Arabic columns that were not one-to-one with English were kept.",
        "",
        f"Selected model `{evaluation['selected_model']}` test MAE {evaluation['test_metrics']['mae_aed']:,.0f} AED, within 20% on {evaluation['test_metrics']['within_20pct']:.1%} of the untouched test period.",
        "",
    ])


def _api() -> str:
    return "\n".join([
        "# API documentation",
        "",
        "Start the service from the repository root after the artifacts exist:",
        "",
        "```bash",
        "uvicorn api.main:app --reload",
        "```",
        "",
        "Interactive schema: `/docs`.",
        "",
        "| Method | Path | Role |",
        "| --- | --- | --- |",
        "| POST | `/api/valuation/predict` | Estimate, interval, classification, comparables, trend, reliability, model version |",
        "| POST | `/api/valuation/comparables` | Similar earlier sales and similarity scores |",
        "| GET | `/api/market/overview` | Primary-sale market totals and monthly/quarterly series |",
        "| GET | `/api/communities` | Community index |",
        "| GET | `/api/communities/{community_id}` | One community |",
        "| GET | `/api/communities/{community_id}/trends` | Monthly and quarterly series |",
        "| POST | `/api/communities/compare` | Two to five communities on the same filters |",
        "| GET | `/api/map/communities` | Metrics with null geometry unless an external GeoJSON is joined |",
        "| GET | `/api/model/methodology` | Coverage, features, split, test metrics, limitations |",
        "",
        "Community ids look like `master__dubai-marina` and `area__marsa-dubai`. `DownTown Dubai` is the spelling in the file. `Downtown Dubai` is accepted as an alias.",
        "",
        "Errors use `{\"error\": {\"code\", \"message\", \"details\"}}`. Unknown or thin communities return 422 rather than a number. Invalid JSON fields return 422. More than 60 requests per minute from one IP return 429.",
        "",
        "Asking price is required for `/predict` and is not passed into the model.",
        "",
    ])


def _markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in frame.itertuples(index=False):
        cells = []
        for value in row:
            if pd.isna(value):
                cells.append("")
            elif isinstance(value, float):
                cells.append(f"{value:.6g}")
            else:
                cells.append(str(value).replace("|", "/").replace("\n", " "))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _filter_table(filters: pd.DataFrame) -> str:
    columns = [c for c in ("step", "rows_before", "rows_removed", "rows_after") if c in filters.columns]
    return filters[columns].to_string(index=False)


if __name__ == "__main__":
    write_reports()
