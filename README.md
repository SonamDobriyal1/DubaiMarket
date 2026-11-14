# Dubai Real Estate Intelligence

Statistical valuation and community analytics for Dubai residential sales. This is not a listing site and it does not produce investment recommendations.

The only source file used for measurement is `data/dld_transactions_extracted.csv`.

## What the pipeline does

1. Audits the extract, including duplicate transaction ids, missingness, and the identity `meter_sale_price ≈ actual_worth / procedure_area`.
2. Keeps one copy of each transaction id after checking that price, area, procedure, and date do not conflict.
3. Builds a primary valuation population of residential unit and villa sales (`Sell` and `Sell - Pre registration`) and records every exclusion in `data/interim/filter_log.csv`.
4. Engineers month-lagged community, building, and project statistics so a row never sees same-month or future sales.
5. Compares a median AED-per-sqm baseline, ridge regression, random forest, histogram gradient boosting, XGBoost, LightGBM, and CatBoost on a chronological validation slice.
6. Fits a split-conformal prediction interval on a later validation slice and scores an untouched final period once.
7. Serves estimates, comparables, and community metrics through FastAPI.

Asking price is compared with the estimate after prediction. It is not a model input. Rental yields are not estimated. Coordinates are not invented.

## Run

```bash
python3 -m src.preprocessing.preprocessing_pipeline
python3 - << 'PY'
from src.common import load_config, resolve
from src.features.build import build_modeling_table, save_modeling_table
import pandas as pd
cfg = load_config()
frame = pd.read_parquet(resolve("data/processed/residential_sales.parquet"))
built, meta = build_modeling_table(frame, cfg)
save_modeling_table(built, meta, resolve("data/processed"), resolve("models"))
PY
python3 -m src.analytics.run_analytics
python3 -m src.reporting.eda
python3 - << 'PY'
from src.common import load_config
from src.models.run_training import run_training
run_training(load_config())
PY
python3 -m src.reporting.write_reports
uvicorn api.main:app --reload
```

On macOS, LightGBM and XGBoost need `libomp` (`brew install libomp`).

## Layout

Processed sales, history tables, community metrics, the production model, and the written reports live under `data/`, `models/`, and `reports/`. Narrative conclusions are generated from those artifacts by `src/reporting/write_reports.py`.

## Tests

```bash
python3 -m pytest tests -q
```

## Interpretation

A valuation is a prediction of a registered residential transaction price, with an interval for that single transaction. It is not an appraisal, a listing, or a forecast that a sale will happen at the point estimate. Read `reports/methodology.md` and `reports/production_readiness.md` after the training step.
