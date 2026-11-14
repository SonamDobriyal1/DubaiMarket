"""Chronological model comparison.

Hyperparameters, calibration, and the production choice use training and
validation slices only. Test labels are scored after that choice is frozen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge

from src.features.schema import CATEGORICAL_FEATURES, NUMERIC_FEATURES
from src.models.metrics import regression_metrics

try:
    import lightgbm as lgb
except Exception:  # pragma: no cover
    lgb = None
try:
    import xgboost as xgb
except Exception:  # pragma: no cover
    xgb = None
try:
    from catboost import CatBoostRegressor, Pool
except Exception:  # pragma: no cover
    CatBoostRegressor = None
    Pool = None
try:
    import optuna
except Exception:  # pragma: no cover
    optuna = None


@dataclass
class Candidate:
    name: str
    kind: str
    target_mode: str
    estimator: object
    calibration: dict
    metrics_val_sel: dict
    metrics_test: dict | None = None
    train_seconds: float = 0.0
    hyperparameters: dict = field(default_factory=dict)
    n_estimators: int | None = None
    notes: str = ""
    segment: str = "unified"


def load_model_frame(path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["instance_date"] = pd.to_datetime(frame["instance_date"])
    return frame


def category_levels(train: pd.DataFrame) -> dict[str, list[str]]:
    levels = {}
    for column in CATEGORICAL_FEATURES:
        values = set(train[column].astype(str))
        values.update({"__MISSING__", "__OTHER__"})
        levels[column] = sorted(values)
    return levels


def tree_matrix(df: pd.DataFrame, levels: dict[str, list[str]], library: str) -> pd.DataFrame:
    matrix = pd.DataFrame(index=df.index)
    for column in CATEGORICAL_FEATURES:
        values = df[column].astype(str)
        if library == "catboost":
            matrix[column] = values
        else:
            matrix[column] = pd.Categorical(values, categories=levels[column])
    for column in NUMERIC_FEATURES:
        matrix[column] = pd.to_numeric(df[column], errors="coerce").astype(np.float32)
    return matrix


def _mae(y, pred) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(pred))))


def fit_calibrators(pred_link, y, mode: str) -> list[dict]:
    pred_link = np.asarray(pred_link, dtype=float)
    y = np.asarray(y, dtype=float)
    options = []
    if mode == "log":
        resid = np.log(np.clip(y, 1.0, None)) - pred_link
        options.append({"name": "exp", "kind": "log_affine", "a": 1.0, "b": 0.0})
        options.append({"name": "median_log_shift", "kind": "log_affine", "a": 1.0, "b": float(np.median(resid))})
        options.append({"name": "mean_log_shift", "kind": "log_affine", "a": 1.0, "b": float(np.mean(resid))})
        slope, intercept = np.polyfit(pred_link, np.log(np.clip(y, 1.0, None)), 1)
        if 0.5 <= float(slope) <= 1.5:
            options.append({"name": "log_affine", "kind": "log_affine", "a": float(slope), "b": float(intercept)})
        options.append({"name": "duan_smearing", "kind": "duan", "a": 1.0, "b": float(np.mean(np.exp(resid)))})
    else:
        resid = y - pred_link
        options.append({"name": "identity", "kind": "affine", "a": 1.0, "b": 0.0})
        options.append({"name": "median_shift", "kind": "affine", "a": 1.0, "b": float(np.median(resid))})
        slope, intercept = np.polyfit(pred_link, y, 1)
        if 0.5 <= float(slope) <= 1.5:
            options.append({"name": "affine", "kind": "affine", "a": float(slope), "b": float(intercept)})
    return options


def apply_calibration(pred_link, calibration: dict, mode: str) -> np.ndarray:
    pred_link = np.asarray(pred_link, dtype=float)
    if mode == "log":
        if calibration["kind"] == "duan":
            return np.exp(pred_link) * float(calibration["b"])
        return np.exp(float(calibration["a"]) * pred_link + float(calibration["b"]))
    return float(calibration["a"]) * pred_link + float(calibration["b"])


def choose_calibration(pred_link_fit, y_fit, pred_link_sel, y_sel, mode: str) -> tuple[dict, dict]:
    best = None
    best_metrics = None
    for option in fit_calibrators(pred_link_fit, y_fit, mode):
        pred = apply_calibration(pred_link_sel, option, mode)
        metrics = regression_metrics(y_sel, pred)
        if best is None or metrics["mae_aed"] < best_metrics["mae_aed"]:
            best = option
            best_metrics = metrics
    return best, best_metrics


def _lgb_fit(params, X_train, y_train, X_valid, y_valid, levels_cols):
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=int(params.get("n_estimators", 1200)),
        random_state=42,
        n_jobs=-1,
        verbosity=-1,
        **{k: v for k, v in params.items() if k != "n_estimators"},
    )
    model.fit(
        X_train,
        y_train,
        eval_X=X_valid,
        eval_y=y_valid,
        categorical_feature=levels_cols,
        callbacks=[lgb.early_stopping(40, verbose=False), lgb.log_evaluation(0)],
    )
    trees = int(model.best_iteration_ or params.get("n_estimators", 200))
    return model, max(trees, 1)


def _lgb_refit(params, trees, X_train, y_train, levels_cols):
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=int(trees),
        random_state=42,
        n_jobs=-1,
        verbosity=-1,
        **params,
    )
    model.fit(X_train, y_train, categorical_feature=levels_cols)
    return model


def _xgb_fit(params, X_train, y_train, X_valid, y_valid):
    model = xgb.XGBRegressor(
        n_estimators=int(params.get("n_estimators", 1200)),
        objective="reg:squarederror",
        tree_method="hist",
        enable_categorical=True,
        early_stopping_rounds=40,
        random_state=42,
        n_jobs=-1,
        **{k: v for k, v in params.items() if k != "n_estimators"},
    )
    model.fit(X_train, y_train, eval_set=[(X_valid, y_valid)], verbose=False)
    trees = int(model.best_iteration) + 1
    return model, max(trees, 1)


def _xgb_refit(params, trees, X_train, y_train):
    model = xgb.XGBRegressor(
        n_estimators=int(trees),
        objective="reg:squarederror",
        tree_method="hist",
        enable_categorical=True,
        random_state=42,
        n_jobs=-1,
        **params,
    )
    model.fit(X_train, y_train, verbose=False)
    return model


def _cat_fit(params, X_train, y_train, X_valid, y_valid):
    model = CatBoostRegressor(
        loss_function="RMSE",
        iterations=int(params.get("iterations", 1000)),
        random_seed=42,
        early_stopping_rounds=40,
        verbose=False,
        allow_writing_files=False,
        **{k: v for k, v in params.items() if k != "iterations"},
    )
    cat_idx = list(range(len(CATEGORICAL_FEATURES)))
    model.fit(Pool(X_train, y_train, cat_features=cat_idx), eval_set=Pool(X_valid, y_valid, cat_features=cat_idx))
    trees = int(model.get_best_iteration()) + 1
    return model, max(trees, 1)


def _cat_refit(params, trees, X_train, y_train):
    model = CatBoostRegressor(
        loss_function="RMSE",
        iterations=int(trees),
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        **params,
    )
    model.fit(Pool(X_train, y_train, cat_features=list(range(len(CATEGORICAL_FEATURES)))))
    return model


def suggest_params(trial, kind: str, max_iterations: int) -> dict:
    if kind == "lightgbm":
        return {
            "num_leaves": trial.suggest_int("num_leaves", 31, 255),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.12, log=True),
            "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-2, 10.0, log=True),
            "n_estimators": max_iterations,
        }
    if kind == "xgboost":
        return {
            "max_depth": trial.suggest_int("max_depth", 4, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.15, log=True),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 20.0),
            "subsample": trial.suggest_float("subsample", 0.7, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-2, 10.0, log=True),
            "n_estimators": max_iterations,
        }
    if kind == "catboost":
        return {
            "depth": trial.suggest_int("depth", 6, 10),
            "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.15, log=True),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
            "iterations": max_iterations,
        }
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.03, 0.15, log=True),
        "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 31, 255),
        "min_samples_leaf": trial.suggest_int("min_samples_leaf", 20, 120),
        "l2_regularization": trial.suggest_float("l2_regularization", 0.0, 1.0),
        "max_iter": trial.suggest_int("max_iter", 200, 700),
    }


def tune_kind(kind, core, tail, y_core, y_tail, levels, n_trials, max_iterations, seed):
    if optuna is None or n_trials <= 0:
        params = _default_params(kind, max_iterations)
        model, trees = _fit_once(kind, params, core, y_core, tail, y_tail, levels)
        return params, trees, [{"params": params, "mae_aed": _mae(np.exp(y_tail), np.exp(model.predict(_matrix(kind, tail, levels))))}]

    def objective(trial):
        params = suggest_params(trial, kind, max_iterations)
        model, _trees = _fit_once(kind, params, core, y_core, tail, y_tail, levels)
        pred = _predict_link(kind, model, tail, levels)
        return _mae(np.exp(y_tail), np.exp(pred))

    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    params = study.best_params
    params.update(_fixed_budget(kind, max_iterations))
    model, trees = _fit_once(kind, params, core, y_core, tail, y_tail, levels)
    trials = [
        {"number": t.number, "mae_aed": t.value, "params": t.params}
        for t in study.trials
        if t.value is not None
    ]
    return params, trees, trials


def _fixed_budget(kind, max_iterations):
    if kind == "catboost":
        return {"iterations": max_iterations}
    if kind == "hist_gradient_boosting":
        return {}
    return {"n_estimators": max_iterations}


def _default_params(kind, max_iterations):
    if kind == "lightgbm":
        return {"num_leaves": 63, "learning_rate": 0.06, "min_child_samples": 40, "n_estimators": max_iterations}
    if kind == "xgboost":
        return {"max_depth": 8, "learning_rate": 0.06, "n_estimators": max_iterations}
    if kind == "catboost":
        return {"depth": 8, "learning_rate": 0.06, "iterations": max_iterations}
    return {"learning_rate": 0.06, "max_leaf_nodes": 63, "min_samples_leaf": 40, "max_iter": 400}


def _matrix(kind, df, levels):
    library = "catboost" if kind == "catboost" else "pandas"
    return tree_matrix(df, levels, library)


def _fit_once(kind, params, core, y_core, tail, y_tail, levels):
    X_core = _matrix(kind, core, levels)
    X_tail = _matrix(kind, tail, levels)
    if kind == "lightgbm":
        return _lgb_fit(params, X_core, y_core, X_tail, y_tail, CATEGORICAL_FEATURES)
    if kind == "xgboost":
        return _xgb_fit(params, X_core, y_core, X_tail, y_tail)
    if kind == "catboost":
        return _cat_fit(params, X_core, y_core, X_tail, y_tail)
    model = HistGradientBoostingRegressor(
        learning_rate=params["learning_rate"],
        max_leaf_nodes=params["max_leaf_nodes"],
        min_samples_leaf=params["min_samples_leaf"],
        l2_regularization=params["l2_regularization"],
        max_iter=int(params["max_iter"]),
        early_stopping=False,
        categorical_features=_sklearn_categorical_index(levels),
        random_state=42,
    )
    model.fit(_ordinal_matrix(core, levels), y_core)
    return model, int(params["max_iter"])


def _predict_link(kind, model, df, levels):
    if kind == "hist_gradient_boosting":
        return model.predict(_ordinal_matrix(df, levels))
    return model.predict(_matrix(kind, df, levels))


def _refit(kind, params, trees, train, y_train, levels):
    clean = {k: v for k, v in params.items() if k not in {"n_estimators", "iterations", "max_iter"}}
    if kind == "lightgbm":
        return _lgb_refit(clean, trees, _matrix(kind, train, levels), y_train, CATEGORICAL_FEATURES)
    if kind == "xgboost":
        return _xgb_refit(clean, trees, _matrix(kind, train, levels), y_train)
    if kind == "catboost":
        return _cat_refit(clean, trees, _matrix(kind, train, levels), y_train)
    model = HistGradientBoostingRegressor(
        learning_rate=params["learning_rate"],
        max_leaf_nodes=params["max_leaf_nodes"],
        min_samples_leaf=params["min_samples_leaf"],
        l2_regularization=params["l2_regularization"],
        max_iter=int(params.get("max_iter", trees)),
        early_stopping=False,
        categorical_features=_sklearn_categorical_index(levels),
        random_state=42,
    )
    model.fit(_ordinal_matrix(train, levels), y_train)
    return model


SKLEARN_MAX_CATEGORY_LEVELS = 200


def _sklearn_categorical_columns(levels: dict[str, list[str]]) -> list[str]:
    return [column for column in CATEGORICAL_FEATURES if len(levels[column]) <= SKLEARN_MAX_CATEGORY_LEVELS]


def _sklearn_categorical_index(levels: dict[str, list[str]]) -> list[int]:
    return list(range(len(_sklearn_categorical_columns(levels))))


def _ordinal_matrix(df: pd.DataFrame, levels: dict[str, list[str]], fill_medians: dict | None = None) -> np.ndarray:
    parts = []
    # HistGradientBoosting rejects categoricals with more than 255 levels.
    # Building and project names above the cap stay out of this matrix.
    # Their historical price level is still present as a numeric feature.
    for column in _sklearn_categorical_columns(levels):
        mapping = {value: i for i, value in enumerate(levels[column])}
        other = mapping.get("__OTHER__", 0)
        codes = df[column].astype(str).map(mapping).fillna(other).to_numpy(dtype=np.float64)
        parts.append(codes.reshape(-1, 1))
    nums = df[NUMERIC_FEATURES].apply(pd.to_numeric, errors="coerce")
    if fill_medians:
        for column, median in fill_medians.items():
            nums[column] = nums[column].fillna(median)
    parts.append(nums.to_numpy(dtype=np.float64))
    return np.hstack(parts)


def available_kinds(cfg) -> list[str]:
    kinds = []
    trials = cfg["training"]["optuna_trials"]
    if lgb is not None:
        kinds.append("lightgbm")
    if xgb is not None:
        kinds.append("xgboost")
    if CatBoostRegressor is not None:
        kinds.append("catboost")
    kinds.append("hist_gradient_boosting")
    return [kind for kind in kinds if trials.get(kind, 1) >= 0]


def slice_by_split(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    return frame.loc[frame["split"].eq(name)].copy()


def train_tail_date(meta: dict) -> pd.Timestamp:
    return pd.Timestamp(meta["splits"]["train_inner_tail_start"])


def link_target(y, mode: str) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if mode == "log":
        return np.log(np.clip(y, 1.0, None))
    return y


RIDGE_TE = [
    "area_name_en",
    "master_project_en",
    "nearest_landmark_grouped",
    "nearest_metro_grouped",
    "nearest_mall_grouped",
    "building_name_grouped",
    "project_name_grouped",
]
RIDGE_OHE = ["property_type_en", "property_sub_type_en", "reg_type_en"]
RIDGE_NUM = [c for c in NUMERIC_FEATURES if c != "transaction_month"]


def fit_ridge(train, y_train, core, y_core, tail, y_tail):
    best_alpha, best_mae = None, None
    for alpha in np.logspace(-3, 3, 12):
        model, payload = _ridge_fit(core, y_core, float(alpha))
        pred = _ridge_predict(model, payload, tail)
        mae = _mae(np.exp(y_tail), np.exp(pred))
        if best_mae is None or mae < best_mae:
            best_alpha, best_mae = float(alpha), mae
    model, payload = _ridge_fit(train, y_train, best_alpha)
    return model, payload, best_alpha


def _ridge_fit(df, y, alpha, m=50.0):
    medians = {}
    for column in RIDGE_NUM:
        numeric = pd.to_numeric(df[column], errors="coerce")
        medians[column] = float(numeric.median()) if numeric.notna().any() else 0.0
    global_mean = float(np.mean(y))
    maps = {}
    for column in RIDGE_TE:
        tmp = pd.DataFrame({"key": df[column].astype(str), "y": y})
        agg = tmp.groupby("key")["y"].agg(["mean", "count"])
        smooth = (agg["count"] * agg["mean"] + m * global_mean) / (agg["count"] + m)
        maps[column] = {"values": smooth.to_dict(), "global": global_mean}
    ohe_levels = {column: sorted(df[column].astype(str).unique()) for column in RIDGE_OHE}
    model = Ridge(alpha=alpha, random_state=42)
    model.fit(_ridge_matrix(df, medians, maps, ohe_levels), y)
    return model, {"medians": medians, "maps": maps, "ohe_levels": ohe_levels, "alpha": alpha}


def _ridge_matrix(df, medians, maps, ohe_levels):
    columns = []
    for column in RIDGE_NUM:
        values = pd.to_numeric(df[column], errors="coerce").fillna(medians[column]).to_numpy(dtype=float)
        columns.append(values.reshape(-1, 1))
    for column in RIDGE_TE:
        encoded = df[column].astype(str).map(maps[column]["values"]).fillna(maps[column]["global"])
        columns.append(encoded.to_numpy(dtype=float).reshape(-1, 1))
    for column in RIDGE_OHE:
        values = df[column].astype(str)
        for level in ohe_levels[column][1:]:
            columns.append((values == level).to_numpy(dtype=float).reshape(-1, 1))
    return np.hstack(columns) if columns else np.zeros((len(df), 1))


def _ridge_predict(model, payload, df):
    matrix = _ridge_matrix(df, payload["medians"], payload["maps"], payload["ohe_levels"])
    return model.predict(matrix)
