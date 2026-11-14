# Model evaluation

Test rows: 81,676. Train rows: 380,204.

Test MAE 414,756 AED, RMSE 2,242,270 AED, R² 0.708, median absolute error 148,402 AED.

WAPE 0.187 (denominator: sum of absolute actual worth in AED). Median absolute percentage error 0.111.

Share of test predictions within 10% / 20% / 30%: 45.7% / 76.0% / 89.9%.

Log-price MAE 0.158, RMSE 0.252.

Segment metrics, including communities and price bands with at least 30 test sales and a within-20% rate under 40%, are flagged `unreliable` in `data/analytics/segment_metrics.csv`. Segments under 30 sales are `low_sample` rather than labeled unreliable.

Feature importance is an association between a feature and the model's prediction. It is not a causal effect of changing that feature.

Backtests:

[
  {
    "year": 2023,
    "status": "scored",
    "n_train": 268185,
    "n_calibration": 29926,
    "n_test": 61970,
    "metrics": {
      "n": 61970,
      "mae_aed": 527885.050424448,
      "rmse_aed": 2423762.412423559,
      "r2": 0.7038948101883276,
      "median_absolute_error_aed": 166620.95584275387,
      "wape": 0.2293774020549731,
      "wape_denominator": "sum of absolute actual worth in AED",
      "median_absolute_percentage_error": 0.13418355663773063,
      "within_10pct": 0.38307245441342586,
      "within_20pct": 0.6786993706632242,
      "within_30pct": 0.8504921736324028,
      "mae_log": 0.18877056613893015,
      "rmse_log": 0.2682989691191313
    },
    "interval_coverage": 0.7961594319832177,
    "note": "Frozen hyperparameters from the official run. This overlap with the official test is descriptive and was not used to select the model."
  },
  {
    "year": 2024,
    "status": "scored",
    "n_train": 323874,
    "n_calibration": 36207,
    "n_test": 91925,
    "metrics": {
      "n": 91925,
      "mae_aed": 406760.24682185624,
      "rmse_aed": 1442677.3202376394,
      "r2": 0.8326234423638287,
      "median_absolute_error_aed": 167230.21652185207,
      "wape": 0.18763576731660125,
      "wape_denominator": "sum of absolute actual worth in AED",
      "median_absolute_percentage_error": 0.12518146497097432,
      "within_10pct": 0.410345390263802,
      "within_20pct": 0.7171933641555616,
      "within_30pct": 0.888245852597226,
      "mae_log": 0.16710891003680126,
      "rmse_log": 0.23967712413540437
    },
    "interval_coverage": 0.8378787054664129,
    "note": "Frozen hyperparameters from the official run. This overlap with the official test is descriptive and was not used to select the model."
  },
  {
    "year": 2025,
    "status": "scored",
    "n_train": 406493,
    "n_calibration": 45513,
    "n_test": 91186,
    "metrics": {
      "n": 91186,
      "mae_aed": 391346.46094705246,
      "rmse_aed": 2142542.9620026387,
      "r2": 0.725966159678819,
      "median_absolute_error_aed": 136063.13706552115,
      "wape": 0.17585252670012272,
      "wape_denominator": "sum of absolute actual worth in AED",
      "median_absolute_percentage_error": 0.1019958022828081,
      "within_10pct": 0.4925098151031957,
      "within_20pct": 0.7918101462943873,
      "within_30pct": 0.9116202048560086,
      "mae_log": 0.1468821867774078,
      "rmse_log": 0.2412248440842367
    },
    "interval_coverage": 0.8438795429122892,
    "note": "Frozen hyperparameters from the official run. This overlap with the official test is descriptive and was not used to select the model."
  }
]

IQR sensitivity:

{
  "rows_removed": 166,
  "rows_remaining": 380038,
  "by_property_type": [
    {
      "property_type": "Unit",
      "rows_removed": 119,
      "lower_psm": -65674.91185517173,
      "upper_psm": 90520.96397496946,
      "removed_psm_min": 90613.68549535499,
      "removed_psm_max": 161236.23153305886
    },
    {
      "property_type": "Villa",
      "rows_removed": 47,
      "lower_psm": -39531.06515081543,
      "upper_psm": 54651.32441007469,
      "removed_psm_min": 54664.33992809537,
      "removed_psm_max": 105024.71169686985
    }
  ],
  "validation_mae_aed": 309604.26449365827,
  "production_uses_iqr_filter": false,
  "reason": "The MAD fence changes which high and low prices the model sees. It is reported as a sensitivity check and is not the production training set, because a lower error can come from deleting legitimate tail transactions."
}
