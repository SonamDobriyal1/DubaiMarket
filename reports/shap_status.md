# SHAP

Computed on a 200-row sample of the untouched test period for `residential-sales-hist_gradient_boosting-log-unified`.

Mean absolute SHAP values describe how the fitted model uses features for these predictions. They are not causal effects.
For the deployed log-price model they are on the natural-log price scale, not in AED.

Top features: procedure_area (0.4625), bedroom_count (0.1128), area_trail12_median_psm (0.1024), master_project_en (0.1018).
