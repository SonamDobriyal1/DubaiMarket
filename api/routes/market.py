"""Market, community, map, and methodology routes."""

from __future__ import annotations

import copy
import json

from fastapi import APIRouter, HTTPException, Query, Request

from api.schemas.models import CompareRequest
from api.state import Runtime
from src.analytics.market import compare_communities, filtered_explorer, market_series
from src.analytics.run_analytics import json_ready
from src.common import community_key

router = APIRouter()


def _runtime(request: Request) -> Runtime:
    runtime = request.app.state.runtime
    if not runtime.ready:
        raise HTTPException(status_code=503, detail={"code": "not_ready", "message": runtime.error or "Artifacts are not loaded."})
    return runtime


@router.get("/market/overview")
def market_overview(request: Request):
    runtime = _runtime(request)
    overview = dict(runtime.overview)
    # Full monthly series stays available; the response keeps it because the UI needs the trend.
    overview["rental_valuation_status"] = runtime.rental["rental_valuation_status"]
    return overview


@router.get("/market/series")
def market_trend_series(
    request: Request,
    grain: str = Query(default="quarter", pattern="^(month|quarter)$"),
    property_type: str | None = None,
    registration_type: str | None = None,
):
    runtime = _runtime(request)
    if property_type not in {None, "Unit", "Villa"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": "property_type must be Unit or Villa."})
    if registration_type not in {None, "Existing Properties", "Off-Plan Properties"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": "registration_type is not supported."})
    return market_series(
        runtime.sales,
        {"property_type": property_type, "registration_type": registration_type},
        "month" if grain == "month" else "quarter",
    )


@router.get("/market/explorer")
def market_explorer(
    request: Request,
    kind: str = Query(default="master_project"),
    property_type: str | None = None,
    registration_type: str | None = None,
    bedrooms: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    runtime = _runtime(request)
    if kind not in {"master_project", "official_area"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": "kind must be master_project or official_area."})
    return filtered_explorer(
        runtime.sales,
        {
            "property_type": property_type,
            "registration_type": registration_type,
            "bedrooms": bedrooms,
            "date_from": date_from,
            "date_to": date_to,
        },
        kind,
        int(runtime.cfg["analytics"]["min_growth_observations"]),
    )


@router.get("/communities/registry")
def community_registry(request: Request):
    runtime = _runtime(request)
    return {"communities": runtime.registry}


@router.get("/communities")
def communities(request: Request, kind: str | None = None, min_transactions: int = Query(default=1, ge=1)):
    runtime = _runtime(request)
    frame = runtime.summary
    if kind:
        frame = frame.loc[frame["community_kind"].eq(kind)]
    frame = frame.loc[frame["transactions"].ge(min_transactions)]
    columns = [
        "community_id",
        "community_name",
        "community_kind",
        "transactions",
        "median_price_aed",
        "median_psm",
        "yoy_growth_pct",
        "qoq_growth_pct",
        "trailing_4q_transactions",
        "market_activity_score",
        "data_confidence_score",
        "last_transaction",
        "total_value_aed",
        "cross_sectional_dispersion",
        "time_series_volatility",
        "share_unit",
        "share_villa",
        "share_existing",
        "share_offplan",
        "first_transaction",
    ]
    return {"communities": json_ready(frame[columns].sort_values("transactions", ascending=False))}


@router.get("/communities/{community_id}")
def community_detail(community_id: str, request: Request):
    runtime = _runtime(request)
    row = runtime.summary.loc[runtime.summary["community_id"].eq(community_id)]
    if row.empty:
        raise HTTPException(status_code=404, detail={"code": "unknown_community", "message": community_id})
    record = json_ready(row)[0]
    record["property_types"] = json_ready(
        pd_filter(runtime, "community_property_type_metrics.parquet", community_id)
    )
    record["bedrooms"] = json_ready(pd_filter(runtime, "community_bedroom_metrics.parquet", community_id))
    return record


@router.get("/communities/{community_id}/trends")
def community_trends(community_id: str, request: Request):
    runtime = _runtime(request)
    if runtime.summary.loc[runtime.summary["community_id"].eq(community_id)].empty:
        raise HTTPException(status_code=404, detail={"code": "unknown_community", "message": community_id})
    monthly = runtime.monthly.loc[runtime.monthly["community_id"].eq(community_id)].sort_values("year_month")
    quarterly = runtime.quarterly.loc[runtime.quarterly["community_id"].eq(community_id)].sort_values("quarter")
    return {"community_id": community_id, "monthly": json_ready(monthly), "quarterly": json_ready(quarterly)}


@router.post("/communities/compare")
def compare(body: CompareRequest, request: Request):
    runtime = _runtime(request)
    resolved = []
    for item in body.communities:
        match = _resolve_ref(runtime, item.community_id, item.name, item.kind)
        resolved.append({"kind": match["community_kind"], "name": match["community_name"]})
    return compare_communities(
        runtime.sales,
        resolved,
        {
            "date_from": body.date_from.isoformat() if body.date_from else None,
            "date_to": body.date_to.isoformat() if body.date_to else None,
            "property_type": body.property_type,
            "bedrooms": body.bedrooms,
            "registration_type": body.registration_type,
            "size_min": body.size_min,
            "size_max": body.size_max,
        },
        int(runtime.cfg["analytics"]["min_growth_observations"]),
    )


@router.get("/map/communities")
def map_communities(request: Request, kind: str | None = None):
    runtime = _runtime(request)
    if kind and kind not in {"master_project", "official_area"}:
        raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": "kind must be master_project or official_area."})
    payload = copy.deepcopy(runtime.map_payload)
    if kind:
        payload["communities"] = [row for row in payload["communities"] if row["community_kind"] == kind]
    _attach_place_centroids(runtime, payload)
    return payload


@router.get("/model/methodology")
def methodology(request: Request):
    runtime = _runtime(request)
    evaluation = runtime.evaluation
    return {
        "dataset": {
            "source": runtime.cfg["data"]["raw_csv"],
            "dataset_sha256": evaluation.get("dataset_sha256"),
            "coverage": _coverage(runtime),
            "splits": evaluation.get("splits"),
            "rows": {
                "train": evaluation.get("n_train"),
                "validation_fit": evaluation.get("n_val_fit"),
                "validation_selection": evaluation.get("n_val_sel"),
                "validation_conformal": evaluation.get("n_val_conf"),
                "test": evaluation.get("n_test"),
            },
        },
        "target": "actual_worth in AED for primary residential dwelling sales",
        "asking_price_used_as_feature": False,
        "selected_model": evaluation.get("selected_model"),
        "selection_rule": evaluation.get("selection_rule"),
        "validation_selection_mae_aed": evaluation.get("validation_selection_mae_aed"),
        "test_metrics": evaluation.get("test_metrics"),
        "prediction_interval": {
            "nominal_coverage": evaluation.get("interval", {}).get("nominal_coverage"),
            "test_overall": evaluation.get("interval", {}).get("overall"),
            "property_type_coverage": (evaluation.get("interval", {}).get("segments") or {}).get("property_type"),
            "interpretation": evaluation.get("interval", {}).get("interpretation"),
        },
        "model_comparison_note": _comparison_note(runtime),
        "rental": runtime.rental,
        "limitations": [
            "Estimates are statistical predictions of a registered transaction price, not appraisals or offers.",
            "Coverage of the nominal interval is an average property of the calibration method, not a guarantee for every community.",
            "Off-plan pre-registration prices and existing-property resales are different markets even inside one model.",
            "The transaction extract has no coordinates. Map pins are OpenStreetMap place centroids matched by community name, not parcel coordinates, and unmatched communities are left off the map.",
            "Rental yields are unavailable.",
            "Scores are descriptive. They are not investment recommendations.",
        ],
    }


@router.get("/model/features")
def model_features(request: Request):
    runtime = _runtime(request)
    import pandas as pd

    path = runtime.analytics_dir / "feature_importance.csv"
    if not path.exists():
        return {"features": [], "note": "Feature associations have not been written."}
    frame = pd.read_csv(path).head(12)
    return {
        "features": json_ready(frame),
        "note": "Mean absolute SHAP on a 200-row untouched test sample, measured on the natural-log price scale. These are associations inside the fitted model, not causes.",
    }


def _coverage(runtime: Runtime) -> dict:
    import json

    from src.common import resolve

    audit_path = resolve(runtime.cfg["paths"]["reports"]) / "dataset_audit.json"
    summary_path = resolve(runtime.cfg["paths"]["interim"]) / "preprocessing_summary.json"
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    return {
        "raw_rows": audit.get("n_rows"),
        "deduplicated_rows": summary.get("cleaned_rows"),
        "primary_residential_sales": summary.get("primary_rows"),
        "date_min": summary.get("date_min_primary"),
        "date_max": summary.get("date_max_primary"),
    }


def _comparison_note(runtime: Runtime) -> str | None:
    import pandas as pd

    path = runtime.analytics_dir / "model_comparison.csv"
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    selected = frame.loc[frame["selected"].eq(True)]
    catboost = frame.loc[frame["model"].eq("catboost_log_unified")]
    if selected.empty or catboost.empty:
        return None
    return (
        "CatBoost's untouched-test MAE under the precommitted calibration was "
        f"{float(catboost.iloc[0]['test_mae_aed']):,.0f} AED. "
        f"The deployed {selected.iloc[0]['model']} model was selected on validation MAE "
        f"({float(selected.iloc[0]['validation_mae_aed']):,.0f} AED versus CatBoost "
        f"{float(catboost.iloc[0]['validation_mae_aed']):,.0f} AED). "
        "The test set was not used to change that choice."
    )


def _resolve_ref(runtime: Runtime, community_id, name, kind):
    frame = runtime.summary
    if community_id:
        hit = frame.loc[frame["community_id"].eq(community_id)]
    else:
        hit = frame.loc[frame["community_name"].str.casefold().eq((name or "").casefold())]
        if kind:
            hit = hit.loc[hit["community_kind"].eq(kind)]
    if hit.empty:
        raise HTTPException(status_code=404, detail={"code": "unknown_community", "message": community_id or name})
    if len(hit) > 1:
        raise HTTPException(status_code=409, detail={"code": "ambiguous_community", "message": "Pass community_id or kind."})
    row = hit.iloc[0]
    return {"community_kind": row["community_kind"], "community_name": row["community_name"], "community_id": row["community_id"]}


def _attach_place_centroids(runtime: Runtime, payload: dict) -> None:
    """Overlay verified OpenStreetMap place matches. Unmatched rows stay unlocated."""
    path = runtime.analytics_dir / "community_centroids.json"
    if not path.exists():
        return
    document = json.loads(path.read_text())
    by_name: dict[str, dict] = {}
    for place in document.get("places") or []:
        name = str(place.get("community_name") or "").casefold()
        try:
            lat = float(place["latitude"])
            lon = float(place["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if not name or not (24.70 <= lat <= 25.50 and 54.80 <= lon <= 55.70):
            continue
        by_name[name] = {**place, "latitude": lat, "longitude": lon}
    candidates = []
    for row in payload.get("communities") or []:
        place = by_name.get(str(row.get("community_name") or "").casefold())
        if place:
            candidates.append((row, place))
    best: dict[tuple[float, float], tuple[dict, dict]] = {}
    for row, place in candidates:
        key = (round(place["latitude"], 4), round(place["longitude"], 4))
        current = best.get(key)
        if current is None or int(row.get("transactions") or 0) > int(current[0].get("transactions") or 0):
            best[key] = (row, place)
    chosen = {id(row) for row, _place in best.values()}
    matched = 0
    for row, place in candidates:
        if id(row) not in chosen:
            continue
        row["latitude"] = place["latitude"]
        row["longitude"] = place["longitude"]
        row["location_source"] = document.get("source") or "OpenStreetMap Nominatim"
        row["location_label"] = place.get("label")
        matched += 1
    if not matched:
        return
    payload["geometry_available"] = True
    payload["location_source"] = document.get("source") or "OpenStreetMap Nominatim"
    note = document.get("note") or "Place centroids come from OpenStreetMap. They are not coordinates from the transaction extract."
    if len(candidates) > matched:
        note = f"{note} When several communities resolve to the same place, only the one with more registered sales is pinned."
    payload["geometry_note"] = note


def pd_filter(runtime: Runtime, filename: str, community_id: str):
    import pandas as pd

    frame = pd.read_parquet(runtime.analytics_dir / filename)
    return frame.loc[frame["community_id"].eq(community_id)]
