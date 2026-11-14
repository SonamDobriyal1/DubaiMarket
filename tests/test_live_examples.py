"""Exercise the loaded model on communities that exist in the extract.

Expected prices are not asserted. The checks cover response structure,
interval order, comparable dates, and the refusal for a community with
too few primary residential sales.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from api.main import app


EXAMPLES = (
    ("Dubai Marina", "apartment", "Unit"),
    ("Downtown Dubai", "apartment", "Unit"),
    ("Al Furjan", "villa", "Villa"),
    ("The Greens", "apartment", "Unit"),
)


def _subject(sales: pd.DataFrame, community: str, property_type: str) -> dict:
    part = sales.loc[
        sales["master_project_en"].eq(community) & sales["property_type_en"].eq(property_type)
    ]
    assert not part.empty, community
    row = part.sort_values("instance_date").iloc[len(part) // 2]
    bedrooms = row["bedroom_count"]
    return {
        "community": community if community != "DownTown Dubai" else "Downtown Dubai",
        "property_type": "apartment" if property_type == "Unit" else "villa",
        "bedrooms": 2 if pd.isna(bedrooms) else float(bedrooms),
        "size_sqm": float(row["procedure_area"]),
        "asking_price": float(row["actual_worth"]),
        "registration_type": row["reg_type_en"],
        "valuation_date": "2025-11-07",
    }


def test_examples_and_gardens_refusal():
    sales = pd.read_parquet(
        "data/processed/residential_sales.parquet",
        columns=[
            "master_project_en",
            "property_type_en",
            "bedroom_count",
            "procedure_area",
            "actual_worth",
            "reg_type_en",
            "instance_date",
        ],
    )
    with TestClient(app) as client:
        health = client.get("/health").json()
        assert health["status"] == "ready"
        methodology = client.get("/api/model/methodology").json()
        assert methodology["asking_price_used_as_feature"] is False
        features = json.loads(Path("data/processed/feature_metadata.json").read_text())
        used = " ".join(features["categorical_features"] + features["numeric_features"]).casefold()
        assert "asking" not in used
        assert "meter_sale_price" not in used
        assert "actual_worth" not in used
        assert "rent_value" not in used

        for community, _label, property_type in EXAMPLES:
            lookup = "DownTown Dubai" if community == "Downtown Dubai" else community
            body = _subject(sales, lookup, property_type)
            response = client.post("/api/valuation/predict", json=body)
            assert response.status_code == 200, response.text
            payload = response.json()
            estimate = payload["estimated_market_value_aed"]
            lower = payload["valuation_interval"]["lower_aed"]
            upper = payload["valuation_interval"]["upper_aed"]
            assert estimate > 0
            assert 0 <= lower <= upper
            assert payload["asking_price_used_as_model_input"] is False
            assert payload["pricing_classification"] in {
                "Potentially undervalued",
                "Fairly priced",
                "Potentially overvalued",
                "Inconclusive",
            }
            assert payload["stale_market_features"] is False
            for comp in payload["comparables"]["comparables"]:
                assert comp["transaction_date"] < payload["valuation_date"]
                assert comp["transaction_id"]
                assert comp["similarity_score"] >= 0

        gardens = client.post(
            "/api/valuation/predict",
            json={
                "community": "The Gardens",
                "property_type": "villa",
                "bedrooms": 3,
                "size_sqm": 250,
                "asking_price": 2_000_000,
            },
        )
        assert gardens.status_code == 422
        assert "minimum of 30" in gardens.json()["error"]["message"]

        unsupported = client.post(
            "/api/valuation/comparables",
            json={
                "community": "Dubai Marina",
                "property_type": "Land",
                "bedrooms": 0,
                "size_sqm": 100,
            },
        )
        assert unsupported.status_code == 422
        assert unsupported.json()["error"]["code"] == "invalid_subject"
