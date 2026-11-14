"""Unit checks that do not require the full transaction file."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config
from src.features.historical import add_market_history
from src.preprocessing.clean import assign_eligibility, parse_bedrooms


def test_parse_bedrooms():
    assert parse_bedrooms("Studio")[0] == 0
    assert parse_bedrooms("3 B/R")[0] == 3
    assert parse_bedrooms("PENTHOUSE")[2] == "penthouse_unspecified"
    assert parse_bedrooms("PENTHOUSE")[1] is True
    assert np.isnan(parse_bedrooms("Single Room")[0])
    assert parse_bedrooms("Office")[2] == "ambiguous"
    assert parse_bedrooms(None)[2] == "missing"


def test_eligibility_policy():
    cfg = load_config()
    rows = pd.DataFrame(
        [
            _row("sell", "Sales", "Sell", "Residential", "Unit", "Flat", "Existing Properties"),
            _row("pre", "Sales", "Sell - Pre registration", "Residential", "Villa", None, "Off-Plan Properties"),
            _row("delay", "Sales", "Delayed Sell", "Residential", "Unit", "Flat", "Existing Properties"),
            _row("dev", "Sales", "Sell Development", "Residential", "Unit", "Flat", "Existing Properties"),
            _row("plan", "Sales", "Sale On Payment Plan", "Residential", "Unit", "Flat", "Existing Properties"),
            _row("gift", "Gifts", "Grant", "Residential", "Unit", "Flat", "Existing Properties"),
            _row("mort", "Mortgages", "Mortgage Registration", "Residential", "Unit", "Flat", "Existing Properties"),
            _row("comm", "Sales", "Sell", "Commercial", "Unit", "Office", "Existing Properties"),
            _row("land", "Sales", "Sell", "Residential", "Land", None, "Existing Properties"),
            _row("shop", "Sales", "Sell", "Residential", "Unit", "Shop", "Existing Properties"),
        ]
    )
    rows["instance_date"] = pd.Timestamp("2024-01-15")
    rows["procedure_area"] = 80.0
    rows["actual_worth"] = 1_000_000.0
    flagged = assign_eligibility(rows, cfg)
    tiers = dict(zip(flagged["transaction_id"], flagged["eligibility_tier"]))
    assert tiers["sell"] == "primary"
    assert tiers["pre"] == "primary"
    assert tiers["delay"] == "extended_delayed_sell"
    assert tiers["dev"] == "excluded"
    assert tiers["plan"] == "excluded"
    assert tiers["gift"] == "excluded"
    assert tiers["mort"] == "excluded"
    assert tiers["comm"] == "excluded"
    assert tiers["land"] == "excluded"
    assert tiers["shop"] == "excluded"


def test_history_uses_only_earlier_months():
    frame = pd.DataFrame(
        {
            "transaction_id": ["a", "b", "c"],
            "area_name_en": ["Marina", "Marina", "Marina"],
            "master_project_en": ["Dubai Marina", "Dubai Marina", "Dubai Marina"],
            "property_type_en": ["Unit", "Unit", "Unit"],
            "building_name_en": [None, None, None],
            "project_name_en": [None, None, None],
            "bedroom_count": [1, 1, 1],
            "year_month_index": [10, 11, 12],
            "price_per_sqm": [100.0, 300.0, 500.0],
            "is_penthouse": [0, 0, 0],
        }
    )
    out, _ = add_market_history(frame, min_growth_n=20, shrinkage_k=10)
    by_id = out.set_index("transaction_id")
    assert np.isnan(by_id.loc["a", "area_prior_median_psm"])
    assert by_id.loc["b", "area_prior_median_psm"] == 100
    assert by_id.loc["c", "area_prior_median_psm"] == 200
    assert by_id.loc["c", "area_prior_count"] == 2


def _row(tx, group, procedure, usage, ptype, subtype, reg):
    return {
        "transaction_id": tx,
        "trans_group_en": group,
        "procedure_name_en": procedure,
        "property_usage_en": usage,
        "property_type_en": ptype,
        "property_sub_type_en": subtype,
        "reg_type_en": reg,
    }
