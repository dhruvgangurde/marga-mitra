from fastapi import APIRouter

from backend.app.config import get_settings
from backend.app.db import db_ok
from backend.app.schemas import Health

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> Health:
    ok = db_ok()
    settings = get_settings()
    return Health(ok=ok, db=ok, llm_provider=settings.llm_provider, weather_mode=settings.weather_mode)
