"""Phase 1 audit of the supplied transaction file. No rows are dropped here."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import write_json
from src.preprocessing.schema import ARABIC_COLUMNS, ENGLISH_PARALLEL, TEXT_COLUMNS


def load_raw(path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _financial_profile(series: pd.Series) -> dict:
    valid = series.dropna()
    if valid.empty:
        return {"non_null": 0}
    quantiles = valid.quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]).to_dict()
    return {
        "non_null": int(valid.shape[0]),
        "missing": int(series.isna().sum()),
        "min": float(valid.min()),
        "max": float(valid.max()),
        "mean": float(valid.mean()),
        "median": float(valid.median()),
        "zero": int((valid == 0).sum()),
        "negative": int((valid < 0).sum()),
        "quantiles": {str(k): float(v) for k, v in quantiles.items()},
    }


def meter_price_identity(df: pd.DataFrame) -> dict:
    area = df["procedure_area"].to_numpy(dtype=float)
    worth = df["actual_worth"].to_numpy(dtype=float)
    stated = df["meter_sale_price"].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        calculated = np.where(area != 0, worth / area, np.nan)
    abs_diff = np.abs(calculated - stated)
    rel = abs_diff / np.where(stated == 0, np.nan, np.abs(stated))
    return {
        "definition_tested": "meter_sale_price ?= actual_worth / procedure_area",
        "n_rows": int(len(df)),
        "n_zero_meter_sale_price": int((stated == 0).sum()),
        "n_zero_procedure_area": int((area == 0).sum()),
        "abs_diff_median": float(np.nanmedian(abs_diff)),
        "abs_diff_p99": float(np.nanpercentile(abs_diff, 99)),
        "abs_diff_max": float(np.nanmax(abs_diff)),
        "n_relative_diff_gt_0.1pct": int(np.nansum(rel > 0.001)),
        "n_relative_diff_gt_1pct": int(np.nansum(rel > 0.01)),
        "n_allclose_rtol_1e-3_atol_0.05": int(
            np.isclose(calculated, stated, rtol=1e-3, atol=0.05, equal_nan=False).sum()
        ),
        "conclusion": (
            "meter_sale_price matches actual_worth / procedure_area within rounding "
            "for virtually every row. It is a derived field, not an independent measurement. "
            "Using it as a feature to predict actual_worth would leak the target."
        ),
    }


def _arabic_redundancy(df: pd.DataFrame) -> dict:
    report = {}
    for arabic, english in ENGLISH_PARALLEL.items():
        if arabic not in df.columns or english not in df.columns:
            continue
        mapping = df.groupby(english, dropna=False)[arabic].nunique(dropna=False)
        reverse = df.groupby(arabic, dropna=False)[english].nunique(dropna=False)
        report[arabic] = {
            "english_column": english,
            "max_arabic_values_per_english": int(mapping.max()),
            "max_english_values_per_arabic": int(reverse.max()),
            "one_to_one": bool(mapping.max() == 1 and reverse.max() == 1),
        }
    return report


def _duplicate_report(df: pd.DataFrame) -> dict:
    exact = int(df.duplicated().sum())
    id_dup_rows = int(df["transaction_id"].duplicated().sum())
    conflict = {}
    for column in ("actual_worth", "procedure_area", "procedure_name_en", "instance_date", "area_name_en"):
        nunq = df.groupby("transaction_id")[column].nunique(dropna=False)
        conflict[column] = int((nunq > 1).sum())
    multiplicity = df.groupby("transaction_id").size()
    return {
        "n_rows": int(len(df)),
        "n_unique_transaction_id": int(df["transaction_id"].nunique()),
        "n_exact_duplicate_extra_rows": exact,
        "n_extra_rows_by_transaction_id": id_dup_rows,
        "ids_with_conflicting_values": conflict,
        "max_copies_of_one_id": int(multiplicity.max()),
        "conclusion": (
            "Extra rows are exact copies of the same transaction_id. "
            "Economic fields do not conflict inside an id. "
            "Deduplication keeps one copy and is recorded in the filter log."
            if exact == id_dup_rows and all(v == 0 for v in conflict.values())
            else "Duplicate transaction ids are not all exact copies. Inspect conflicting fields before deleting rows."
        ),
    }


def run_audit(df: pd.DataFrame, source_path: str, out_dir, report_dir) -> dict:
    out_dir = out_dir if hasattr(out_dir, "joinpath") else out_dir
    dates = pd.to_datetime(df["instance_date"], errors="coerce")
    memory_bytes = int(df.memory_usage(deep=True).sum())
    missing = pd.DataFrame(
        {
            "column": df.columns,
            "dtype": [str(t) for t in df.dtypes],
            "n_unique": [int(df[c].nunique(dropna=True)) for c in df.columns],
            "missing_count": [int(df[c].isna().sum()) for c in df.columns],
        }
    )
    missing["missing_pct"] = (missing["missing_count"] / len(df) * 100).round(6)
    missing = missing.sort_values(["missing_count", "column"], ascending=[False, True])
    missing.to_csv(out_dir / "missing_values.csv", index=False)

    dup = _duplicate_report(df)
    pd.DataFrame(
        [
            {"metric": key, "value": value}
            for key, value in dup.items()
            if key != "ids_with_conflicting_values"
        ]
        + [
            {"metric": f"conflicting_ids__{k}", "value": v}
            for k, v in dup["ids_with_conflicting_values"].items()
        ]
    ).to_csv(out_dir / "duplicate_analysis.csv", index=False)

    type_summary = (
        df.assign(_date=dates)
        .groupby(
            ["trans_group_en", "procedure_name_en", "reg_type_en", "property_usage_en", "property_type_en"],
            dropna=False,
        )
        .agg(
            n_rows=("transaction_id", "size"),
            n_unique_transaction_id=("transaction_id", "nunique"),
            total_actual_worth=("actual_worth", "sum"),
            median_actual_worth=("actual_worth", "median"),
            median_procedure_area=("procedure_area", "median"),
            median_meter_sale_price=("meter_sale_price", "median"),
        )
        .reset_index()
        .sort_values("n_rows", ascending=False)
    )
    type_summary.to_csv(out_dir / "transaction_type_summary.csv", index=False)

    usage_counts = df["property_usage_en"].value_counts(dropna=False).to_dict()
    year_counts = dates.dt.year.value_counts(dropna=False).sort_index()
    rent_mask = df["rent_value"].notna()
    rent_procedures = df.loc[rent_mask, "procedure_name_en"].value_counts(dropna=False).to_dict()
    rent_groups = df.loc[rent_mask, "trans_group_en"].value_counts(dropna=False).to_dict()

    whitespace = {}
    for column in TEXT_COLUMNS:
        if column not in df.columns:
            continue
        raw = df[column]
        as_text = raw.dropna().astype(str)
        stripped = as_text.str.strip().str.replace(r"\s+", " ", regex=True)
        whitespace[column] = {
            "n_non_null": int(raw.notna().sum()),
            "n_changed_by_whitespace_normalization": int((as_text.to_numpy() != stripped.to_numpy()).sum()),
            "n_unique_raw": int(raw.nunique(dropna=True)),
            "n_unique_normalized": int(stripped.nunique()),
        }

    area_id_counts = df.groupby("area_name_en")["area_id"].nunique()
    multi_id_areas = {
        str(name): {str(k): int(v) for k, v in df.loc[df["area_name_en"].eq(name), "area_id"].value_counts().items()}
        for name in area_id_counts[area_id_counts > 1].index
    }

    named = {}
    for label in ("Dubai Marina", "DownTown Dubai", "The Greens", "Al Furjan", "The Gardens"):
        mask = df["master_project_en"].eq(label)
        named[label] = {
            "n_rows": int(mask.sum()),
            "property_types": df.loc[mask, "property_type_en"].value_counts().to_dict() if mask.any() else {},
            "areas": df.loc[mask, "area_name_en"].value_counts().head(5).to_dict() if mask.any() else {},
            "usages": df.loc[mask, "property_usage_en"].value_counts().to_dict() if mask.any() else {},
        }

    identity = meter_price_identity(df)
    audit = {
        "source_path": source_path,
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "memory_bytes": memory_bytes,
        "memory_mebibytes": round(memory_bytes / (1024**2), 2),
        "columns": missing.to_dict(orient="records"),
        "date_min_parsed": None if dates.dropna().empty else str(dates.min().date()),
        "date_max_parsed": None if dates.dropna().empty else str(dates.max().date()),
        "n_unparsed_dates": int(dates.isna().sum()),
        "unparsed_date_examples": df.loc[dates.isna(), "instance_date"].astype(str).unique().tolist(),
        "rows_by_year": {str(int(k)) if pd.notna(k) else "unparsed": int(v) for k, v in year_counts.items()},
        "duplicates": dup,
        "trans_group_counts": df["trans_group_en"].value_counts().to_dict(),
        "reg_type_counts": df["reg_type_en"].value_counts().to_dict(),
        "property_type_counts": df["property_type_en"].value_counts().to_dict(),
        "property_usage_counts": {str(k): int(v) for k, v in usage_counts.items()},
        "procedure_counts": df["procedure_name_en"].value_counts().to_dict(),
        "rooms_counts": {str(k): int(v) for k, v in df["rooms_en"].value_counts(dropna=False).items()},
        "has_parking_counts": {str(k): int(v) for k, v in df["has_parking"].value_counts(dropna=False).items()},
        "financial_profiles": {
            column: _financial_profile(df[column])
            for column in ("procedure_area", "actual_worth", "meter_sale_price", "rent_value", "meter_rent_price")
        },
        "meter_sale_price_identity": identity,
        "units_interpretation": {
            "procedure_area": "square meters",
            "actual_worth": "AED",
            "meter_sale_price": "AED per square meter",
            "evidence": (
                "The file has no separate unit-of-measure column. "
                "meter_sale_price matches actual_worth / procedure_area, and the joint magnitudes "
                "(median area near a typical dwelling size, median worth in the low millions, "
                "median meter price in the thousands) are the Dubai Land Department convention of "
                "square meters and AED. This is an interpretation of the supplied fields, not a second measurement."
            ),
        },
        "target_assessment": {
            "candidate": "actual_worth",
            "suitable_for_arm_length_sale_model": False,
            "reason": (
                "actual_worth is populated for sales, mortgages, and gifts. "
                "On mortgages it is a financing amount. On gifts and grants it is not an arm's-length market price. "
                "It is an appropriate transaction-price target only after the eligibility policy restricts rows "
                "to residential dwelling sales. meter_sale_price is the same information divided by area."
            ),
        },
        "unavailable_at_prediction_time": [
            "actual_worth",
            "meter_sale_price",
            "rent_value",
            "meter_rent_price",
            "no_of_parties_role_1",
            "no_of_parties_role_2",
            "no_of_parties_role_3",
            "transaction_id",
            "procedure_id",
            "load_timestamp",
            "procedure_name_en",
            "trans_group_en",
            "asking price (not in the file; must not be used as a model input)",
        ],
        "leakage_columns_if_predicting_actual_worth": [
            "actual_worth",
            "meter_sale_price",
            "rent_value",
            "meter_rent_price",
        ],
        "arabic_parallel_columns": _arabic_redundancy(df),
        "whitespace_normalization": whitespace,
        "area_names_with_multiple_area_ids": multi_id_areas,
        "n_area_name": int(df["area_name_en"].nunique()),
        "n_building_name": int(df["building_name_en"].nunique(dropna=True)),
        "n_project_name": int(df["project_name_en"].nunique(dropna=True)),
        "n_master_project": int(df["master_project_en"].nunique(dropna=True)),
        "rental_fields": {
            "n_rent_value_non_null": int(rent_mask.sum()),
            "n_meter_rent_price_non_null": int(df["meter_rent_price"].notna().sum()),
            "trans_group_counts": {str(k): int(v) for k, v in rent_groups.items()},
            "procedure_counts": {str(k): int(v) for k, v in rent_procedures.items()},
            "note": (
                "Non-null rent fields sit on lease-to-own and related mortgage procedures, "
                "not on a general rental-contract population."
            ),
        },
        "named_master_projects_requested_by_product": named,
        "load_timestamp_unique_values": df["load_timestamp"].astype(str).unique().tolist()[:5],
        "n_load_timestamp_unique": int(df["load_timestamp"].nunique()),
    }
    write_json(out_dir / "dataset_audit.json", audit)
    # Also place the audit JSON at the analytics-facing interim path expected by the brief.
    write_json(report_dir / "dataset_audit.json", audit)
    return audit
