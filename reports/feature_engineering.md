# Feature engineering

Community, building, project, property-type, and bedroom statistics are computed from earlier calendar months only. The current month is excluded. Rare building, project, landmark, metro, and mall labels are grouped using training-period frequencies only. Unseen labels become __OTHER__. Missing labels stay __MISSING__.

Categorical features: area_name_en, master_project_en, property_type_en, property_sub_type_en, reg_type_en, nearest_landmark_grouped, nearest_metro_grouped, nearest_mall_grouped, building_name_grouped, project_name_grouped.

Numeric features: bedroom_count, bedroom_missing, is_penthouse, is_studio, procedure_area, log_procedure_area, has_parking, parking_missing, transaction_year, transaction_month, transaction_quarter, months_since_2000, month_sin, month_cos, area_prior_median_psm, area_prior_count, area_prior_dispersion, area_trail12_count, area_trail12_median_psm, area_qoq_growth, area_type_prior_median_psm, area_bed_prior_median_psm, master_prior_median_psm, master_prior_count, building_prior_shrunk_psm, building_prior_count, project_prior_shrunk_psm, project_prior_count.

Forbidden inputs, which are not in either list: actual_worth, meter_sale_price, price_per_sqm, psm_recalculated, rent_value, meter_rent_price, no_of_parties_role_1, no_of_parties_role_2, no_of_parties_role_3, asking_price, transaction_id, procedure_id, procedure_name_en, load_timestamp.

Rows are assigned by instance_date. A boundary date belongs entirely to the later slice. Hyperparameters use only the training period, with early stopping on the inner training tail. Calibration is fit on val_fit and chosen on val_sel. Conformal scores use val_conf. The test period is not used to fit, stop, calibrate, or select.

Split counts: {"train": 380204, "test": 81676, "val_conf": 27436, "val_sel": 27249, "val_fit": 26627}.

Validation starts 2024-04-16. Selection slice starts 2024-07-29. Conformal slice starts 2024-10-24. Test starts 2025-02-12. Inner training tail starts 2023-09-22.

Building and project history is shrunk toward the official-area median. The shrinkage weight is n/(n+10). A level with no prior sales stays missing. Trees keep missing numeric values. The linear model and the random forest use training-set medians plus, for the linear model, smoothed target encodings fit on training rows only.

Same-month sales are not visible to a row. A valuation in month M uses the latest history month strictly before M.
