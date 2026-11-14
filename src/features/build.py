"""Build the modeling table and the rare-category maps fit on training rows only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import MISSING, OTHER, write_json
from src.features.historical import add_market_history
from src.features.schema import (
    CATEGORICAL_FEATURES,
    FORBIDDEN_FEATURES,
    NUMERIC_FEATURES,
    SIZE_BAND_LABELS,
    SIZE_BANDS,
)


RARE_SOURCE = {
    "nearest_landmark_grouped": "nearest_landmark_en",
    "nearest_metro_grouped": "nearest_metro_en",
    "nearest_mall_grouped": "nearest_mall_en",
    "building_name_grouped": "building_name_en",
    "project_name_grouped": "project_name_en",
}


def assign_splits(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    ordered = df.sort_values(["instance_date", "transaction_id"]).copy()
    daily = ordered.groupby("instance_date").size().sort_index().cumsum()
    total = int(daily.iloc[-1])
    train_fraction = float(cfg["splits"]["train_fraction"])
    val_fraction = float(cfg["splits"]["val_fraction"])
    d_val = daily[daily >= train_fraction * total].index[0]
    d_test = daily[daily >= (train_fraction + val_fraction) * total].index[0]
    if d_test <= d_val:
        later = daily.index[daily.index > d_val]
        if len(later) == 0:
            raise RuntimeError("Not enough distinct dates to form a validation and test window.")
        d_test = later[0]

    val_mask = (ordered["instance_date"] >= d_val) & (ordered["instance_date"] < d_test)
    val_daily = ordered.loc[val_mask].groupby("instance_date").size().sort_index().cumsum()
    if val_daily.empty:
        raise RuntimeError("Validation window is empty.")
    vtotal = int(val_daily.iloc[-1])
    d_sel = _advance(val_daily, vtotal / 3, None)
    d_conf = _advance(val_daily, 2 * vtotal / 3, d_sel)

    dates = ordered["instance_date"]
    split = np.full(len(ordered), "train", dtype=object)
    split[(dates >= d_val) & (dates < d_sel)] = "val_fit"
    split[(dates >= d_sel) & (dates < d_conf)] = "val_sel"
    split[(dates >= d_conf) & (dates < d_test)] = "val_conf"
    split[dates >= d_test] = "test"
    # Dates in [d_val, d_test) that missed a slice because boundaries collapsed go to val_conf.
    in_val = (dates >= d_val) & (dates < d_test)
    split[in_val & ~np.isin(split, ["val_fit", "val_sel", "val_conf"])] = "val_conf"
    ordered["split"] = split
    ordered["split_family"] = ordered["split"].map(
        {"train": "train", "val_fit": "validation", "val_sel": "validation", "val_conf": "validation", "test": "test"}
    )

    train = ordered.loc[ordered["split"].eq("train")]
    train_daily = train.groupby("instance_date").size().sort_index().cumsum()
    tail_fraction = float(cfg["training"]["inner_tail_fraction"])
    d_tail = train_daily[train_daily >= (1 - tail_fraction) * int(train_daily.iloc[-1])].index[0]
    boundaries = {
        "validation_start": str(pd.Timestamp(d_val).date()),
        "validation_selection_start": str(pd.Timestamp(d_sel).date()),
        "validation_conformal_start": str(pd.Timestamp(d_conf).date()),
        "test_start": str(pd.Timestamp(d_test).date()),
        "train_inner_tail_start": str(pd.Timestamp(d_tail).date()),
        "counts": ordered["split"].value_counts().to_dict(),
        "rule": (
            "Rows are assigned by instance_date. A boundary date belongs entirely to the later slice. "
            "Hyperparameters use only the training period, with early stopping on the inner training tail. "
            "Calibration is fit on val_fit and chosen on val_sel. Conformal scores use val_conf. "
            "The test period is not used to fit, stop, calibrate, or select."
        ),
    }
    return ordered, boundaries


def _advance(cumulative: pd.Series, target: float, previous) -> pd.Timestamp:
    hit = cumulative[cumulative >= target]
    candidate = pd.Timestamp(hit.index[0])
    if previous is not None and candidate <= pd.Timestamp(previous):
        later = cumulative.index[cumulative.index > pd.Timestamp(previous)]
        if len(later):
            return pd.Timestamp(later[0])
    return candidate


def fit_rare_maps(train: pd.DataFrame, min_counts: dict) -> dict:
    source_to_grouped = {source: grouped for grouped, source in RARE_SOURCE.items()}
    maps = {}
    for key, min_count in min_counts.items():
        grouped_col = key if key in RARE_SOURCE else source_to_grouped[key]
        source = RARE_SOURCE[grouped_col]
        counts = train[source].dropna().astype(str).value_counts()
        maps[grouped_col] = sorted(counts[counts >= int(min_count)].index.tolist())
    return maps


def apply_category_levels(df: pd.DataFrame, rare_maps: dict) -> pd.DataFrame:
    out = df.copy()
    plain = [
        "area_name_en",
        "master_project_en",
        "property_type_en",
        "property_sub_type_en",
        "reg_type_en",
    ]
    for column in plain:
        out[column] = out[column].map(lambda v: MISSING if pd.isna(v) or str(v).strip() == "" else str(v))
    for grouped_col, keep in rare_maps.items():
        source = RARE_SOURCE[grouped_col]
        keep_set = set(keep)
        source_values = out[source]

        def _map(value, allowed=keep_set):
            if pd.isna(value) or str(value).strip() == "":
                return MISSING
            text = str(value)
            return text if text in allowed else OTHER

        out[grouped_col] = source_values.map(_map)
    return out


def build_modeling_table(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    frame = df.copy()
    frame["log_procedure_area"] = np.log(frame["procedure_area"].where(frame["procedure_area"].gt(0)))
    frame["is_studio"] = np.where(frame["bedroom_count"].isna(), np.nan, (frame["bedroom_count"] == 0).astype(float))
    frame["is_penthouse"] = frame["is_penthouse"].astype(float)
    frame["size_band"] = pd.cut(
        frame["procedure_area"],
        bins=SIZE_BANDS,
        labels=SIZE_BAND_LABELS,
        right=False,
    ).astype(str)
    frame, history_tables = add_market_history(
        frame,
        min_growth_n=int(cfg["history"]["min_growth_n"]),
        shrinkage_k=float(cfg["history"]["shrinkage_k"]),
    )
    frame.attrs["history_tables"] = history_tables
    frame, boundaries = assign_splits(frame, cfg)
    rare_maps = fit_rare_maps(frame.loc[frame["split"].eq("train")], cfg["training"]["rare_min_count"])
    frame = apply_category_levels(frame, rare_maps)
    leaked = [column for column in FORBIDDEN_FEATURES if column in CATEGORICAL_FEATURES or column in NUMERIC_FEATURES]
    if leaked:
        raise RuntimeError(f"Forbidden columns entered the feature contract: {leaked}")
    meta = {
        "categorical_features": CATEGORICAL_FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "forbidden_features": FORBIDDEN_FEATURES,
        "target": "actual_worth",
        "rare_maps": rare_maps,
        "splits": boundaries,
        "history_rule": (
            "Community, building, project, property-type, and bedroom statistics are computed "
            "from earlier calendar months only. The current month is excluded. "
            "Rare building, project, landmark, metro, and mall labels are grouped using training-period "
            "frequencies only. Unseen labels become __OTHER__. Missing labels stay __MISSING__."
        ),
        "n_rows": int(len(frame)),
    }
    return frame, meta


def save_modeling_table(frame: pd.DataFrame, meta: dict, processed_dir, model_dir) -> None:
    history_dir = processed_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    history_tables = frame.attrs.pop("history_tables", {})
    for name, table in history_tables.items():
        table.to_parquet(history_dir / f"{name}.parquet", index=False)
    keep = [
        "transaction_id",
        "instance_date",
        "actual_worth",
        "price_per_sqm",
        "procedure_area",
        "property_type_en",
        "property_sub_type_en",
        "reg_type_en",
        "area_name_en",
        "master_project_en",
        "building_name_en",
        "project_name_en",
        "rooms_en",
        "bedroom_count",
        "bedroom_parse_status",
        "size_band",
        "split",
        "split_family",
        "eligibility_tier",
    ] + CATEGORICAL_FEATURES + NUMERIC_FEATURES
    # Categorical feature names overlap the display columns. Preserve one copy.
    keep = list(dict.fromkeys([c for c in keep if c in frame.columns]))
    path = processed_dir / "modeling_table.parquet"
    output = frame[keep].copy()
    output.attrs = {}
    output.to_parquet(path, index=False)
    write_json(model_dir / "feature_metadata.json", meta)
    write_json(processed_dir / "feature_metadata.json", meta)
