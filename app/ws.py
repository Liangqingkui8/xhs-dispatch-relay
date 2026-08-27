# encoding: utf-8
"""WebSocket 管理：事件广播到所有前端连接"""
import json
from typing import Set

from fastapi import WebSocket

from .models import Event


class WsManager:
    def __init__(self):
        self._conns: Set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._conns.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._conns.discard(ws)

    async def broadcast(self, event: Event) -> None:
        msg = json.dumps(event.to_dict(), ensure_ascii=False)
        dead = []
        for ws in list(self._conns):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.remove(ws)
