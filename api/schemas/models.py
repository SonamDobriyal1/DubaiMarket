"""Pydantic contracts for the valuation and market API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class ValuationRequest(BaseModel):
    community: str = Field(min_length=2, max_length=120)
    property_type: str
    bedrooms: float = Field(ge=0, le=20)
    size_sqm: float = Field(gt=0, le=20000)
    asking_price: float = Field(gt=0)
    property_subtype: str | None = None
    building: str | None = None
    project: str | None = None
    parking: int | None = Field(default=None, ge=0, le=1)
    registration_type: str | None = None
    official_area: str | None = None
    nearest_landmark: str | None = None
    nearest_metro: str | None = None
    nearest_mall: str | None = None
    valuation_date: date | None = None

    @field_validator("registration_type")
    @classmethod
    def registration(cls, value):
        allowed = {None, "Existing Properties", "Off-Plan Properties"}
        if value not in allowed:
            raise ValueError("registration_type must be Existing Properties or Off-Plan Properties.")
        return value


class ComparableRequest(ValuationRequest):
    asking_price: float | None = None


class CommunityRef(BaseModel):
    community_id: str | None = None
    name: str | None = None
    kind: str | None = None


class CompareRequest(BaseModel):
    communities: list[CommunityRef] = Field(min_length=2, max_length=5)
    date_from: date | None = None
    date_to: date | None = None
    property_type: str | None = None
    bedrooms: float | None = Field(default=None, ge=0, le=20)
    registration_type: str | None = None
    size_min: float | None = Field(default=None, gt=0)
    size_max: float | None = Field(default=None, gt=0)
