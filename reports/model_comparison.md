# Model comparison

Candidates are ranked by validation-selection MAE in AED after a precommitted median residual correction fit on the earlier validation slice. A raw-target or separate-segment model replaces the unified log model only if it reduces that MAE by more than 2%. The final calibration menu is searched only for the frozen winner. Conformal quantiles use the later validation slice. Test metrics are not used to choose the model.

Selected candidate: `hist_gradient_boosting_log_unified` (residential-sales-hist_gradient_boosting-log-unified). Validation-selection MAE: 309,190 AED.

Test metrics were computed after that choice. They did not choose the winner.

CatBoost's untouched-test MAE under the precommitted calibration is lower than the selected model's. The selection rule ranks validation MAE, so the deployed model was not replaced after the test scores were known.

The ridge `train_seconds` value records the scoring call that followed the fit, not the fit itself. The random-forest seconds include that model's fit.

| model | kind | target_mode | strategy | validation_mae_aed | validation_median_ae_aed | validation_within_20pct | test_mae_aed | test_rmse_aed | test_r2 | test_median_ae_aed | test_wape | test_median_ape | test_within_10pct | test_within_20pct | test_within_30pct | train_seconds | selected | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lightgbm_log_unified | lightgbm | log | unified | 347908 | 151790 | 0.771551 | 461250 | 2.05716e+06 | 0.753941 | 173465 | 0.207722 | 0.133539 | 0.39058 | 0.685465 | 0.852907 | 138.672 | False | Tuned on the inner training tail. Precommitted median log-shift calibration. |
| xgboost_log_unified | xgboost | log | unified | 394699 | 149404 | 0.744431 | 502710 | 2.09644e+06 | 0.744455 | 189034 | 0.226393 | 0.148583 | 0.344324 | 0.646738 | 0.82051 | 48.0883 | False | Tuned on the inner training tail. Precommitted median log-shift calibration. |
| catboost_log_unified | catboost | log | unified | 315103 | 128698 | 0.819737 | 379709 | 1.81389e+06 | 0.808697 | 143722 | 0.171 | 0.104948 | 0.480741 | 0.773201 | 0.905321 | 506.929 | False | Tuned on the inner training tail. Precommitted median log-shift calibration. |
| hist_gradient_boosting_log_unified | hist_gradient_boosting | log | unified | 309190 | 130867 | 0.821425 | 412017 | 2.23314e+06 | 0.710042 | 148030 | 0.18555 | 0.11012 | 0.459388 | 0.763223 | 0.898722 | 89.0115 | True | Tuned on the inner training tail. Precommitted median log-shift calibration. Categorical labels with more than 200 training levels are omitted because this algorithm caps cardinality at 255. Building and project price levels remain in the shrunk history features. |
| ridge_log_unified | ridge | log | unified | 549714 | 224046 | 0.599068 | 674314 | 4.59249e+06 | -0.226305 | 241513 | 0.303675 | 0.178737 | 0.302916 | 0.545632 | 0.733765 | 1.25001e-07 | False | Smoothed target encoding and one-hot low-cardinality fields, fit on training rows only. |
| random_forest_log_unified | random_forest | log | unified | 365350 | 151893 | 0.775992 | 459153 | 2.47514e+06 | 0.643793 | 158241 | 0.206778 | 0.119832 | 0.43173 | 0.716392 | 0.861465 | 23.3376 | False | Each tree draws max_samples training rows. Numeric missing values use training medians. |
| baseline_area_median_psm | baseline | raw | unified | 617743 | 265222 | 0.527983 | 664719 | 3.05006e+06 | 0.459099 | 235801 | 0.299354 | 0.173227 | 0.321135 | 0.55381 | 0.726346 | 0 | False | Leakage-safe prior median AED per sqm times size, with a median residual shift fit on val_fit. |
| baseline_area_type_median_psm | baseline | raw | unified | 613302 | 261246 | 0.532276 | 655502 | 2.89598e+06 | 0.512365 | 232073 | 0.295203 | 0.17283 | 0.320547 | 0.555132 | 0.728317 | 0 | False | Leakage-safe prior median AED per sqm times size, with a median residual shift fit on val_fit. |
| hist_gradient_boosting_raw_unified | hist_gradient_boosting | raw | unified | 361509 | 146955 | 0.773349 | 408434 | 2.04852e+06 | 0.756003 | 159825 | 0.183937 | 0.115193 | 0.440191 | 0.744858 | 0.881789 | 14.6134 | False | Same hyperparameters and tree count as the log model, trained on AED. |
| hist_gradient_boosting_log_by_reg_type | hist_gradient_boosting | log | by_reg_type | 326313 | 127441 | 0.823627 | 395721 | 2.04144e+06 | 0.757687 | 148109 | 0.178211 | 0.111055 | 0.457221 | 0.761448 | 0.896089 |  | False | Separate models by reg_type_en, same hyperparameters, precommitted median calibration. |
| hist_gradient_boosting_log_by_property_type | hist_gradient_boosting | log | by_property_type | 312115 | 124183 | 0.822966 | 396107 | 1.99637e+06 | 0.76827 | 148077 | 0.178385 | 0.113267 | 0.450353 | 0.759183 | 0.904599 |  | False | Separate models by property_type_en, same hyperparameters, precommitted median calibration. |
| hist_gradient_boosting_log_iqr_sensitivity | hist_gradient_boosting | log | unified_iqr_sensitivity | 309604 | 128705 | 0.830563 | 417959 | 2.33623e+06 | 0.682653 | 145448 | 0.188226 | 0.109745 | 0.461433 | 0.761693 | 0.899689 |  | False | Training rows outside a wide within-type MAD fence were removed. The same validation rows are scored. Not used for production. |

WAPE uses the sum of absolute actual prices as the denominator. Median absolute percentage error is the median of |error| / actual.

The IQR sensitivity row, when present, refits the chosen algorithm after dropping training rows outside a wide within-type MAD fence and scores the same validation rows. It is not the production training set.
