"""Policy, comparable search, and API validation tests."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app
from src.comparables.engine import find_comparables
from src.valuation.policy import classify_asking_price


def test_classification_rules():
    below = classify_asking_price(700_000, 1_000_000, 800_000, 1_200_000, 0.70)
    assert below["classification"] == "Potentially undervalued"
    inside = classify_asking_price(1_000_000, 1_000_000, 800_000, 1_200_000, 0.70)
    assert inside["classification"] == "Fairly priced"
    wide = classify_asking_price(1_000_000, 1_000_000, 400_000, 1_600_000, 0.70)
    assert wide["classification"] == "Inconclusive"
    above = classify_asking_price(1_500_000, 1_000_000, 800_000, 1_200_000, 0.70)
    assert above["classification"] == "Potentially overvalued"


def test_comparables_exclude_future_and_other_communities():
    sales = pd.DataFrame(
        {
            "transaction_id": ["old", "future", "other", "close"],
            "instance_date": pd.to_datetime(["2024-01-01", "2025-01-01", "2024-06-01", "2024-11-01"]),
            "master_project_en": ["Dubai Marina", "Dubai Marina", "The Greens", "Dubai Marina"],
            "area_name_en": ["Marsa Dubai", "Marsa Dubai", "Al Thanyah Third", "Marsa Dubai"],
            "property_type_en": ["Unit", "Unit", "Unit", "Unit"],
            "bedroom_count": [1, 1, 1, 1],
            "procedure_area": [80, 80, 80, 82],
            "actual_worth": [1_000_000, 9_000_000, 1_000_000, 1_050_000],
            "price_per_sqm": [12500, 112500, 12500, 12805],
            "reg_type_en": ["Existing Properties"] * 4,
            "building_name_en": ["A", "A", "B", "A"],
            "project_name_en": ["P", "P", "Q", "P"],
        }
    )
    result = find_comparables(
        sales,
        valuation_date=datetime(2024, 12, 1),
        community_column="master_project_en",
        community_value="Dubai Marina",
        property_type="Unit",
        bedrooms=1,
        size_sqm=80,
        registration="Existing Properties",
        building="A",
        project="P",
        min_return=1,
        max_return=10,
    )
    ids = [row["transaction_id"] for row in result["comparables"]]
    assert "future" not in ids
    assert "other" not in ids
    assert "old" in ids and "close" in ids


def test_api_rejects_bad_input_and_reports_health():
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        bad = client.post("/api/valuation/predict", json={"community": "Dubai Marina", "property_type": "Unit"})
        assert bad.status_code == 422
        assert bad.json()["error"]["code"] == "invalid_request"
