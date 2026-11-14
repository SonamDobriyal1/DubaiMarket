"""Month-lagged market statistics.

Every statistic stored on month m includes transactions in month m.
A prediction dated in month M is joined to the latest stored month strictly
before M, so same-month and future sales are excluded.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

METRIC_SUFFIXES = [
    "prior_median_psm",
    "prior_count",
    "prior_dispersion",
    "trail12_count",
    "trail12_median_psm",
    "qoq_growth",
    "recent3_count",
    "recent3_median_psm",
]


def _month_end_table(df: pd.DataFrame, group_col: str, prefix: str, min_growth_n: int) -> pd.DataFrame:
    work = df.loc[df[group_col].notna(), [group_col, "year_month_index", "price_per_sqm"]].dropna()
    if work.empty:
        return pd.DataFrame(columns=[group_col, "year_month_index"])
    work["year_month_index"] = work["year_month_index"].astype(np.int32)
    rows: list[dict] = []
    for key, group in work.groupby(group_col, sort=False):
        group = group.sort_values("year_month_index")
        yms = group["year_month_index"].to_numpy(dtype=np.int32)
        vals = group["price_per_sqm"].to_numpy(dtype=np.float64)
        ends = np.r_[np.flatnonzero(np.diff(yms)) + 1, len(yms)]
        for end in ends:
            ym = int(yms[end - 1])
            window = vals[:end]
            y_window = yms[:end]
            median = float(np.median(window))
            mad = float(np.median(np.abs(window - median)))
            recent = window[np.searchsorted(y_window, ym - 2) :]
            previous = window[np.searchsorted(y_window, ym - 5) : np.searchsorted(y_window, ym - 2)]
            trail = window[np.searchsorted(y_window, ym - 11) :]
            qoq = np.nan
            if len(recent) >= min_growth_n and len(previous) >= min_growth_n:
                previous_median = float(np.median(previous))
                if previous_median > 0:
                    qoq = float(np.median(recent) / previous_median - 1.0)
            rows.append(
                {
                    group_col: key,
                    "year_month_index": ym,
                    f"{prefix}_prior_median_psm": median,
                    f"{prefix}_prior_count": int(end),
                    f"{prefix}_prior_dispersion": float(mad / median) if median > 0 else np.nan,
                    f"{prefix}_trail12_count": int(len(trail)),
                    f"{prefix}_trail12_median_psm": float(np.median(trail)) if len(trail) else np.nan,
                    f"{prefix}_qoq_growth": qoq,
                    f"{prefix}_recent3_count": int(len(recent)),
                    f"{prefix}_recent3_median_psm": float(np.median(recent)) if len(recent) else np.nan,
                }
            )
    table = pd.DataFrame(rows)
    table = table.drop_duplicates([group_col, "year_month_index"], keep="last")
    return table.sort_values("year_month_index")


def _feature_names(prefix: str, columns: list[str] | None) -> list[str]:
    if columns is not None:
        return columns
    return [f"{prefix}_{suffix}" for suffix in METRIC_SUFFIXES]


def attach_prior_history(
    df: pd.DataFrame,
    table: pd.DataFrame,
    group_col: str,
    prefix: str,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Attach history available strictly before each row's transaction month."""
    feature_names = _feature_names(prefix, columns)
    out = df.copy()
    out["_join_month"] = out["year_month_index"] - 1
    for name in feature_names:
        out[name] = np.nan
    usable = out[group_col].notna() & out["_join_month"].notna()
    merged = out.loc[usable, ["transaction_id", group_col, "_join_month"]].copy()
    merged[group_col] = merged[group_col].astype(str)
    merged["_join_month"] = merged["_join_month"].astype("int64")
    merged = merged.sort_values("_join_month")
    if table.empty or merged.empty:
        return out.drop(columns=["_join_month"])
    right = table.copy()
    right[group_col] = right[group_col].astype(str)
    right["year_month_index"] = right["year_month_index"].astype("int64")
    right = right.sort_values("year_month_index")
    attached = pd.merge_asof(
        merged,
        right,
        left_on="_join_month",
        right_on="year_month_index",
        by=group_col,
        direction="backward",
    )
    present = [name for name in feature_names if name in attached.columns]
    attached = attached[["transaction_id"] + present].drop_duplicates("transaction_id", keep="last")
    out = out.drop(columns=["_join_month"] + present).merge(attached, on="transaction_id", how="left")
    return out


def add_market_history(df: pd.DataFrame, min_growth_n: int, shrinkage_k: float) -> tuple[pd.DataFrame, dict]:
    frame = df.copy()
    frame["area_type_key"] = np.where(
        frame["area_name_en"].notna() & frame["property_type_en"].notna(),
        frame["area_name_en"].astype(str) + "||" + frame["property_type_en"].astype(str),
        np.nan,
    )
    bed_label = np.where(frame["bedroom_count"].isna(), "missing", frame["bedroom_count"].astype("Int64").astype(str))
    frame["area_bed_key"] = np.where(
        frame["area_name_en"].notna(),
        frame["area_name_en"].astype(str) + "||" + pd.Series(bed_label, index=frame.index).astype(str),
        np.nan,
    )
    frame["building_key"] = np.where(
        frame["area_name_en"].notna() & frame["building_name_en"].notna(),
        frame["area_name_en"].astype(str) + "||" + frame["building_name_en"].astype(str),
        np.nan,
    )
    frame["project_key"] = np.where(
        frame["area_name_en"].notna() & frame["project_name_en"].notna(),
        frame["area_name_en"].astype(str) + "||" + frame["project_name_en"].astype(str),
        np.nan,
    )

    specs = [
        ("area", "area_name_en", None),
        ("master", "master_project_en", ["master_prior_median_psm", "master_prior_count", "master_qoq_growth", "master_trail12_count"]),
        ("area_type", "area_type_key", ["area_type_prior_median_psm", "area_type_prior_count"]),
        ("area_bed", "area_bed_key", ["area_bed_prior_median_psm", "area_bed_prior_count"]),
        ("building", "building_key", ["building_prior_median_psm", "building_prior_count"]),
        ("project", "project_key", ["project_prior_median_psm", "project_prior_count"]),
    ]
    tables = {}
    for prefix, column, columns in specs:
        started = time.perf_counter()
        table = _month_end_table(frame, column, prefix, min_growth_n)
        print(f"history {prefix}: {len(table)} rows in {time.perf_counter() - started:.1f}s", flush=True)
        if columns:
            table = table[[column, "year_month_index"] + [c for c in columns if c in table.columns]]
        tables[prefix] = table
        frame = attach_prior_history(frame, table, column, prefix, columns)

    frame = _shrink(frame, "building", shrinkage_k)
    frame = _shrink(frame, "project", shrinkage_k)
    return frame, tables


def _shrink(frame: pd.DataFrame, prefix: str, k: float) -> pd.DataFrame:
    count = frame[f"{prefix}_prior_count"]
    level = frame[f"{prefix}_prior_median_psm"]
    area_level = frame["area_prior_median_psm"]
    weight = count / (count + k)
    shrunk = weight * level + (1.0 - weight) * area_level
    shrunk = shrunk.where(count.gt(0) & level.notna())
    no_area = shrunk.isna() & count.ge(5) & level.notna()
    frame[f"{prefix}_prior_shrunk_psm"] = shrunk.where(~no_area, level)
    return frame
