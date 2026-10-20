"""Request and response bodies that only the API uses; every shared shape lives in contracts.models."""
from datetime import date

from pydantic import BaseModel


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
