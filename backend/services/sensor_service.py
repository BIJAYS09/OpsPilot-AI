"""
Sensor service — all TimescaleDB queries for sensor data.
Called by REST routes and the WebSocket broadcaster.
"""

from datetime import datetime
from typing import Optional
from core.database import query_sync, query_async


class SensorService:

    # ── Latest readings ───────────────────────────────────────────────────────

    @staticmethod
    def get_latest(asset_id: str, sensors: Optional[list[str]] = None) -> list[dict]:
        """Most recent value per sensor for one asset."""
        if sensors:
            return query_sync("""
                SELECT DISTINCT ON (sensor)
                    time, asset_id, sensor, value, unit,
                    alert_level, is_failure, failure_name, rul_hours
                FROM sensor_readings
                WHERE asset_id = %s AND sensor = ANY(%s)
                ORDER BY sensor, time DESC
            """, (asset_id, sensors))
        return query_sync("""
            SELECT DISTINCT ON (sensor)
                time, asset_id, sensor, value, unit,
                alert_level, is_failure, failure_name, rul_hours
            FROM sensor_readings
            WHERE asset_id = %s
            ORDER BY sensor, time DESC
        """, (asset_id,))

    # ── History (bucketed) ────────────────────────────────────────────────────

    @staticmethod
    def get_history(
        asset_id: str,
        sensor: str,
        hours: int = 24,
        interval: str = "15 minutes",
    ) -> list[dict]:
        return query_sync("""
            SELECT
                time_bucket(%s, time)   AS bucket,
                ROUND(AVG(value)::numeric, 4)  AS avg_value,
                ROUND(MIN(value)::numeric, 4)  AS min_value,
                ROUND(MAX(value)::numeric, 4)  AS max_value,
                mode() WITHIN GROUP (ORDER BY alert_level) AS alert_level
            FROM sensor_readings
            WHERE asset_id = %s
              AND sensor    = %s
              AND time > NOW() - (%s || ' hours')::interval
              AND value IS NOT NULL
            GROUP BY bucket
            ORDER BY bucket ASC
        """, (interval, asset_id, sensor, str(hours)))

    # ── Alerts ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_alerts(
        asset_id: Optional[str] = None,
        level: Optional[str] = None,
        hours: int = 24,
        limit: int = 200,
    ) -> list[dict]:
        conditions = [
            "time > NOW() - (%s || ' hours')::interval",
            "alert_level IN ('WARNING','CRITICAL')",
        ]
        params: list = [str(hours)]
        if asset_id:
            conditions.append("asset_id = %s")
            params.append(asset_id)
        if level:
            conditions.append("alert_level = %s")
            params.append(level.upper())
        params.append(limit)

        return query_sync(f"""
            SELECT time, asset_id, sensor, value, unit,
                   alert_level, is_failure, failure_name, rul_hours
            FROM sensor_readings
            WHERE {' AND '.join(conditions)}
            ORDER BY time DESC
            LIMIT %s
        """, params)

    # ── Health summary ────────────────────────────────────────────────────────

    @staticmethod
    def get_health_summary() -> list[dict]:
        return query_sync("""
            WITH latest AS (
                SELECT DISTINCT ON (asset_id, sensor)
                    asset_id, alert_level, is_failure,
                    failure_name, rul_hours, time
                FROM sensor_readings
                ORDER BY asset_id, sensor, time DESC
            )
            SELECT
                l.asset_id,
                a.asset_type,
                a.site,
                MAX(CASE
                    WHEN l.alert_level = 'CRITICAL' THEN 2
                    WHEN l.alert_level = 'WARNING'  THEN 1
                    ELSE 0 END)                                     AS severity_score,
                BOOL_OR(l.is_failure)                               AS has_active_failure,
                MAX(l.failure_name)                                  AS failure_name,
                MIN(l.rul_hours) FILTER (WHERE l.rul_hours IS NOT NULL) AS min_rul_hours,
                MAX(l.time)                                          AS last_updated
            FROM latest l
            JOIN assets a USING (asset_id)
            GROUP BY l.asset_id, a.asset_type, a.site
            ORDER BY severity_score DESC, min_rul_hours ASC NULLS LAST
        """)

    # ── Failure timeline ──────────────────────────────────────────────────────

    @staticmethod
    def get_failure_timeline(asset_id: str) -> list[dict]:
        return query_sync("""
            SELECT
                asset_id,
                failure_name,
                MIN(time)   AS first_detected,
                MAX(time)   AS last_seen,
                COUNT(*)    AS affected_readings,
                MIN(rul_hours) FILTER (WHERE rul_hours IS NOT NULL) AS min_rul_hours
            FROM sensor_readings
            WHERE asset_id = %s AND is_failure = TRUE
            GROUP BY asset_id, failure_name
            ORDER BY first_detected
        """, (asset_id,))

    # ── Async variants used by WebSocket broadcaster ──────────────────────────

    @staticmethod
    async def get_latest_async(asset_id: str) -> list[dict]:
        return await query_async("""
            SELECT DISTINCT ON (sensor)
                time, asset_id, sensor, value, unit,
                alert_level, is_failure, failure_name, rul_hours
            FROM sensor_readings
            WHERE asset_id = %s
            ORDER BY sensor, time DESC
        """, (asset_id,))

    @staticmethod
    async def get_alerts_async(hours: int = 1, limit: int = 50) -> list[dict]:
        return await query_async("""
            SELECT time, asset_id, sensor, value, unit,
                   alert_level, is_failure, failure_name, rul_hours
            FROM sensor_readings
            WHERE time > NOW() - (%s || ' hours')::interval
              AND alert_level IN ('WARNING','CRITICAL')
            ORDER BY time DESC
            LIMIT %s
        """, (str(hours), limit))


class EnergyService:

    @staticmethod
    def get_summary(days: int = 7) -> list[dict]:
        return query_sync("""
            SELECT
                time_bucket('1 day', time)                   AS day,
                site,
                ROUND(SUM(energy_mwh)::numeric, 2)           AS total_mwh,
                ROUND(AVG(power_mw)::numeric,   2)           AS avg_power_mw,
                ROUND(MAX(power_mw)::numeric,   2)           AS peak_power_mw,
                ROUND(AVG(availability) * 100,  1)           AS availability_pct
            FROM energy_readings
            WHERE time > NOW() - (%s || ' days')::interval
            GROUP BY day, site
            ORDER BY day DESC, site
        """, (str(days),))

    @staticmethod
    def get_live_power(asset_ids: Optional[list[str]] = None) -> list[dict]:
        if asset_ids:
            return query_sync("""
                SELECT DISTINCT ON (asset_id)
                    time, asset_id, site, power_mw, frequency_hz, availability
                FROM energy_readings
                WHERE asset_id = ANY(%s)
                ORDER BY asset_id, time DESC
            """, (asset_ids,))
        return query_sync("""
            SELECT DISTINCT ON (asset_id)
                time, asset_id, site, power_mw, frequency_hz, availability
            FROM energy_readings
            ORDER BY asset_id, time DESC
        """)


class MaintenanceService:

    @staticmethod
    def get_logs(
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        conditions, params = [], []
        if asset_id:
            conditions.append("asset_id = %s"); params.append(asset_id)
        if status:
            conditions.append("status = %s");   params.append(status.upper())
        params.append(limit)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return query_sync(f"""
            SELECT log_id, asset_id, site, log_type, severity, status,
                   technician, description, created_at, completed_at,
                   cost_eur, parts_replaced
            FROM maintenance_logs
            {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params)

    @staticmethod
    def get_cost_summary() -> list[dict]:
        return query_sync("""
            SELECT asset_id, severity,
                   COUNT(*)                          AS total_jobs,
                   ROUND(SUM(cost_eur)::numeric, 2) AS total_cost_eur,
                   ROUND(AVG(cost_eur)::numeric, 2) AS avg_cost_eur
            FROM maintenance_logs
            WHERE cost_eur IS NOT NULL
            GROUP BY asset_id, severity
            ORDER BY total_cost_eur DESC
        """)


class AssetService:

    @staticmethod
    def get_all() -> list[dict]:
        return query_sync("SELECT * FROM assets WHERE is_active = TRUE ORDER BY asset_id")

    @staticmethod
    def get_one(asset_id: str) -> Optional[dict]:
        rows = query_sync("SELECT * FROM assets WHERE asset_id = %s", (asset_id,))
        return rows[0] if rows else None
