# Methodology

Source file: `/Users/sonamdobriyal/Test/DubaiMarket/data/dld_transactions_extracted.csv` with 1,593,464 rows, 1,001,280 after exact-id deduplication, and 543,192 primary residential sales from 1993-01-27 to 2025-11-07.

The model predicts `actual_worth` for a residential unit or villa sale. Asking price is applied only after prediction, to compute the gap and the interval-based classification.

Community, building, project, property-type, and bedroom statistics are computed from earlier calendar months only. The current month is excluded. Rare building, project, landmark, metro, and mall labels are grouped using training-period frequencies only. Unseen labels become __OTHER__. Missing labels stay __MISSING__.

Candidates are ranked by validation-selection MAE in AED after a precommitted median residual correction fit on the earlier validation slice. A raw-target or separate-segment model replaces the unified log model only if it reduces that MAE by more than 2%. The final calibration menu is searched only for the frozen winner. Conformal quantiles use the later validation slice. Test metrics are not used to choose the model.

Deployed model: residential-sales-hist_gradient_boosting-log-unified. Test MAE: 414,756 AED.

Non-null rent fields are attached to lease-to-own and related mortgage procedures, not to a general set of rental contracts. They are not used to estimate market rent or yield. Sales rows carrying rent_value after deduplication: 0.

No coordinates were created. Map payloads leave latitude, longitude, and geometry null unless an external GeoJSON is joined by name.
