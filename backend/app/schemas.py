"""Request and response bodies that only the API uses; every shared shape lives in contracts.models."""
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, model_validator

from contracts.models import Metrics, Plan, WorkChange


class Health(BaseModel):
    ok: bool
    db: bool
    llm_provider: str
    weather_mode: str


class ScenarioLoaded(BaseModel):
    seed: int
    start_date: date
    works: int
    segments: int


class Department(BaseModel):
    id: str
    name: str
    icon: str
    color_token: str


class NoDigEntry(BaseModel):
    segment_id: str
    name: str
    protected_until: date
    why: str


class _Days(BaseModel):
    start_day: int = Field(ge=0, le=27)
    end_day: int = Field(ge=0, le=27)

    @model_validator(mode="after")
    def _in_order(self) -> Self:
        if self.end_day < self.start_day:
            raise ValueError("end_day must not be before start_day")
        return self


class ForecastOverride(_Days):
    kind: Literal["rain", "air"]
    value: float
    label: str | None = None


class EventIn(_Days):
    label: str
    segment_ids: list[str] = Field(min_length=1)


class ConfirmationIn(BaseModel):
    """A resident's answer. It never carries a name or a phone number."""
    work_id: str
    answer: Literal["yes", "notyet"]
    problems: list[Annotated[str, Field(max_length=60)]] = Field(default=[], max_length=4)
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "reject"]
    by: str
    reason: str | None = None


class WhatIfIn(BaseModel):
    work_id: str
    delay_days: int = Field(ge=1, le=14)


class WhatIfResult(BaseModel):
    plan: Plan
    diff: list[WorkChange]
    metrics: Metrics
