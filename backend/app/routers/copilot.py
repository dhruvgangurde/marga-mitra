import logging

from fastapi import APIRouter, HTTPException, Request

from backend.app.config import get_settings
from backend.app.schemas import CopilotIn
from contracts.models import CopilotReply

logger = logging.getLogger(__name__)
router = APIRouter(tags=["copilot"])


@router.post("/copilot")
async def ask(request: Request, body: CopilotIn) -> CopilotReply:
    wiring = request.app.state.wiring
    try:
        # The copilot calls this same API at internal_api_base, never through the public address.
        return await wiring.run_copilot(body.message, body.context.model_dump(), get_settings().internal_api_base,
                                        wiring.deps.emit)
    except Exception as e:  # any failure inside the copilot is a plain "try again" for the person
        logger.exception("The copilot could not answer.")
        raise HTTPException(503, "The copilot could not answer. Try again.") from e
