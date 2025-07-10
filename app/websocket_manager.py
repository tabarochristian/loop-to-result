from fastapi import WebSocket
from typing import Dict, List
import json

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def register(self, experiment_id: str, websocket: WebSocket):
        if experiment_id not in self.active_connections:
            self.active_connections[experiment_id] = []
        self.active_connections[experiment_id].append(websocket)

    def unregister(self, experiment_id: str, websocket: WebSocket):
        if experiment_id in self.active_connections:
            self.active_connections[experiment_id].remove(websocket)
            if not self.active_connections[experiment_id]:
                del self.active_connections[experiment_id]

    async def broadcast(self, experiment_id: str, message: dict):
        if experiment_id in self.active_connections:
            for connection in self.active_connections[experiment_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except Exception as e:
                    self.unregister(experiment_id, connection)