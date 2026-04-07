"""
Background Broadcaster
======================
Two async tasks run for the lifetime of the app:

1. sensor_broadcaster  — every WS_SENSOR_PUSH_SECONDS, fetches the latest
   sensor readings for each asset from TimescaleDB and pushes them to the
   correct channels ("sensors:{asset_id}" and "sensors:all").

2. alert_broadcaster   — every 10 s, fetches WARNING/CRITICAL readings from
   the last minute and pushes them to the "alerts" channel.

Both tasks simulate "live" data by replaying from the CSV when no real SCADA
stream is connected — this is correct behaviour for a demo / development env.
"""

import asyncio
import logging
from datetime import datetime, timezone

from api.websockets.manager import manager
from services.sensor_service import SensorService, AssetService
from core.config import get_settings

logger   = logging.getLogger(__name__)
settings = get_settings()

ASSET_IDS: list[str] = []   # populated at startup


async def _load_asset_ids() -> None:
    global ASSET_IDS
    try:
        assets   = AssetService.get_all()
        ASSET_IDS = [a["asset_id"] for a in assets]
        logger.info("Broadcaster: tracking %d assets", len(ASSET_IDS))
    except Exception as e:
        logger.warning("Could not load asset IDs (DB not ready?): %s — using defaults", e)
        ASSET_IDS = ["TRB-001", "TRB-002", "TRB-003",
                     "CMP-001", "CMP-002", "PMP-001", "PMP-002"]


async def sensor_broadcaster() -> None:
    """
    Push sensor_update messages to:
      - "sensors:{asset_id}"  subscribers (scoped to one asset)
      - "sensors:all"         subscribers (full plant view)
    """
    await _load_asset_ids()
    interval = settings.WS_SENSOR_PUSH_SECONDS

    while True:
        await asyncio.sleep(interval)

        # Skip work if nobody is listening
        stats = manager.stats()
        if not any(ch.startswith("sensors") for ch in stats):
            continue

        for asset_id in ASSET_IDS:
            channel = f"sensors:{asset_id}"
            # Only query DB if at least one client watches this asset or "all"
            if not (stats.get(channel) or stats.get("sensors:all")):
                continue

            try:
                readings = await SensorService.get_latest_async(asset_id)
                if not readings:
                    continue

                msg = {
                    "type":      "sensor_update",
                    "asset_id":  asset_id,
                    "readings":  readings,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                await manager.broadcast_multi([channel, "sensors:all"], msg)

            except Exception as e:
                logger.error("sensor_broadcaster error asset=%s: %s", asset_id, e)


async def alert_broadcaster() -> None:
    """
    Push alert_fired messages to the "alerts" channel.
    Deduplicates within a 60-second window so clients don't get spammed.
    """
    seen: set[str] = set()   # "asset_id:sensor:bucket_minute" already sent

    while True:
        await asyncio.sleep(10)

        if not manager.stats().get("alerts"):
            seen.clear()
            continue

        try:
            alerts = await SensorService.get_alerts_async(hours=1, limit=100)
            for alert in alerts:
                # Deduplicate key: asset + sensor + minute bucket
                t   = alert.get("time")
                key = f"{alert['asset_id']}:{alert['sensor']}:{t.strftime('%Y%m%d%H%M') if t else 'x'}"
                if key in seen:
                    continue
                seen.add(key)

                msg = {
                    "type":         "alert_fired",
                    "asset_id":     alert["asset_id"],
                    "sensor":       alert["sensor"],
                    "value":        alert.get("value"),
                    "alert_level":  alert["alert_level"],
                    "failure_name": alert.get("failure_name"),
                    "rul_hours":    alert.get("rul_hours"),
                    "timestamp":    t.isoformat() if t else None,
                }
                await manager.broadcast("alerts", msg)

            # Trim seen set to avoid unbounded growth
            if len(seen) > 5000:
                seen.clear()

        except Exception as e:
            logger.error("alert_broadcaster error: %s", e)


async def heartbeat_broadcaster() -> None:
    """Sends a heartbeat to every connected client every 30 s."""
    interval = settings.WS_HEARTBEAT_SECONDS
    while True:
        await asyncio.sleep(interval)
        if manager.total_connections == 0:
            continue
        msg = {
            "type":        "heartbeat",
            "server_time": datetime.now(timezone.utc).isoformat(),
            "connections": manager.total_connections,
        }
        # Broadcast to all known channels
        for ch in list(manager.stats().keys()):
            await manager.broadcast(ch, msg)


async def start_broadcasters() -> None:
    """Called from app lifespan — launches all background tasks."""
    asyncio.create_task(sensor_broadcaster(),   name="sensor_broadcaster")
    asyncio.create_task(alert_broadcaster(),    name="alert_broadcaster")
    asyncio.create_task(heartbeat_broadcaster(),name="heartbeat_broadcaster")
    logger.info("Background broadcasters started.")
