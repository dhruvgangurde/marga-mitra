from fastapi import WebSocket

from contracts.models import WsEvent


class Hub:
    def __init__(self) -> None:
        self.sockets: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.sockets.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.sockets.discard(ws)

    async def broadcast(self, event: WsEvent) -> None:
        data = event.model_dump(mode="json")
        for ws in list(self.sockets):
            try:
                await ws.send_json(data)
            except Exception:  # a closed socket fails in several ways; one dead viewer must not stop the rest
                self.disconnect(ws)


hub = Hub()
