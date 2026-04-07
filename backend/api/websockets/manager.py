"""
WebSocket Connection Manager
============================
Tracks all live WS connections and provides:
  - subscribe(ws, channel)          — add a client to a named channel
  - unsubscribe(ws, channel)
  - broadcast(channel, message)     — push JSON to everyone on a channel
  - send_personal(ws, message)      — push to one client

Channels used:
  "sensors:{asset_id}"   — live sensor updates for one asset
  "sensors:all"          — updates for every asset
  "alerts"               — WARNING/CRITICAL alerts plant-wide
  "agent:{session_id}"   — streaming agent tokens for one chat session
"""

import asyncio
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # channel → set of WebSocket connections
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        # ws → set of channels it is subscribed to (reverse index for cleanup)
        self._ws_channels: dict[WebSocket, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self, ws: WebSocket, channel: str) -> None:
        await ws.accept()
        async with self._lock:
            self._channels[channel].add(ws)
            self._ws_channels[ws].add(channel)
        logger.info("WS connected   channel=%s  total=%d", channel,
                    len(self._channels[channel]))
        await self.send_personal(ws, {
            "type": "subscribed",
            "channel": channel,
            "server_time": datetime.now(timezone.utc).isoformat(),
        })

    async def subscribe(self, ws: WebSocket, channel: str) -> None:
        async with self._lock:
            self._channels[channel].add(ws)
            self._ws_channels[ws].add(channel)
        logger.debug("WS subscribed  channel=%s", channel)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            for ch in list(self._ws_channels.get(ws, [])):
                self._channels[ch].discard(ws)
                if not self._channels[ch]:
                    del self._channels[ch]
            self._ws_channels.pop(ws, None)
        logger.info("WS disconnected")

    # ── Messaging ─────────────────────────────────────────────────────────────

    @staticmethod
    def _serialise(data: Any) -> str:
        if isinstance(data, str):
            return data
        return json.dumps(data, default=str)

    async def broadcast(self, channel: str, data: Any) -> None:
        """Send to all subscribers of a channel. Dead connections are pruned."""
        payload  = self._serialise(data)
        dead: list[WebSocket] = []

        async with self._lock:
            targets = list(self._channels.get(channel, []))

        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def broadcast_multi(self, channels: list[str], data: Any) -> None:
        payload = self._serialise(data)
        seen: set[WebSocket] = set()
        dead: list[WebSocket] = []

        async with self._lock:
            for ch in channels:
                seen.update(self._channels.get(ch, []))

        for ws in seen:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            await self.disconnect(ws)

    async def send_personal(self, ws: WebSocket, data: Any) -> None:
        try:
            await ws.send_text(self._serialise(data))
        except Exception as e:
            logger.warning("send_personal failed: %s", e)
            await self.disconnect(ws)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        return {
            ch: len(conns)
            for ch, conns in self._channels.items()
        }

    @property
    def total_connections(self) -> int:
        return len(self._ws_channels)


# Singleton used throughout the app
manager = ConnectionManager()
