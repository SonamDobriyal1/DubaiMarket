# Production readiness and limitations

The API serves the frozen model, leakage-safe history tables, and precomputed community metrics. It validates inputs, returns structured errors, caches the model in memory, and applies a simple per-IP rate limit.

Limitations:

- The file is a DLD transaction extract, not a listing database, and it ends on 2025-11-07. A later valuation date reuses the last observed history and is flagged stale. It does not forecast a 2026 price path.
- Off-plan pre-registration prices and existing resales are different economic events. The comparison includes separate models, and the deployed choice is the one that won the precommitted validation rule.
- Prediction intervals are for one transaction. Empirical test coverage is an average. It is not a guarantee for every community.
- Non-null rent fields are attached to lease-to-own and related mortgage procedures, not to a general set of rental contracts. They are not used to estimate market rent or yield. Sales rows carrying rent_value after deduplication: 0.
- Scores and classifications are not investment advice and are not statements that a property will sell at the estimate.
- Luxury sales below the inconsistency ceiling were retained. A sensitivity model that applies a wide MAD fence is reported and not automatically promoted.
- Duplicate transaction ids were exact copies. Arabic columns that were not one-to-one with English were kept.

Selected model `residential-sales-hist_gradient_boosting-log-unified` test MAE 414,756 AED, within 20% on 76.0% of the untouched test period.
