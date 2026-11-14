"""Filtered series stay on the same sale population and do not invent growth."""

import pandas as pd

from src.analytics.market import compare_communities, market_series


def _sales():
    return pd.DataFrame(
        {
            "transaction_id": ["a", "b", "c", "d"],
            "instance_date": pd.to_datetime(["2024-01-15", "2024-02-15", "2025-01-20", "2025-02-20"]),
            "actual_worth": [1_000_000, 2_000_000, 1_100_000, 3_000_000],
            "price_per_sqm": [10_000, 20_000, 11_000, 15_000],
            "procedure_area": [100, 100, 100, 200],
            "property_type_en": ["Unit", "Villa", "Unit", "Unit"],
            "reg_type_en": ["Existing Properties", "Existing Properties", "Off-Plan Properties", "Existing Properties"],
            "bedroom_count": [1, 4, 1, 2],
            "master_project_en": ["Dubai Marina", "Dubai Marina", "The Greens", "Dubai Marina"],
            "area_name_en": ["Marsa Dubai", "Marsa Dubai", "Al Thanyah Third", "Marsa Dubai"],
        }
    )


def test_series_filter_counts_only_matching_sales():
    result = market_series(_sales(), {"property_type": "Unit", "registration_type": None}, "quarter")
    assert result["transactions"] == 3
    assert sum(point["transactions"] for point in result["series"]) == 3


def test_comparison_suppresses_growth_below_the_minimum():
    result = compare_communities(
        _sales(),
        [{"kind": "master_project", "name": "Dubai Marina"}, {"kind": "master_project", "name": "Nowhere"}],
        {},
        20,
    )
    marina = result["communities"][0]
    assert marina["yoy_growth_pct"] is None
    assert result["communities"][1]["metrics"] is None
    assert result["communities"][1]["quarterly"] == []
