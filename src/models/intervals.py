"""Split conformal intervals for an individual transaction price.

The interval is not a confidence interval for a population mean, and a nominal
90% level is not a guarantee for every community.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def conformal_quantile(y_true, y_pred, nominal: float = 0.90) -> float:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    valid = np.isfinite(y) & np.isfinite(p) & (p > 0)
    scores = np.abs(y[valid] - p[valid]) / p[valid]
    n = int(scores.size)
    if n == 0:
        return 1.0
    level = min(1.0, np.ceil((n + 1) * nominal) / n)
    return float(np.quantile(scores, level, method="higher"))


def prediction_bounds(y_pred, quantile: float) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(y_pred, dtype=float)
    q = float(max(quantile, 0.0))
    lower = np.maximum(p * (1.0 - q), 0.0)
    upper = p * (1.0 + q)
    return lower, upper


def fit_conformal(y_true, y_pred, reg_type, nominal: float, min_segment_n: int) -> dict:
    global_q = conformal_quantile(y_true, y_pred, nominal)
    by_type = {}
    reg = pd.Series(reg_type).astype(str).to_numpy()
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    for label in sorted(set(reg)):
        mask = reg == label
        if int(mask.sum()) >= min_segment_n:
            by_type[label] = conformal_quantile(y[mask], p[mask], nominal)
    return {
        "nominal_coverage": nominal,
        "score": "absolute percentage residual |y-pred|/pred",
        "interval_form": "pred * (1 ± q), lower bound truncated at 0",
        "q_global": global_q,
        "q_by_reg_type": by_type,
        "segment_rule": (
            "Separate existing and off-plan quantiles are used when each calibration "
            f"segment has at least {min_segment_n} rows. Otherwise the global quantile is used. "
            "This is a prediction interval for one property's potential transaction price."
        ),
    }


def apply_conformal(y_pred, reg_type, conformal: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p = np.asarray(y_pred, dtype=float)
    reg = pd.Series(reg_type).astype(str).fillna("__MISSING__").to_numpy()
    quantiles = np.full(len(p), float(conformal["q_global"]))
    for label, q in conformal.get("q_by_reg_type", {}).items():
        quantiles[reg == str(label)] = float(q)
    lower, upper = prediction_bounds(p, 0.0)
    lower = np.maximum(p * (1.0 - quantiles), 0.0)
    upper = p * (1.0 + quantiles)
    # Rows with a non-positive prediction cannot support a multiplicative interval.
    bad = ~np.isfinite(p) | (p <= 0)
    lower[bad] = np.nan
    upper[bad] = np.nan
    return lower, upper, quantiles


def coverage_report(y_true, lower, upper, groups: dict[str, np.ndarray] | None = None, y_pred=None) -> dict:
    y = np.asarray(y_true, dtype=float)
    lo = np.asarray(lower, dtype=float)
    hi = np.asarray(upper, dtype=float)
    pred = None if y_pred is None else np.asarray(y_pred, dtype=float)
    valid = np.isfinite(y) & np.isfinite(lo) & np.isfinite(hi)
    covered = (y >= lo) & (y <= hi)
    width = hi - lo

    def _block(mask):
        mask = mask & valid
        n = int(mask.sum())
        if n == 0:
            return {"n": 0}
        relative = None
        if pred is not None:
            ratio = width[mask] / np.maximum(pred[mask], 1.0)
            ratio = ratio[np.isfinite(ratio)]
            if ratio.size:
                relative = float(np.median(ratio))
        return {
            "n": n,
            "empirical_coverage": float(np.mean(covered[mask])),
            "mean_width_aed": float(np.mean(width[mask])),
            "median_width_aed": float(np.median(width[mask])),
            "median_width_over_predicted": relative,
        }

    report = {"overall": _block(np.ones(len(y), dtype=bool))}
    if groups:
        report["segments"] = {}
        for name, labels in groups.items():
            labels = np.asarray(labels).astype(str)
            report["segments"][name] = {}
            for label in sorted(set(labels)):
                report["segments"][name][label] = _block(labels == label)
    return report
