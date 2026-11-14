"""SHAP summary for the deployed tree model, on a test sample.

Importance is an association with the prediction, not a causal effect.
"""

from __future__ import annotations

import json

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.common import load_config, resolve
from src.models.train import _matrix, _ordinal_matrix


def run_shap(cfg: dict | None = None, sample_size: int = 800) -> None:
    cfg = cfg or load_config()
    reports = resolve(cfg["paths"]["reports"])
    figures = resolve(cfg["paths"]["figures"])
    bundle = joblib.load(resolve(cfg["paths"]["models"]) / "production_model.joblib")
    kind = bundle["kind"]
    if kind not in {"lightgbm", "xgboost", "catboost", "hist_gradient_boosting", "random_forest"}:
        (reports / "shap_status.md").write_text(f"SHAP was not run because the deployed model is {kind}.\n")
        return
    frame = pd.read_parquet(resolve(cfg["paths"]["analytics"]) / "test_predictions.parquet", columns=["transaction_id"])
    model_frame = pd.read_parquet(resolve(cfg["paths"]["processed"]) / "modeling_table.parquet")
    test = model_frame.loc[model_frame["transaction_id"].isin(frame["transaction_id"])].sample(
        n=min(sample_size, len(frame)), random_state=int(cfg["seed"])
    )
    import shap

    model = bundle["estimator"]
    if kind == "hist_gradient_boosting":
        from src.features.schema import NUMERIC_FEATURES
        from src.models.train import _sklearn_categorical_columns

        matrix = _ordinal_matrix(test, bundle["levels"])
        names = _sklearn_categorical_columns(bundle["levels"]) + list(NUMERIC_FEATURES)
        plot_data = pd.DataFrame(matrix, columns=names)
        explainer = shap.TreeExplainer(model)
        plot_values = explainer.shap_values(matrix)
    elif kind == "catboost":
        matrix = _matrix(kind, test, bundle["levels"])
        values = model.get_feature_importance(type="ShapValues", data=matrix)
        plot_values = values[:, :-1]
        plot_data = matrix
    else:
        matrix = _matrix("pandas", test, bundle["levels"])
        explainer = shap.TreeExplainer(model)
        plot_values = explainer.shap_values(matrix)
        plot_data = matrix
    plt.figure()
    shap.summary_plot(plot_values, plot_data, show=False, max_display=20)
    plt.tight_layout()
    plt.savefig(figures / "shap_summary.png", dpi=140, bbox_inches="tight")
    plt.close()
    mean_abs = np.mean(np.abs(np.asarray(plot_values)), axis=0)
    names = list(plot_data.columns) if hasattr(plot_data, "columns") else [f"f{i}" for i in range(len(mean_abs))]
    importance = pd.DataFrame({
        "feature": names,
        "importance": mean_abs,
        "method": f"mean_abs_shap_on_{len(test)}_test_rows",
        "note": "Association with the log-price prediction on a test sample. Not a causal effect and not an AED effect.",
    }).sort_values("importance", ascending=False)
    importance.to_csv(resolve(cfg["paths"]["analytics"]) / "feature_importance.csv", index=False)
    importance.to_csv(reports / "feature_importance.csv", index=False)
    order = np.argsort(mean_abs)[::-1][:4]
    for rank, idx in enumerate(order, start=1):
        plt.figure()
        shap.dependence_plot(int(idx), np.asarray(plot_values), plot_data, show=False)
        plt.tight_layout()
        plt.savefig(figures / f"shap_dependence_{rank}.png", dpi=140, bbox_inches="tight")
        plt.close()
    (reports / "shap_status.md").write_text(
        "\n".join([
            "# SHAP",
            "",
            f"Computed on a {len(test)}-row sample of the untouched test period for `{bundle['model_version']}`.",
            "",
            "Mean absolute SHAP values describe how the fitted model uses features for these predictions. They are not causal effects.",
            "For the deployed log-price model they are on the natural-log price scale, not in AED.",
            "",
            "Top features: " + ", ".join(f"{names[i]} ({mean_abs[i]:.4f})" for i in order) + ".",
            "",
        ])
    )
    print("shap written", flush=True)


if __name__ == "__main__":
    run_shap()
