"""Point-prediction metrics in AED and on the log scale."""

from __future__ import annotations

import numpy as np


def regression_metrics(y_true, y_pred) -> dict:
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_pred, dtype=float)
    valid = np.isfinite(y) & np.isfinite(p)
    y = y[valid]
    p = p[valid]
    if len(y) == 0:
        return {"n": 0}
    error = p - y
    abs_error = np.abs(error)
    pct = abs_error / np.clip(np.abs(y), 1.0, None)
    ss_res = float(np.sum(error**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    log_y = np.log(np.clip(y, 1.0, None))
    log_p = np.log(np.clip(p, 1.0, None))
    return {
        "n": int(len(y)),
        "mae_aed": float(np.mean(abs_error)),
        "rmse_aed": float(np.sqrt(np.mean(error**2))),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else None,
        "median_absolute_error_aed": float(np.median(abs_error)),
        "wape": float(np.sum(abs_error) / np.sum(np.abs(y))),
        "wape_denominator": "sum of absolute actual worth in AED",
        "median_absolute_percentage_error": float(np.median(pct)),
        "within_10pct": float(np.mean(pct <= 0.10)),
        "within_20pct": float(np.mean(pct <= 0.20)),
        "within_30pct": float(np.mean(pct <= 0.30)),
        "mae_log": float(np.mean(np.abs(log_y - log_p))),
        "rmse_log": float(np.sqrt(np.mean((log_y - log_p) ** 2))),
    }
