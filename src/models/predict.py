"""Shared prediction path for training, the API, and tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.models.intervals import apply_conformal
from src.models.train import (
    _matrix,
    _ordinal_matrix,
    _predict_link,
    _ridge_predict,
    apply_calibration,
)


def predict_link(bundle: dict, frame: pd.DataFrame, estimator=None) -> np.ndarray:
    kind = bundle["kind"]
    model = bundle["estimator"] if estimator is None else estimator
    if kind == "baseline":
        column = bundle["baseline_column"]
        psm = frame[column]
        if column != "area_prior_median_psm" and "area_prior_median_psm" in frame:
            psm = psm.fillna(frame["area_prior_median_psm"])
        psm = psm.fillna(bundle["global_median_psm"])
        return (psm.to_numpy(dtype=float) * frame["procedure_area"].to_numpy(dtype=float))
    if kind == "ridge":
        payload = getattr(model, "_ridge_payload", None) or bundle["ridge_payload"]
        return _ridge_predict(model, payload, frame)
    if kind == "random_forest":
        return model.predict(_ordinal_matrix(frame, bundle["levels"], bundle.get("rf_medians")))
    if kind == "hist_gradient_boosting":
        return _predict_link(kind, model, frame, bundle["levels"])
    return _predict_link(kind, model, frame, bundle["levels"])


def predict_aed(bundle: dict, frame: pd.DataFrame) -> np.ndarray:
    strategy = bundle.get("strategy", "unified")
    if strategy == "unified" or "segment_estimators" not in bundle:
        link = predict_link(bundle, frame)
        return apply_calibration(link, bundle["calibration"], bundle["target_mode"])

    predictions = np.full(len(frame), np.nan)
    column = bundle["segment_column"]
    labels = frame[column].astype(str)
    for label, estimator in bundle["segment_estimators"].items():
        mask = labels.eq(str(label)).to_numpy()
        if not mask.any():
            continue
        part = frame.loc[mask]
        link = predict_link(bundle, part, estimator=estimator)
        calibration = bundle["segment_calibrations"][str(label)]
        predictions[mask] = apply_calibration(link, calibration, bundle["target_mode"])
    missing = ~np.isfinite(predictions)
    if missing.any():
        link = predict_link(bundle, frame.loc[missing], estimator=bundle["fallback_estimator"])
        predictions[missing] = apply_calibration(link, bundle["fallback_calibration"], bundle["target_mode"])
    return predictions


def predict_interval(bundle: dict, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    point = predict_aed(bundle, frame)
    reg = frame["reg_type_en"] if "reg_type_en" in frame else pd.Series(["__MISSING__"] * len(frame))
    lower, upper, quantiles = apply_conformal(point, reg, bundle["conformal"])
    return point, lower, upper
