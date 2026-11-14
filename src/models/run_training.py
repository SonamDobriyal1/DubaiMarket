"""Fit, select, and save the residential valuation model."""

from __future__ import annotations

import json
import time

import joblib
import numpy as np
import pandas as pd

from src.common import file_sha256, resolve, write_json
from src.models.intervals import coverage_report, fit_conformal
from src.models.metrics import regression_metrics
from src.models.predict import predict_aed, predict_interval, predict_link
from src.models.train import (
    Candidate,
    _refit,
    available_kinds,
    category_levels,
    fit_ridge,
    link_target,
    load_model_frame,
    slice_by_split,
    train_tail_date,
    tune_kind,
)

try:
    import optuna
except Exception:  # pragma: no cover
    optuna = None

try:
    from sklearn.ensemble import RandomForestRegressor
except Exception:  # pragma: no cover
    RandomForestRegressor = None


IMPROVEMENT_REQUIRED = 0.02


def run_training(cfg: dict) -> dict:
    if optuna is not None:
        optuna.logging.set_verbosity(optuna.logging.WARNING)
    processed = resolve(cfg["paths"]["processed"])
    model_dir = resolve(cfg["paths"]["models"])
    analytics = resolve(cfg["paths"]["analytics"])
    reports = resolve(cfg["paths"]["reports"])
    frame = load_model_frame(processed / "modeling_table.parquet")
    meta = json.loads((processed / "feature_metadata.json").read_text())
    print("modeling rows", len(frame), frame["split"].value_counts().to_dict(), flush=True)

    train = slice_by_split(frame, "train")
    val_fit = slice_by_split(frame, "val_fit")
    val_sel = slice_by_split(frame, "val_sel")
    val_conf = slice_by_split(frame, "val_conf")
    test = slice_by_split(frame, "test")
    tail_start = train_tail_date(meta)
    core = train.loc[train["instance_date"] < tail_start].copy()
    tail = train.loc[train["instance_date"] >= tail_start].copy()
    levels = category_levels(train)
    y_train = train["actual_worth"].to_numpy(dtype=float)
    y_core = link_target(core["actual_worth"], "log")
    y_tail = link_target(tail["actual_worth"], "log")
    global_median = float(train["price_per_sqm"].median())
    dataset_hash = file_sha256(processed / "residential_sales.parquet")

    library_runs = {}
    comparison_rows = []
    trials_blob = {}

    for kind in available_kinds(cfg):
        print(f"tuning {kind}", flush=True)
        started = time.perf_counter()
        params, trees, trials = tune_kind(
            kind,
            core,
            tail,
            y_core,
            y_tail,
            levels,
            int(cfg["training"]["optuna_trials"].get(kind, 0)),
            int(cfg["training"]["max_iterations"]),
            int(cfg["seed"]),
        )
        model = _refit(kind, params, trees, train, link_target(y_train, "log"), levels)
        seconds = time.perf_counter() - started
        library_runs[kind] = {
            "model": model,
            "params": params,
            "trees": trees,
            "seconds": seconds,
            "target_mode": "log",
        }
        trials_blob[kind] = trials
        note = "Tuned on the inner training tail. Precommitted median log-shift calibration."
        if kind == "hist_gradient_boosting":
            note += " Categorical labels with more than 200 training levels are omitted because this algorithm caps cardinality at 255. Building and project price levels remain in the shrunk history features."
        row = _score_candidate(
            f"{kind}_log_unified",
            kind,
            "log",
            "unified",
            model,
            levels,
            val_fit,
            val_sel,
            seconds,
            params,
            trees,
            note,
        )
        comparison_rows.append(row)
        print(f"  val_sel MAE {row['mae_aed']:.0f} in {seconds:.1f}s trees={trees}", flush=True)

    print("fitting ridge and random forest", flush=True)
    ridge_model, ridge_payload, ridge_alpha = fit_ridge(
        train,
        link_target(y_train, "log"),
        core,
        y_core,
        tail,
        y_tail,
    )
    started = time.perf_counter()
    ridge_row = _score_candidate(
        "ridge_log_unified",
        "ridge",
        "log",
        "unified",
        ridge_model,
        levels,
        val_fit,
        val_sel,
        time.perf_counter() - started,
        {"alpha": ridge_alpha},
        None,
        "Smoothed target encoding and one-hot low-cardinality fields, fit on training rows only.",
        ridge_payload=ridge_payload,
    )
    comparison_rows.append(ridge_row)
    library_runs["ridge"] = {
        "model": ridge_model,
        "params": {"alpha": ridge_alpha},
        "trees": None,
        "seconds": ridge_row["train_seconds"],
        "target_mode": "log",
        "ridge_payload": ridge_payload,
    }

    if RandomForestRegressor is not None:
        started = time.perf_counter()
        rf_settings = cfg["training"]["random_forest"]
        medians = _numeric_medians(train)
        rf = RandomForestRegressor(
            n_estimators=int(rf_settings["n_estimators"]),
            max_depth=int(rf_settings["max_depth"]),
            min_samples_leaf=int(rf_settings["min_samples_leaf"]),
            max_samples=int(rf_settings["max_samples"]),
            n_jobs=-1,
            random_state=int(cfg["seed"]),
        )
        from src.models.train import _ordinal_matrix

        rf.fit(_ordinal_matrix(train, levels, medians), link_target(y_train, "log"))
        rf_row = _score_candidate(
            "random_forest_log_unified",
            "random_forest",
            "log",
            "unified",
            rf,
            levels,
            val_fit,
            val_sel,
            time.perf_counter() - started,
            rf_settings,
            int(rf_settings["n_estimators"]),
            "Each tree draws max_samples training rows. Numeric missing values use training medians.",
            rf_medians=medians,
        )
        comparison_rows.append(rf_row)
        library_runs["random_forest"] = {
            "model": rf,
            "params": rf_settings,
            "trees": int(rf_settings["n_estimators"]),
            "seconds": rf_row["train_seconds"],
            "target_mode": "log",
            "rf_medians": medians,
        }

    for name, column in (
        ("baseline_area_median_psm", "area_prior_median_psm"),
        ("baseline_area_type_median_psm", "area_type_prior_median_psm"),
    ):
        comparison_rows.append(
            _score_baseline(name, column, global_median, val_fit, val_sel)
        )

    unified = [row for row in comparison_rows if row["strategy"] == "unified"]
    best = min(unified, key=lambda row: row["mae_aed"])
    print("best unified", best["name"], best["mae_aed"], flush=True)

    # Raw-target challenger for the best tree/linear kind, using the same hyperparameters.
    raw_row = None
    if best["kind"] not in {"baseline"} and best["kind"] in library_runs:
        raw_row = _fit_raw_challenger(best, library_runs, train, core, tail, levels, val_fit, val_sel, cfg)
        comparison_rows.append(raw_row)
        print("raw challenger", raw_row["mae_aed"], flush=True)

    chosen = best
    chosen_mode = best["target_mode"]
    if raw_row is not None and raw_row["mae_aed"] < best["mae_aed"] * (1 - IMPROVEMENT_REQUIRED):
        chosen = raw_row
        chosen_mode = "raw"
        print("selected raw target", flush=True)

    if chosen["kind"] == "baseline":
        base_run = {"model": None, "params": {}, "trees": None, "target_mode": "raw"}
    else:
        base_run = library_runs[chosen["kind"]]
    if chosen_mode == "raw" and raw_row is not None and chosen["kind"] != "baseline":
        base_run = raw_row["_run"]

    segmented_rows = []
    if chosen["kind"] != "baseline":
        for column, strategy in (("reg_type_en", "by_reg_type"), ("property_type_en", "by_property_type")):
            row = _fit_segmented(
                chosen["kind"],
                base_run,
                strategy,
                column,
                chosen_mode,
                train,
                levels,
                val_fit,
                val_sel,
            )
            segmented_rows.append(row)
            comparison_rows.append(row)
            print(strategy, row["mae_aed"], flush=True)

    strategy = "unified"
    segment_column = None
    segment_bundle = None
    for row in segmented_rows:
        if row["mae_aed"] < chosen["mae_aed"] * (1 - IMPROVEMENT_REQUIRED):
            if segment_bundle is None or row["mae_aed"] < segment_bundle["mae_aed"]:
                segment_bundle = row
                strategy = row["strategy"]
                segment_column = row["_column"]
    if segment_bundle is not None:
        chosen = segment_bundle
        print("selected strategy", strategy, flush=True)

    if chosen["kind"] == "baseline":
        iqr_report = {
            "rows_removed": 0,
            "rows_remaining": int(len(train)),
            "by_property_type": [],
            "validation_mae_aed": None,
            "production_uses_iqr_filter": False,
            "reason": "The selected model is the median price-per-sqm baseline, so the MAD training filter was not refit.",
            "row": {
                "name": "iqr_sensitivity_not_run",
                "kind": "baseline",
                "target_mode": "raw",
                "strategy": "unified_iqr_sensitivity",
                "mae_aed": None,
                "median_absolute_error_aed": None,
                "within_20pct": None,
                "train_seconds": None,
                "notes": "Not run because the baseline won the unified comparison.",
            },
        }
    else:
        iqr_report = _iqr_sensitivity(chosen, base_run, chosen_mode, train, levels, val_fit, val_sel, cfg)
    comparison_rows.append(iqr_report["row"])

    final_bundle = _freeze_bundle(
        chosen,
        strategy,
        segment_column,
        segment_bundle,
        base_run,
        levels,
        chosen_mode,
        global_median,
        val_fit,
        val_sel,
        val_conf,
        train,
        cfg,
        meta,
        dataset_hash,
        frame,
    )
    print("production", final_bundle["model_version"], "val_sel", final_bundle["selection_mae_aed"], flush=True)

    test_predictions = _predict_frame(final_bundle, test)
    test_metrics = regression_metrics(test["actual_worth"], test_predictions["predicted_value_aed"])
    groups = {
        "property_type": test["property_type_en"].to_numpy(),
        "reg_type": test["reg_type_en"].to_numpy(),
        "bedrooms": test["bedroom_count"].map(lambda v: "missing" if pd.isna(v) else str(int(v))).to_numpy(),
        "size_band": test["size_band"].to_numpy(),
        "quarter": test["instance_date"].dt.to_period("Q").astype(str).to_numpy(),
    }
    price_bins = [0, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000, np.inf]
    price_labels = ["<0.5m", "0.5-1m", "1-2m", "2-5m", "5-10m", "10m+"]
    groups["price_band"] = pd.cut(test["actual_worth"], price_bins, labels=price_labels, right=False).astype(str).to_numpy()
    high_volume = set(train["area_name_en"].value_counts().head(20).index)
    groups["community_volume"] = np.where(test["area_name_en"].isin(high_volume), "top_20_train_areas", "other_areas")
    interval_report = coverage_report(
        test["actual_worth"],
        test_predictions["lower_aed"],
        test_predictions["upper_aed"],
        groups,
    )
    interval_report["nominal_coverage"] = cfg["intervals"]["nominal_coverage"]
    interval_report["method"] = final_bundle["conformal"]["score"]
    interval_report["interpretation"] = (
        "This is a prediction interval for an individual property's potential transaction price. "
        "It is not a confidence interval for a mean price. "
        "Overall coverage near the nominal level does not guarantee the same coverage in every community."
    )
    interval_report["calibration_window"] = {
        "start": meta["splits"]["validation_conformal_start"],
        "end_exclusive": meta["splits"]["test_start"],
        "n": int(len(val_conf)),
    }

    # Test metrics for every unified candidate. Selection is already frozen.
    for row in comparison_rows:
        predictor = row.get("_predictor")
        if predictor is None:
            continue
        pred = predictor(test)
        row["test_metrics"] = regression_metrics(test["actual_worth"], pred)

    final_bundle["test_metrics"] = test_metrics
    backtests = _backtests(final_bundle, frame, levels, cfg)
    importance = _importance_frame(final_bundle)
    importance.to_csv(analytics / "feature_importance.csv", index=False)
    importance.to_csv(reports / "feature_importance.csv", index=False)

    comparison = pd.DataFrame(
        [
            {
                "model": row["name"],
                "kind": row["kind"],
                "target_mode": row["target_mode"],
                "strategy": row["strategy"],
                "validation_mae_aed": row["mae_aed"],
                "validation_median_ae_aed": row["median_absolute_error_aed"],
                "validation_within_20pct": row["within_20pct"],
                "test_mae_aed": None if "test_metrics" not in row else row["test_metrics"].get("mae_aed"),
                "test_rmse_aed": None if "test_metrics" not in row else row["test_metrics"].get("rmse_aed"),
                "test_r2": None if "test_metrics" not in row else row["test_metrics"].get("r2"),
                "test_median_ae_aed": None if "test_metrics" not in row else row["test_metrics"].get("median_absolute_error_aed"),
                "test_wape": None if "test_metrics" not in row else row["test_metrics"].get("wape"),
                "test_median_ape": None if "test_metrics" not in row else row["test_metrics"].get("median_absolute_percentage_error"),
                "test_within_10pct": None if "test_metrics" not in row else row["test_metrics"].get("within_10pct"),
                "test_within_20pct": None if "test_metrics" not in row else row["test_metrics"].get("within_20pct"),
                "test_within_30pct": None if "test_metrics" not in row else row["test_metrics"].get("within_30pct"),
                "train_seconds": row.get("train_seconds"),
                "selected": row["name"] == final_bundle["candidate_name"],
                "notes": row.get("notes"),
            }
            for row in comparison_rows
        ]
    )
    comparison.to_csv(analytics / "model_comparison.csv", index=False)
    comparison.to_csv(reports / "model_comparison.csv", index=False)

    pred_path = analytics / "test_predictions.parquet"
    test_predictions.to_parquet(pred_path, index=False)
    segment_metrics = _segment_metrics(test, test_predictions)
    segment_metrics.to_csv(analytics / "segment_metrics.csv", index=False)

    evaluation = {
        "selection_rule": (
            "Candidates are ranked by validation-selection MAE in AED after a precommitted "
            "median residual correction fit on the earlier validation slice. "
            f"A raw-target or separate-segment model replaces the unified log model only if it "
            f"reduces that MAE by more than {IMPROVEMENT_REQUIRED:.0%}. "
            "The final calibration menu is searched only for the frozen winner. "
            "Conformal quantiles use the later validation slice. Test metrics are not used to choose the model."
        ),
        "selected_model": final_bundle["model_version"],
        "candidate_name": final_bundle["candidate_name"],
        "validation_selection_mae_aed": final_bundle["selection_mae_aed"],
        "deployed_calibration": final_bundle["calibration"],
        "test_metrics": test_metrics,
        "interval": interval_report,
        "iqr_sensitivity": {k: v for k, v in iqr_report.items() if k != "row"},
        "backtests": backtests,
        "splits": meta["splits"],
        "dataset_sha256": dataset_hash,
        "seed": cfg["seed"],
        "optuna_trials": trials_blob,
        "n_train": int(len(train)),
        "n_val_fit": int(len(val_fit)),
        "n_val_sel": int(len(val_sel)),
        "n_val_conf": int(len(val_conf)),
        "n_test": int(len(test)),
    }
    write_json(analytics / "model_evaluation.json", evaluation)
    write_json(analytics / "valuation_interval_calibration.json", interval_report)
    write_json(reports / "model_evaluation.json", evaluation)

    # Drop non-serializable helpers before joblib.
    serializable = {k: v for k, v in final_bundle.items() if not k.startswith("_")}
    joblib.dump(serializable, model_dir / "production_model.joblib")
    print("test MAE", round(test_metrics["mae_aed"], 1), "coverage", interval_report["overall"], flush=True)
    return evaluation


def _bundle_from_row(row, levels, global_median, mode):
    bundle = {
        "kind": row["kind"],
        "strategy": "unified",
        "target_mode": mode,
        "estimator": row["_estimator"],
        "calibration": row["_calibration"],
        "levels": levels,
        "global_median_psm": global_median,
        "baseline_column": row.get("_baseline_column"),
        "ridge_payload": row.get("_ridge_payload"),
        "rf_medians": row.get("_rf_medians"),
    }
    return bundle


def _score_candidate(name, kind, mode, strategy, model, levels, val_fit, val_sel, seconds, params, trees, notes, ridge_payload=None, rf_medians=None, baseline_column=None):
    bundle = {
        "kind": kind,
        "strategy": "unified",
        "target_mode": mode,
        "estimator": model,
        "levels": levels,
        "ridge_payload": ridge_payload,
        "rf_medians": rf_medians,
        "baseline_column": baseline_column,
        "global_median_psm": None,
        "calibration": {"name": "uncalibrated", "kind": "log_affine" if mode == "log" else "affine", "a": 1.0, "b": 0.0},
    }
    link_fit = predict_link(bundle, val_fit)
    calibration = _precommit(link_fit, val_fit["actual_worth"].to_numpy(), mode)
    bundle["calibration"] = calibration
    pred_sel = predict_aed(bundle, val_sel)
    metrics = regression_metrics(val_sel["actual_worth"], pred_sel)
    return {
        "name": name,
        "kind": kind,
        "target_mode": mode,
        "strategy": strategy,
        "mae_aed": metrics["mae_aed"],
        "median_absolute_error_aed": metrics["median_absolute_error_aed"],
        "within_20pct": metrics["within_20pct"],
        "train_seconds": seconds,
        "hyperparameters": params,
        "n_estimators": trees,
        "notes": notes,
        "_estimator": model,
        "_calibration": calibration,
        "_predictor": lambda df, b=bundle: predict_aed(b, df),
        "_ridge_payload": ridge_payload,
        "_rf_medians": rf_medians,
        "_metrics": metrics,
    }


def _score_baseline(name, column, global_median, val_fit, val_sel):
    bundle = {
        "kind": "baseline",
        "strategy": "unified",
        "target_mode": "raw",
        "estimator": None,
        "calibration": {"name": "identity", "kind": "affine", "a": 1.0, "b": 0.0},
        "levels": {},
        "global_median_psm": global_median,
        "baseline_column": column,
    }
    raw_fit = predict_link(bundle, val_fit)
    shift = float(np.median(val_fit["actual_worth"].to_numpy() - raw_fit))
    bundle["calibration"] = {"name": "median_shift", "kind": "affine", "a": 1.0, "b": shift}
    pred = predict_aed(bundle, val_sel)
    metrics = regression_metrics(val_sel["actual_worth"], pred)
    return {
        "name": name,
        "kind": "baseline",
        "target_mode": "raw",
        "strategy": "unified",
        "mae_aed": metrics["mae_aed"],
        "median_absolute_error_aed": metrics["median_absolute_error_aed"],
        "within_20pct": metrics["within_20pct"],
        "train_seconds": 0.0,
        "hyperparameters": {"column": column, "global_median_psm": global_median},
        "n_estimators": None,
        "notes": "Leakage-safe prior median AED per sqm times size, with a median residual shift fit on val_fit.",
        "_estimator": None,
        "_calibration": bundle["calibration"],
        "_baseline_column": column,
        "_global_median_psm": global_median,
        "_predictor": lambda df, b=bundle: predict_aed(b, df),
        "_metrics": metrics,
    }


def _precommit(pred_link, y, mode):
    if mode == "log":
        resid = np.log(np.clip(y, 1.0, None)) - np.asarray(pred_link)
        return {"name": "median_log_shift", "kind": "log_affine", "a": 1.0, "b": float(np.median(resid))}
    resid = np.asarray(y) - np.asarray(pred_link)
    return {"name": "median_shift", "kind": "affine", "a": 1.0, "b": float(np.median(resid))}


def _fit_raw_challenger(best, library_runs, train, core, tail, levels, val_fit, val_sel, cfg):
    kind = best["kind"]
    run = library_runs[kind]
    y_train = train["actual_worth"].to_numpy(dtype=float)
    started = time.perf_counter()
    if kind == "ridge":
        from src.models.train import _ridge_fit

        alpha = float(run["params"].get("alpha", 1.0))
        model, payload = _ridge_fit(train, y_train, alpha)
        model._ridge_payload = payload
        row = _score_candidate(
            f"{kind}_raw_unified",
            kind,
            "raw",
            "unified",
            model,
            levels,
            val_fit,
            val_sel,
            time.perf_counter() - started,
            {"alpha": alpha},
            None,
            "Same ridge design with an AED target.",
            ridge_payload=payload,
        )
        row["_run"] = {"model": model, "params": {"alpha": alpha}, "trees": None, "ridge_payload": payload, "target_mode": "raw"}
        return row
    if kind == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        from src.models.train import _ordinal_matrix

        medians = run["rf_medians"]
        model = RandomForestRegressor(
            n_estimators=int(run["params"]["n_estimators"]),
            max_depth=int(run["params"]["max_depth"]),
            min_samples_leaf=int(run["params"]["min_samples_leaf"]),
            max_samples=int(run["params"]["max_samples"]),
            n_jobs=-1,
            random_state=int(cfg["seed"]),
        )
        model.fit(_ordinal_matrix(train, levels, medians), y_train)
        row = _score_candidate(
            f"{kind}_raw_unified",
            kind,
            "raw",
            "unified",
            model,
            levels,
            val_fit,
            val_sel,
            time.perf_counter() - started,
            run["params"],
            int(run["params"]["n_estimators"]),
            "Same random-forest settings with an AED target.",
            rf_medians=medians,
        )
        row["_run"] = {"model": model, "params": run["params"], "trees": run["trees"], "rf_medians": medians, "target_mode": "raw"}
        return row
    model = _refit(kind, run["params"], run["trees"], train, y_train, levels)
    row = _score_candidate(
        f"{kind}_raw_unified",
        kind,
        "raw",
        "unified",
        model,
        levels,
        val_fit,
        val_sel,
        time.perf_counter() - started,
        run["params"],
        run["trees"],
        "Same hyperparameters and tree count as the log model, trained on AED.",
    )
    row["_run"] = {"model": model, "params": run["params"], "trees": run["trees"], "target_mode": "raw"}
    return row


def _fit_segmented(kind, run, strategy, column, mode, train, levels, val_fit, val_sel):
    estimators = {}
    y_mode = mode
    for label, part in train.groupby(column):
        if len(part) < 1000:
            continue
        target = part["actual_worth"].to_numpy(dtype=float)
        estimators[str(label)] = _fit_estimator(kind, run, part, target, levels, y_mode)
    # Placeholder predictions are filled below.
    pred_fit = np.full(len(val_fit), np.nan)
    pred_sel = np.full(len(val_sel), np.nan)
    labels_fit = val_fit[column].astype(str)
    labels_sel = val_sel[column].astype(str)
    for label, estimator in estimators.items():
        for dest, data, labels in ((pred_fit, val_fit, labels_fit), (pred_sel, val_sel, labels_sel)):
            mask = labels.eq(label).to_numpy()
            if mask.any():
                link = predict_link(_temp_bundle(kind, run, estimator, levels, y_mode), data.loc[mask])
                dest[mask] = link
    # Segments without a model fall back to the unified estimator.
    fallback = run["model"]
    for dest, data in ((pred_fit, val_fit), (pred_sel, val_sel)):
        missing = ~np.isfinite(dest)
        if missing.any():
            dest[missing] = predict_link(_temp_bundle(kind, run, fallback, levels, y_mode), data.loc[missing])
    calibration = _precommit(pred_fit, val_fit["actual_worth"].to_numpy(), y_mode)
    pred_sel_aed = _apply(pred_sel, calibration, y_mode)
    metrics = regression_metrics(val_sel["actual_worth"], pred_sel_aed)
    started_name = f"{kind}_{y_mode}_{strategy}"
    bundle = {
        "kind": kind,
        "strategy": strategy,
        "segment_column": column,
        "target_mode": y_mode,
        "estimator": fallback,
        "fallback_estimator": fallback,
        "fallback_calibration": calibration,
        "calibration": calibration,
        "segment_estimators": estimators,
        "segment_calibrations": {str(label): calibration for label in estimators},
        "levels": levels,
        "ridge_payload": run.get("ridge_payload"),
        "rf_medians": run.get("rf_medians"),
        "global_median_psm": None,
        "baseline_column": None,
    }
    return {
        "name": started_name,
        "kind": kind,
        "target_mode": y_mode,
        "strategy": strategy,
        "mae_aed": metrics["mae_aed"],
        "median_absolute_error_aed": metrics["median_absolute_error_aed"],
        "within_20pct": metrics["within_20pct"],
        "train_seconds": None,
        "hyperparameters": run.get("params"),
        "n_estimators": run.get("trees"),
        "notes": f"Separate models by {column}, same hyperparameters, precommitted median calibration.",
        "_estimators": estimators,
        "_fallback": fallback,
        "_column": column,
        "_calibration": calibration,
        "_metrics": metrics,
        "_predictor": lambda df, b=bundle: predict_aed(b, df),
    }


def part_key(train, column):
    return column


def _temp_bundle(kind, run, estimator, levels, mode):
    return {
        "kind": kind,
        "estimator": estimator,
        "levels": levels,
        "target_mode": mode,
        "ridge_payload": run.get("ridge_payload"),
        "rf_medians": run.get("rf_medians"),
        "calibration": {"name": "identity", "kind": "log_affine" if mode == "log" else "affine", "a": 1.0, "b": 0.0},
        "global_median_psm": None,
        "baseline_column": None,
    }


def _fit_estimator(kind, run, data, y, levels, mode):
    target = link_target(y, mode)
    if kind == "ridge":
        from src.models.train import _ridge_fit

        model, payload = _ridge_fit(data, target, float(run["params"].get("alpha", 1.0)))
        model._ridge_payload = payload
        return model
    if kind == "random_forest":
        from sklearn.ensemble import RandomForestRegressor
        from src.models.train import _ordinal_matrix

        model = RandomForestRegressor(
            n_estimators=int(run["params"]["n_estimators"]),
            max_depth=int(run["params"]["max_depth"]),
            min_samples_leaf=int(run["params"]["min_samples_leaf"]),
            max_samples=min(int(run["params"]["max_samples"]), len(data)),
            n_jobs=-1,
            random_state=42,
        )
        model.fit(_ordinal_matrix(data, levels, run["rf_medians"]), target)
        return model
    return _refit(kind, run["params"], run["trees"], data, target, levels)


def _apply(pred_link, calibration, mode):
    from src.models.train import apply_calibration

    return apply_calibration(pred_link, calibration, mode)


def _iqr_sensitivity(chosen, run, mode, train, levels, val_fit, val_sel, cfg):
    k = float(cfg["outliers"]["sensitivity_mad_k"])
    keep = pd.Series(True, index=train.index)
    removed = []
    for label, part in train.groupby("property_type_en"):
        psm = part["price_per_sqm"]
        median = float(psm.median())
        mad = float((psm - median).abs().median())
        scale = 1.4826 * mad
        if scale == 0:
            continue
        low, high = median - k * scale, median + k * scale
        drop = ~psm.between(low, high)
        keep.loc[psm.index[drop]] = False
        removed.append(
            {
                "property_type": str(label),
                "rows_removed": int(drop.sum()),
                "lower_psm": low,
                "upper_psm": high,
                "removed_psm_min": None if not drop.any() else float(psm.loc[drop].min()),
                "removed_psm_max": None if not drop.any() else float(psm.loc[drop].max()),
            }
        )
    filtered = train.loc[keep]
    model = _fit_estimator(chosen["kind"], run, filtered, filtered["actual_worth"].to_numpy(), levels, mode)
    row = _score_candidate(
        f"{chosen['kind']}_{mode}_iqr_sensitivity",
        chosen["kind"],
        mode,
        "unified_iqr_sensitivity",
        model,
        levels,
        val_fit,
        val_sel,
        None,
        run.get("params"),
        run.get("trees"),
        "Training rows outside a wide within-type MAD fence were removed. The same validation rows are scored. Not used for production.",
        ridge_payload=run.get("ridge_payload"),
        rf_medians=run.get("rf_medians"),
    )
    return {
        "rows_removed": int((~keep).sum()),
        "rows_remaining": int(keep.sum()),
        "by_property_type": removed,
        "validation_mae_aed": row["mae_aed"],
        "production_uses_iqr_filter": False,
        "reason": (
            "The MAD fence changes which high and low prices the model sees. "
            "It is reported as a sensitivity check and is not the production training set, "
            "because a lower error can come from deleting legitimate tail transactions."
        ),
        "row": row,
    }


def _freeze_bundle(chosen, strategy, segment_column, segment_bundle, base_run, levels, mode, global_median, val_fit, val_sel, val_conf, train, cfg, meta, dataset_hash, frame):
    from src.models.train import choose_calibration

    kind = chosen["kind"]
    if strategy == "unified":
        estimator = chosen["_estimator"]
        link_fit = predict_link(_temp_bundle(kind, {**base_run, "model": estimator, "ridge_payload": chosen.get("_ridge_payload"), "rf_medians": chosen.get("_rf_medians")}, estimator, levels, mode), val_fit)
        link_sel = predict_link(_temp_bundle(kind, {**base_run, "model": estimator, "ridge_payload": chosen.get("_ridge_payload"), "rf_medians": chosen.get("_rf_medians")}, estimator, levels, mode), val_sel)
        calibration, _ = choose_calibration(link_fit, val_fit["actual_worth"].to_numpy(), link_sel, val_sel["actual_worth"].to_numpy(), mode)
        bundle = {
            "kind": kind,
            "strategy": "unified",
            "target_mode": mode,
            "estimator": estimator,
            "fallback_estimator": estimator,
            "fallback_calibration": calibration,
            "calibration": calibration,
            "levels": levels,
            "ridge_payload": chosen.get("_ridge_payload", base_run.get("ridge_payload")),
            "rf_medians": chosen.get("_rf_medians", base_run.get("rf_medians")),
            "global_median_psm": chosen.get("_global_median_psm", global_median),
            "baseline_column": chosen.get("_baseline_column"),
            "segment_estimators": {},
            "segment_calibrations": {},
        }
    else:
        estimators = segment_bundle["_estimators"]
        calibrations = {}
        for label, estimator in estimators.items():
            mask_fit = val_fit[segment_column].astype(str).eq(label)
            mask_sel = val_sel[segment_column].astype(str).eq(label)
            if mask_fit.sum() < 100 or mask_sel.sum() < 100:
                calibrations[label] = segment_bundle["_calibration"]
                continue
            temp = _temp_bundle(kind, base_run, estimator, levels, mode)
            link_fit = predict_link(temp, val_fit.loc[mask_fit])
            link_sel = predict_link(temp, val_sel.loc[mask_sel])
            calibration, _ = choose_calibration(
                link_fit,
                val_fit.loc[mask_fit, "actual_worth"].to_numpy(),
                link_sel,
                val_sel.loc[mask_sel, "actual_worth"].to_numpy(),
                mode,
            )
            calibrations[label] = calibration
        fallback_cal = segment_bundle["_calibration"]
        bundle = {
            "kind": kind,
            "strategy": strategy,
            "segment_column": segment_column,
            "target_mode": mode,
            "estimator": segment_bundle["_fallback"],
            "fallback_estimator": segment_bundle["_fallback"],
            "fallback_calibration": fallback_cal,
            "calibration": fallback_cal,
            "segment_estimators": estimators,
            "segment_calibrations": calibrations,
            "levels": levels,
            "ridge_payload": base_run.get("ridge_payload"),
            "rf_medians": base_run.get("rf_medians"),
            "global_median_psm": global_median,
            "baseline_column": None,
        }
    # Point predictions on the conformal slice use the deployed calibration.
    point_conf = predict_aed(bundle, val_conf)
    conformal = fit_conformal(
        val_conf["actual_worth"].to_numpy(),
        point_conf,
        val_conf["reg_type_en"],
        float(cfg["intervals"]["nominal_coverage"]),
        int(cfg["intervals"]["min_segment_calibration_n"]),
    )
    bundle.update(
        {
            "conformal": conformal,
            "model_version": f"residential-sales-{kind}-{mode}-{strategy}",
            "candidate_name": chosen["name"],
            "selection_mae_aed": chosen["mae_aed"],
            "selection_metric": "validation_selection_mae_aed",
            "hyperparameters": chosen.get("hyperparameters"),
            "n_estimators": chosen.get("n_estimators"),
            "random_seed": int(cfg["seed"]),
            "dataset_sha256": dataset_hash,
            "dataset_version": dataset_hash[:12],
            "feature_version": "history-lag-1-month-v1",
            "categorical_features": meta["categorical_features"],
            "numeric_features": meta["numeric_features"],
            "rare_maps": meta["rare_maps"],
            "split_boundaries": meta["splits"],
            "data_max_date": str(pd.to_datetime(frame["instance_date"]).max().date()),
            "train_date_max": str(train["instance_date"].max().date()),
            "asking_price_used_as_feature": False,
            "notes": chosen.get("notes"),
        }
    )
    return bundle


def _predict_frame(bundle, frame):
    point, lower, upper = predict_interval(bundle, frame)
    out = frame[
        [
            "transaction_id",
            "instance_date",
            "actual_worth",
            "procedure_area",
            "price_per_sqm",
            "area_name_en",
            "master_project_en",
            "property_type_en",
            "bedroom_count",
            "reg_type_en",
            "size_band",
            "split",
        ]
    ].copy()
    out["predicted_value_aed"] = point
    out["lower_aed"] = lower
    out["upper_aed"] = upper
    out["absolute_error_aed"] = np.abs(out["actual_worth"] - out["predicted_value_aed"])
    out["absolute_percentage_error"] = out["absolute_error_aed"] / out["actual_worth"].clip(lower=1)
    return out


def _segment_metrics(test, predictions):
    merged = predictions.copy()
    rows = []
    specs = {
        "property_type": merged["property_type_en"],
        "reg_type": merged["reg_type_en"],
        "bedrooms": merged["bedroom_count"].map(lambda v: "missing" if pd.isna(v) else str(int(v))),
        "size_band": merged["size_band"],
        "area": merged["area_name_en"],
        "master_project": merged["master_project_en"].fillna("__MISSING__"),
    }
    price_bins = [0, 500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000, np.inf]
    price_labels = ["<0.5m", "0.5-1m", "1-2m", "2-5m", "5-10m", "10m+"]
    specs["price_band"] = pd.cut(merged["actual_worth"], price_bins, labels=price_labels, right=False).astype(str)
    specs["quarter"] = merged["instance_date"].dt.to_period("Q").astype(str)
    for family, series in specs.items():
        for label, idx in series.groupby(series).groups.items():
            part = merged.loc[idx]
            metrics = regression_metrics(part["actual_worth"], part["predicted_value_aed"])
            metrics.update({"segment_family": family, "segment": str(label)})
            covered = part["actual_worth"].between(part["lower_aed"], part["upper_aed"])
            metrics["interval_coverage"] = float(covered.mean()) if len(part) else None
            metrics["unreliable"] = bool(metrics["n"] >= 30 and metrics["within_20pct"] < 0.40)
            metrics["low_sample"] = bool(metrics["n"] < 30)
            rows.append(metrics)
    return pd.DataFrame(rows)


def _numeric_medians(train: pd.DataFrame) -> dict:
    from src.features.schema import NUMERIC_FEATURES

    medians = {}
    for column in NUMERIC_FEATURES:
        numeric = pd.to_numeric(train[column], errors="coerce")
        medians[column] = float(numeric.median()) if numeric.notna().any() else 0.0
    return medians


def _importance_frame(bundle) -> pd.DataFrame:
    from src.features.schema import CATEGORICAL_FEATURES, NUMERIC_FEATURES

    names = CATEGORICAL_FEATURES + NUMERIC_FEATURES
    model = bundle.get("estimator")
    values = None
    method = None
    if bundle["kind"] == "catboost" and model is not None:
        values = model.get_feature_importance()
        method = "catboost_prediction_values_change"
    elif hasattr(model, "feature_importances_"):
        values = model.feature_importances_
        method = "split_gain_or_impurity"
    elif bundle["kind"] == "ridge" and model is not None:
        values = np.abs(model.coef_)
        names = [f"ridge_coef_{i}" for i in range(len(model.coef_))]
        method = "absolute_ridge_coefficient"
    if values is None:
        return pd.DataFrame(columns=["feature", "importance", "method"])
    size = min(len(names), len(values))
    frame = pd.DataFrame({"feature": names[:size], "importance": np.asarray(values)[:size], "method": method})
    frame["note"] = "Association with the model prediction, not a causal effect."
    return frame.sort_values("importance", ascending=False)


def _backtests(bundle, frame, levels, cfg) -> list[dict]:
    """Expanding-window refits with frozen hyperparameters. Not used for selection."""
    if bundle["kind"] in {"baseline", "ridge"} or bundle["strategy"] != "unified":
        return [{"status": "skipped", "reason": "Backtests refit the unified tree winner only."}] if bundle["strategy"] != "unified" or bundle["kind"] == "baseline" else _backtests_unified(bundle, frame, levels, cfg)
    return _backtests_unified(bundle, frame, levels, cfg)


def _backtests_unified(bundle, frame, levels, cfg) -> list[dict]:
    results = []
    if bundle["kind"] in {"baseline"}:
        return [{"status": "skipped", "reason": "Baseline has no hyperparameters to refit."}]
    for year in (2023, 2024, 2025):
        start = pd.Timestamp(f"{year}-01-01")
        end = pd.Timestamp(f"{year + 1}-01-01")
        train = frame.loc[frame["instance_date"] < start]
        holdout = frame.loc[(frame["instance_date"] >= start) & (frame["instance_date"] < end)]
        if len(train) < 20000 or len(holdout) < 5000:
            results.append({"year": year, "status": "skipped", "n_train": int(len(train)), "n_test": int(len(holdout))})
            continue
        daily = train.groupby("instance_date").size().sort_index().cumsum()
        cut = daily[daily >= 0.9 * int(daily.iloc[-1])].index[0]
        calib = train.loc[train["instance_date"] >= cut]
        fit_rows = train.loc[train["instance_date"] < cut]
        run = {
            "params": bundle.get("hyperparameters") or {},
            "trees": bundle.get("n_estimators") or 300,
            "ridge_payload": bundle.get("ridge_payload"),
            "rf_medians": bundle.get("rf_medians") or _numeric_medians(fit_rows),
        }
        model = _fit_estimator(bundle["kind"], run, fit_rows, fit_rows["actual_worth"].to_numpy(), levels, bundle["target_mode"])
        temp = _temp_bundle(bundle["kind"], run, model, levels, bundle["target_mode"])
        link_cal = predict_link(temp, calib)
        calibration = _precommit(link_cal, calib["actual_worth"].to_numpy(), bundle["target_mode"])
        link_test = predict_link(temp, holdout)
        from src.models.train import apply_calibration

        pred = apply_calibration(link_test, calibration, bundle["target_mode"])
        metrics = regression_metrics(holdout["actual_worth"], pred)
        q = fit_conformal(calib["actual_worth"], apply_calibration(link_cal, calibration, bundle["target_mode"]), calib["reg_type_en"], 0.9, 10**9)
        from src.models.intervals import prediction_bounds

        lower, upper = prediction_bounds(pred, q["q_global"])
        covered = (holdout["actual_worth"].to_numpy() >= lower) & (holdout["actual_worth"].to_numpy() <= upper)
        results.append(
            {
                "year": year,
                "status": "scored",
                "n_train": int(len(fit_rows)),
                "n_calibration": int(len(calib)),
                "n_test": int(len(holdout)),
                "metrics": metrics,
                "interval_coverage": float(np.mean(covered)),
                "note": "Frozen hyperparameters from the official run. This overlap with the official test is descriptive and was not used to select the model.",
            }
        )
    return results
