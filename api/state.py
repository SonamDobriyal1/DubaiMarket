"""Load models and analytical tables once per process."""

from __future__ import annotations

import json
from functools import lru_cache

import joblib
import pandas as pd

from src.common import load_config, resolve


class Runtime:
    def __init__(self):
        self.cfg = load_config()
        self.ready = False
        self.error = None
        self.bundle = None
        self.history = {}
        self.registry = []
        self.sales = None
        self.quarterly = None
        self.summary = None
        self.monthly = None
        self.overview = None
        self.evaluation = None
        self.map_payload = None
        self.rental = None
        try:
            self._load()
            self.ready = True
        except Exception as exc:  # pragma: no cover - surfaced through API
            self.error = str(exc)

    def _load(self):
        analytics = resolve(self.cfg["paths"]["analytics"])
        processed = resolve(self.cfg["paths"]["processed"])
        models = resolve(self.cfg["paths"]["models"])
        self.bundle = joblib.load(models / "production_model.joblib")
        history_dir = processed / "history"
        self.history = {
            name: pd.read_parquet(history_dir / f"{name}.parquet")
            for name in ("area", "master", "area_type", "area_bed", "building", "project")
        }
        self.registry = json.loads((analytics / "community_registry.json").read_text())
        self.sales = pd.read_parquet(processed / "residential_sales.parquet")
        self.sales["instance_date"] = pd.to_datetime(self.sales["instance_date"])
        self.quarterly = pd.read_parquet(analytics / "community_quarterly_metrics.parquet")
        self.summary = pd.read_parquet(analytics / "community_summary.parquet")
        self.monthly = pd.read_parquet(analytics / "community_monthly_metrics.parquet")
        self.overview = json.loads((analytics / "market_overview.json").read_text())
        self.evaluation = json.loads((analytics / "model_evaluation.json").read_text())
        self.map_payload = json.loads((analytics / "map_communities.json").read_text())
        self.rental = json.loads((analytics / "rental_feasibility.json").read_text())
        self.analytics_dir = analytics


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    return Runtime()
