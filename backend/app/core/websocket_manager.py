"""WebSocket connection manager for real-time dashboard updates.
Concurrently broadcasts telemetry with per-client timeouts, safe connection tracking,
and graceful shutdown cleanup.
"""
import json
import asyncio
from typing import List, Dict, Any
from fastapi import WebSocket
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(f"WS client connected. Total clients: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(f"WS client disconnected. Total clients: {len(self._connections)}")

    async def disconnect_all(self):
        """Cleanly close all open websocket connections during server shutdown."""
        async with self._lock:
            conns = list(self._connections)
            self._connections.clear()

        for conn in conns:
            try:
                await conn.close(code=1001, reason="Server shutting down")
            except Exception:
                pass
        logger.info(f"Closed {len(conns)} WebSocket connections during shutdown.")

    async def broadcast(self, message: Dict[str, Any]):
        """
        Broadcast to all connected clients concurrently.
        Takes a snapshot of active connections to prevent concurrent modification issues.
        Enforces a 2-second timeout per client so a stalled network connection never blocks others.
        """
        async with self._lock:
            conns = list(self._connections)

        if not conns:
            return

        data = json.dumps(message, default=str)

        # Dispatch all sends in parallel with timeouts
        results = await asyncio.gather(
            *[self._send_with_timeout(conn, data) for conn in conns],
            return_exceptions=True,
        )

        # Identify connections that failed or timed out
        dead = [conn for conn, r in zip(conns, results) if isinstance(r, Exception)]
        if dead:
            async with self._lock:
                for conn in dead:
                    if conn in self._connections:
                        self._connections.remove(conn)
            logger.info(f"Pruned {len(dead)} dead/stalled WS clients. Active clients: {len(self._connections)}")

    async def _send_with_timeout(self, connection: WebSocket, data: str, timeout: float = 2.0):
        """Send data with a strict timeout to prevent slow consumer bottlenecks."""
        await asyncio.wait_for(connection.send_text(data), timeout=timeout)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        data = json.dumps(message, default=str)
        await self._send_with_timeout(websocket, data, timeout=2.0)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def active_connections(self) -> List[WebSocket]:
        return list(self._connections)


manager = ConnectionManager()
