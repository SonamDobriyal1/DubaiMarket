"""Reusable preprocessing entry point.

Reads the supplied CSV, writes the audit, and saves:
- cleaned_transactions.parquet: deduplicated full transaction file with flags
- residential_sales.parquet: primary residential dwelling sales after domain screens
- residential_sales_extended.parquet: primary sales plus qualifying delayed sales
"""

from __future__ import annotations

import pandas as pd

from src.common import ensure_dirs, load_config, resolve, write_json
from src.preprocessing.audit import load_raw, run_audit
from src.preprocessing.clean import prepare_transactions


def run_preprocessing(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    ensure_dirs(cfg)
    interim = resolve(cfg["paths"]["interim"])
    processed = resolve(cfg["paths"]["processed"])
    reports = resolve(cfg["paths"]["reports"])
    raw_path = resolve(cfg["data"]["raw_csv"])

    frame = load_raw(raw_path)
    audit = run_audit(frame, str(raw_path), interim, reports)
    cleaned, primary, extended, log, meta = prepare_transactions(frame, cfg)
    del frame

    filter_path = interim / "filter_log.csv"
    log.frame().to_csv(filter_path, index=False)
    cleaned_path = processed / "cleaned_transactions.parquet"
    primary_path = processed / "residential_sales.parquet"
    extended_path = processed / "residential_sales_extended.parquet"
    cleaned.to_parquet(cleaned_path, index=False)
    primary.to_parquet(primary_path, index=False)
    extended.to_parquet(extended_path, index=False)

    summary = {
        "raw_rows": audit["n_rows"],
        "raw_columns": audit["n_columns"],
        "cleaned_rows": int(len(cleaned)),
        "primary_rows": int(len(primary)),
        "extended_rows": int(len(extended)),
        "date_min_primary": None if primary.empty else str(primary["instance_date"].min().date()),
        "date_max_primary": None if primary.empty else str(primary["instance_date"].max().date()),
        "outputs": {
            "cleaned_transactions": str(cleaned_path),
            "residential_sales": str(primary_path),
            "residential_sales_extended": str(extended_path),
            "filter_log": str(filter_path),
            "dataset_audit": str(reports / "dataset_audit.json"),
        },
        "meta": meta,
        "audit_highlights": {
            "unique_transaction_ids": audit["duplicates"]["n_unique_transaction_id"],
            "exact_duplicate_extra_rows": audit["duplicates"]["n_exact_duplicate_extra_rows"],
            "meter_identity": audit["meter_sale_price_identity"],
            "rent_non_null": audit["rental_fields"]["n_rent_value_non_null"],
            "named_master_projects": audit["named_master_projects_requested_by_product"],
        },
    }
    write_json(interim / "preprocessing_summary.json", summary)
    return summary


if __name__ == "__main__":
    result = run_preprocessing()
    print(pd.Series({k: result[k] for k in ("raw_rows", "cleaned_rows", "primary_rows", "extended_rows")}))
