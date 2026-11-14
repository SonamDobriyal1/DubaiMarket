"""Asking-price classification. This is not an investment recommendation."""

from __future__ import annotations

import math


def classify_asking_price(asking_price: float, predicted: float, lower: float, upper: float, max_width: float) -> dict:
    if not all(math.isfinite(v) for v in (asking_price, predicted, lower, upper)) or predicted <= 0 or lower > upper:
        return {
            "classification": "Inconclusive",
            "price_gap_pct": None,
            "relative_interval_width": None,
            "reason": "The estimate or the prediction interval is not usable.",
        }
    gap = (asking_price - predicted) / predicted * 100.0
    width = (upper - lower) / predicted
    if asking_price < lower:
        label = "Potentially undervalued"
        reason = "The asking price is below the lower bound of the individual-transaction prediction interval."
    elif asking_price > upper:
        label = "Potentially overvalued"
        reason = "The asking price is above the upper bound of the individual-transaction prediction interval."
    elif width > max_width:
        label = "Inconclusive"
        reason = (
            "The asking price sits inside the prediction interval, but the interval is wider than "
            f"{max_width:.0%} of the estimate, so the band is too coarse to call the price fair."
        )
    else:
        label = "Fairly priced"
        reason = (
            "The asking price sits inside the prediction interval, and the interval is within the "
            "configured informative-width limit."
        )
    return {
        "classification": label,
        "price_gap_pct": gap,
        "relative_interval_width": width,
        "reason": reason,
        "rule": (
            "price_gap_pct = (asking_price - estimated_market_value) / estimated_market_value * 100. "
            "Below the lower bound: potentially undervalued. Above the upper bound: potentially overvalued. "
            "Inside a narrow interval: fairly priced. Inside a wide interval: inconclusive."
        ),
    }


def reliability_indicator(prior_count: float | None, relative_width: float | None, support_source: str = "official_area") -> dict:
    reasons = []
    count = 0 if prior_count is None or (isinstance(prior_count, float) and math.isnan(prior_count)) else prior_count
    width = None if relative_width is None or (isinstance(relative_width, float) and math.isnan(relative_width)) else relative_width
    source_label = "official area" if support_source == "official_area" else "master project"
    if count < 30:
        reasons.append(f"Fewer than 30 prior sales in the resolved {source_label} before the valuation month.")
    if width is None:
        reasons.append("Interval width is unavailable.")
    elif width > 0.70:
        reasons.append("The 90% prediction interval is wider than 70% of the estimate.")
    if count >= 200 and width is not None and width <= 0.45:
        level = "supported"
    elif count < 30 or (width is not None and width > 0.80):
        level = "limited"
    else:
        level = "moderate"
    return {
        "level": level,
        "reasons": reasons,
        "prior_sales": count,
        "prior_sales_source": support_source,
        "prior_area_sales": count if support_source == "official_area" else None,
        "definition": (
            "A heuristic label for data support and interval width. "
            "It is not the probability that the estimate equals a future transaction price."
        ),
    }
