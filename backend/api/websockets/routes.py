"""
WebSocket endpoints
===================

GET /ws/sensors/{asset_id}   — live sensor feed for one asset
GET /ws/sensors              — live feed for ALL assets
GET /ws/alerts               — plant-wide WARNING/CRITICAL stream
GET /ws/agent/{session_id}   — streaming agent responses (SSE-over-WS)

All endpoints accept an optional ?token=<JWT> query param for auth.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from api.websockets.manager import manager
from core.security import verify_token
from core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()
router   = APIRouter(tags=["websockets"])


# ── Auth helper ───────────────────────────────────────────────────────────────

async def _authenticate_ws(ws: WebSocket, token: str | None) -> bool:
    """Returns True if the token is valid; closes the WS and returns False if not."""
    if not token:
        await ws.close(code=4001, reason="Missing auth token")
        return False
    try:
        verify_token(token, expected_type="access")
        return True
    except Exception:
        await ws.close(code=4003, reason="Invalid or expired token")
        return False


# ── /ws/sensors/{asset_id} ────────────────────────────────────────────────────

@router.websocket("/sensors/{asset_id}")
async def ws_sensor_asset(
    ws: WebSocket,
    asset_id: str,
    token: str | None = Query(default=None),
):
    """
    Subscribe to live sensor readings for a specific asset.

    Message format (server → client):
    {
        "type": "sensor_update",
        "asset_id": "TRB-001",
        "readings": [ { "sensor": "vibration_x", "value": 2.3, ... }, ... ],
        "timestamp": "2024-01-15T10:30:00Z"
    }

    Client can send:
    { "action": "ping" }   → server replies with pong
    """
    if not await _authenticate_ws(ws, token):
        return

    channel = f"sensors:{asset_id}"
    await manager.connect(ws, channel)

    try:
        while True:
            # Listen for client messages (ping / unsubscribe)
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                msg = json.loads(raw)
                if msg.get("action") == "ping":
                    await manager.send_personal(ws, {
                        "type": "pong",
                        "server_time": datetime.now(timezone.utc).isoformat(),
                    })
            except asyncio.TimeoutError:
                pass   # no message — that's fine, broadcaster will push
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
        logger.info("WS sensor feed closed: asset=%s", asset_id)


# ── /ws/sensors (all assets) ──────────────────────────────────────────────────

@router.websocket("/sensors")
async def ws_sensors_all(
    ws: WebSocket,
    token: str | None = Query(default=None),
):
    """
    Subscribe to live sensor readings for ALL assets.
    Useful for the main plant dashboard.
    """
    if not await _authenticate_ws(ws, token):
        return

    await manager.connect(ws, "sensors:all")

    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                msg = json.loads(raw)

                # Allow client to narrow subscription to specific assets
                if msg.get("action") == "subscribe_asset":
                    extra_id = msg.get("asset_id")
                    if extra_id:
                        await manager.subscribe(ws, f"sensors:{extra_id}")
                        await manager.send_personal(ws, {
                            "type": "subscribed",
                            "channel": f"sensors:{extra_id}",
                        })

            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)


# ── /ws/alerts ────────────────────────────────────────────────────────────────

@router.websocket("/alerts")
async def ws_alerts(
    ws: WebSocket,
    token: str | None = Query(default=None),
):
    """
    Subscribe to plant-wide WARNING and CRITICAL alerts in real time.

    Message format (server → client):
    {
        "type": "alert_fired",
        "asset_id": "TRB-001",
        "sensor": "vibration_x",
        "value": 5.3,
        "alert_level": "WARNING",
        "failure_name": "Bearing wear",
        "rul_hours": 48.5,
        "timestamp": "2024-01-15T10:30:00Z"
    }
    """
    if not await _authenticate_ws(ws, token):
        return

    await manager.connect(ws, "alerts")

    try:
        while True:
            try:
                await asyncio.wait_for(ws.receive_text(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)


# ── /ws/agent/{session_id} ────────────────────────────────────────────────────

@router.websocket("/agent/{session_id}")
async def ws_agent(
    ws: WebSocket,
    session_id: str,
    token: str | None = Query(default=None),
):
    """
    Bi-directional agent channel.

    Client sends:
    {
        "message": "Why is TRB-001 vibrating?",
        "asset_id": "TRB-001",          // optional context scope
        "history": [...]                 // optional conversation history
    }

    Server streams back:
    { "type": "agent_chunk",  "session_id": "...", "delta": "Based on..." }
    { "type": "agent_chunk",  "session_id": "...", "delta": " the sensor..." }
    { "type": "agent_done",   "session_id": "...", "sources": [...] }

    On error:
    { "type": "agent_error",  "session_id": "...", "detail": "..." }
    """
    if not await _authenticate_ws(ws, token):
        return

    channel = f"agent:{session_id}"
    await manager.connect(ws, channel)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal(ws, {
                    "type": "agent_error",
                    "session_id": session_id,
                    "detail": "Invalid JSON payload",
                })
                continue

            user_message = payload.get("message", "").strip()
            if not user_message:
                continue

            asset_id = payload.get("asset_id")
            history  = payload.get("history", [])

            # Delegate to agent service (imported lazily to avoid circular imports)
            try:
                from services.agent_service import AgentService
                agent = AgentService()

                async for chunk in agent.stream_response(
                    session_id=session_id,
                    message=user_message,
                    asset_id=asset_id,
                    history=history,
                ):
                    await manager.send_personal(ws, chunk)

            except Exception as e:
                logger.exception("Agent error session=%s", session_id)
                await manager.send_personal(ws, {
                    "type":       "agent_error",
                    "session_id": session_id,
                    "detail":     str(e),
                })

    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
        logger.info("WS agent session closed: %s", session_id)
