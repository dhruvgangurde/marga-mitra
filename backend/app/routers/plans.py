from fastapi import APIRouter, Request

from backend.app import store
from backend.app.db import session
from contracts.models import Plan

router = APIRouter(tags=["plans"])


@router.get("/plans")
def list_plans(request: Request) -> list[Plan]:
    with session() as s:
        return store.list_plans(s, request.app.state.seed)
