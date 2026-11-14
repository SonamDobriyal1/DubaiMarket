"""Valuation and comparable-sales routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.schemas.models import ComparableRequest, ValuationRequest
from api.state import Runtime
from src.comparables.engine import find_comparables
from src.valuation.engine import resolve_location, valuate

router = APIRouter()


def _runtime(request: Request) -> Runtime:
    runtime = request.app.state.runtime
    if not runtime.ready:
        raise HTTPException(status_code=503, detail={"code": "not_ready", "message": runtime.error or "Artifacts are not loaded."})
    return runtime


@router.post("/valuation/predict")
def predict(body: ValuationRequest, request: Request):
    runtime = _runtime(request)
    subject = body.model_dump()
    subject["valuation_date"] = body.valuation_date.isoformat() if body.valuation_date else None
    try:
        return valuate(
            subject,
            runtime.bundle,
            runtime.history,
            runtime.registry,
            runtime.sales,
            runtime.quarterly,
            runtime.cfg,
        )
    except LookupError as exc:
        raise HTTPException(status_code=422, detail={"code": "unknown_or_unsupported_community", "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_subject", "message": str(exc)}) from exc


@router.post("/valuation/comparables")
def comparables(body: ComparableRequest, request: Request):
    runtime = _runtime(request)
    try:
        location = resolve_location(
            body.community,
            runtime.registry,
            body.official_area,
            float(runtime.cfg["valuation"]["modal_area_share_min"]),
        )
    except LookupError as exc:
        raise HTTPException(status_code=422, detail={"code": "unknown_or_unsupported_community", "message": str(exc)}) from exc
    valuation_date = body.valuation_date or runtime.bundle["data_max_date"]
    column = "master_project_en" if location["master_project_en"] else "area_name_en"
    value = location["master_project_en"] or location["area_name_en"]
    folded = body.property_type.casefold()
    if folded in {"unit", "apartment", "flat"}:
        property_type = "Unit"
    elif folded == "villa":
        property_type = "Villa"
    else:
        raise HTTPException(status_code=422, detail={"code": "invalid_subject", "message": "Unsupported property type."})
    return find_comparables(
        runtime.sales,
        valuation_date=valuation_date if hasattr(valuation_date, "year") else __import__("pandas").Timestamp(valuation_date).to_pydatetime(),
        community_column=column,
        community_value=value,
        property_type=property_type,
        bedrooms=body.bedrooms,
        size_sqm=body.size_sqm,
        registration=body.registration_type,
        building=body.building,
        project=body.project,
        max_return=int(runtime.cfg["analytics"]["comparable_max_return"]),
        min_return=int(runtime.cfg["analytics"]["comparable_min_return"]),
    )
