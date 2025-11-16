# conexão dos players

import asyncio
from typing import Dict, Any
from starlette.websockets import WebSocket

class ConnectionManager:
    def __init__(self):
        self._clients: Dict[str, WebSocket] = {}   # client_id -> ws
        self._meta: Dict[str, dict] = {}          # client_id -> {name, avatar}

    def client_count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket, client_id: str):
        await ws.accept()
        self._clients[client_id] = ws

    def set_meta(self, client_id, meta):
        if client_id not in self._meta:
            meta["joinOrder"] = len(self._meta)  # 0 = brancas, 1 = pretas
        self._meta[client_id] = meta

    def remove(self, client_id: str):
        self._clients.pop(client_id, None)
        self._meta.pop(client_id, None)

    def list_players(self):
        ordered = sorted(
            self._meta.items(),
            key=lambda kv: kv[1].get("joinOrder", 9999)
        )
        return [
            {"id": cid, **meta} for cid, meta in ordered
        ]

    async def send_personal(self, client_id: str, message: dict):
        ws = self._clients.get(client_id)
        if ws:
            await ws.send_json(message)

    async def broadcast(self, message: dict):
        if not self._clients:
            return
        to_drop = []
        for cid, ws in self._clients.items():
            try:
                await ws.send_json(message)
            except Exception:
                to_drop.append(cid)
        for cid in to_drop:
            self.remove(cid)

    async def recv_json(self, client_id: str) -> Any:
        ws = self._clients.get(client_id)
        if not ws:
            return None
        return await ws.receive_json()
