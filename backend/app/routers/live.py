from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.ws import hub

router = APIRouter(tags=["live"])


@router.websocket("/ws")
async def live(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(websocket)
