from typing import List, Dict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[Dict] = []

    async def connect(self, websocket: WebSocket, user_id: int, role: str):
        await websocket.accept()
        self.active_connections.append({
            "websocket": websocket,
            "user_id": user_id,
            "role": role
        })

    def disconnect(self, websocket: WebSocket):
        self.active_connections = [
            c for c in self.active_connections if c["websocket"] != websocket
        ]

    async def broadcast(self, message: dict):
        dead = []
        for conn in self.active_connections:
            try:
                await conn["websocket"].send_json(message)
            except Exception:
                dead.append(conn["websocket"])
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_to_roles(self, message: dict, roles: List[str]):
        dead = []
        for conn in self.active_connections:
            if conn["role"] in roles:
                try:
                    await conn["websocket"].send_json(message)
                except Exception:
                    dead.append(conn["websocket"])
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
