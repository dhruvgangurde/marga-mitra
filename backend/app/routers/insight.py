from fastapi import APIRouter, Request

from backend.app import store
from backend.app.deps import in_session
from contracts.models import AuditorFlag

router = APIRouter(tags=["insight"])


@router.get("/auditor/flags")
def auditor_flags(request: Request) -> list[AuditorFlag]:
    return in_session(store.list_flags, request.app.state.seed)
