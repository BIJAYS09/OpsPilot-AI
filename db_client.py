"""
DB Client — Energy Co-pilot
============================
Import this in your FastAPI app.  Provides typed query helpers for
TimescaleDB and Qdrant so agents and API routes don't write raw SQL.

Usage:
    from db_client import TimeScaleClient, QdrantRAGClient

    ts  = TimeScaleClient()
    rag = QdrantRAGClient()

    # Latest 50 alerts for a turbine
    rows = ts.get_recent_alerts("TRB-001", limit=50)

    # RAG: find relevant docs about bearing failure
    hits = rag.search("turbine bearing temperature rising", asset_type="turbine")
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env.example")


# ─── TimescaleDB client ───────────────────────────────────────────────────────

class TimeScaleClient:
    """
    Thin wrapper around psycopg2 with connection pooling (SimpleConnectionPool).
    All methods return plain dicts — easy to serialise in FastAPI responses.
    """

    def __init__(self):
        import psycopg2
        from psycopg2 import pool
        self._pool = pool.SimpleConnectionPool(
            minconn=1, maxconn=10,
            host=os.getenv("TIMESCALE_HOST", "localhost"),
            port=int(os.getenv("TIMESCALE_PORT", 5432)),
            dbname=os.getenv("TIMESCALE_DB", "energy_copilot"),
            user=os.getenv("TIMESCALE_USER", "postgres"),
            password=os.getenv("TIMESCALE_PASSWORD", "yourpassword"),
        )

    def _query(self, sql: str, params=None) -> list[dict]:
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
        finally:
            self._pool.putconn(conn)

    # ── Sensor queries ────────────────────────────────────────────────────────

    def get_latest_readings(self, asset_id: str, sensors: Optional[list] = None) -> list[dict]:
        """Most recent reading per sensor for an asset."""
        sensor_filter = "AND sensor = ANY(%s)" if sensors else ""
        params = (asset_id, sensors) if sensors else (asset_id,)
        return self._query(f"""
            SELECT DISTINCT ON (sensor)
                time, asset_id, sensor, value, unit, alert_level,
                is_failure, failure_name, rul_hours
            FROM sensor_readings
            WHERE asset_id = %s {sensor_filter}
            ORDER BY sensor, time DESC
        """, params)

    def get_sensor_history(
        self,
        asset_id: str,
        sensor: str,
        hours: int = 24,
        interval: str = "5 minutes",
    ) -> list[dict]:
        """Time-bucketed average for a sensor over the last N hours."""
        return self._query("""
            SELECT
                time_bucket(%s, time) AS bucket,
                AVG(value)            AS avg_value,
                MIN(value)            AS min_value,
                MAX(value)            AS max_value,
                alert_level
            FROM sensor_readings
            WHERE asset_id = %s
              AND sensor    = %s
              AND time > NOW() - (%s || ' hours')::interval
              AND value IS NOT NULL
            GROUP BY bucket, alert_level
            ORDER BY bucket ASC
        """, (interval, asset_id, sensor, str(hours)))

    def get_recent_alerts(
        self,
        asset_id: Optional[str] = None,
        level: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch WARNING/CRITICAL readings across all or one asset."""
        conditions = ["time > NOW() - (%s || ' hours')::interval",
                      "alert_level != 'NORMAL'"]
        params: list = [str(hours)]
        if asset_id:
            conditions.append("asset_id = %s")
            params.append(asset_id)
        if level:
            conditions.append("alert_level = %s")
            params.append(level)
        params.append(limit)
        where = " AND ".join(conditions)
        return self._query(f"""
            SELECT time, asset_id, sensor, value, unit, alert_level,
                   is_failure, failure_name, rul_hours
            FROM sensor_readings
            WHERE {where}
            ORDER BY time DESC
            LIMIT %s
        """, params)

    def get_asset_health_summary(self) -> list[dict]:
        """Per-asset: latest alert level, active failure, min RUL."""
        return self._query("""
            WITH latest AS (
                SELECT DISTINCT ON (asset_id, sensor)
                    asset_id, sensor, value, alert_level,
                    is_failure, failure_name, rul_hours, time
                FROM sensor_readings
                ORDER BY asset_id, sensor, time DESC
            )
            SELECT
                l.asset_id,
                a.asset_type,
                a.site,
                MAX(CASE WHEN l.alert_level = 'CRITICAL' THEN 2
                         WHEN l.alert_level = 'WARNING'  THEN 1 ELSE 0 END) AS severity_score,
                BOOL_OR(l.is_failure)                                        AS has_active_failure,
                MAX(l.failure_name)                                           AS failure_name,
                MIN(l.rul_hours) FILTER (WHERE l.rul_hours IS NOT NULL)      AS min_rul_hours,
                MAX(l.time)                                                   AS last_updated
            FROM latest l
            JOIN assets a USING (asset_id)
            GROUP BY l.asset_id, a.asset_type, a.site
            ORDER BY severity_score DESC, min_rul_hours ASC NULLS LAST
        """)

    def get_failure_timeline(self, asset_id: str) -> list[dict]:
        """First and last occurrence of each failure for an asset."""
        return self._query("""
            SELECT
                asset_id,
                failure_name,
                MIN(time) AS first_detected,
                MAX(time) AS last_seen,
                COUNT(*)  AS affected_readings,
                MIN(rul_hours) FILTER (WHERE rul_hours IS NOT NULL) AS min_rul_hours
            FROM sensor_readings
            WHERE asset_id = %s AND is_failure = TRUE
            GROUP BY asset_id, failure_name
            ORDER BY first_detected
        """, (asset_id,))

    # ── Energy queries ────────────────────────────────────────────────────────

    def get_energy_summary(self, days: int = 7) -> list[dict]:
        """Daily MWh totals per site for the last N days."""
        return self._query("""
            SELECT
                time_bucket('1 day', time) AS day,
                site,
                ROUND(SUM(energy_mwh)::numeric, 2) AS total_mwh,
                ROUND(AVG(power_mw)::numeric, 2)   AS avg_power_mw,
                ROUND(MAX(power_mw)::numeric, 2)   AS peak_power_mw,
                ROUND(AVG(availability) * 100, 1)  AS availability_pct
            FROM energy_readings
            WHERE time > NOW() - (%s || ' days')::interval
            GROUP BY day, site
            ORDER BY day DESC, site
        """, (str(days),))

    # ── Maintenance queries ───────────────────────────────────────────────────

    def get_maintenance_history(
        self,
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        conditions = []
        params = []
        if asset_id:
            conditions.append("asset_id = %s")
            params.append(asset_id)
        if status:
            conditions.append("status = %s")
            params.append(status)
        params.append(limit)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        return self._query(f"""
            SELECT log_id, asset_id, site, log_type, severity, status,
                   technician, description, created_at, completed_at,
                   cost_eur, parts_replaced
            FROM maintenance_logs
            {where}
            ORDER BY created_at DESC
            LIMIT %s
        """, params)

    def get_maintenance_cost_summary(self) -> list[dict]:
        return self._query("""
            SELECT
                asset_id,
                severity,
                COUNT(*)              AS total_jobs,
                ROUND(SUM(cost_eur)::numeric, 2)  AS total_cost_eur,
                ROUND(AVG(cost_eur)::numeric, 2)  AS avg_cost_eur
            FROM maintenance_logs
            WHERE cost_eur IS NOT NULL
            GROUP BY asset_id, severity
            ORDER BY total_cost_eur DESC
        """)


# ─── Qdrant RAG client ────────────────────────────────────────────────────────

class QdrantRAGClient:
    """
    Search the energy_docs collection.
    Supports optional payload filters (asset_type, category, tags).
    """

    COLLECTION = "energy_docs"

    def __init__(self, backend: Optional[str] = None):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        self._Filter       = Filter
        self._FieldCond    = FieldCondition
        self._MatchVal     = MatchValue

        host    = os.getenv("QDRANT_HOST", "localhost")
        port    = int(os.getenv("QDRANT_PORT", 6333))
        api_key = os.getenv("QDRANT_API_KEY") or None
        self._client = QdrantClient(host=host, port=port, api_key=api_key)

        backend = backend or os.getenv("EMBEDDING_BACKEND", "sentence-transformers")
        self._embed = self._load_embedder(backend)

    @staticmethod
    def _load_embedder(backend: str):
        if backend == "sentence-transformers":
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(
                os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            )
            return lambda text: model.encode([text]).tolist()[0]
        elif backend == "openai":
            import openai
            client  = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            model   = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
            return lambda text: client.embeddings.create(
                input=[text], model=model
            ).data[0].embedding
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def search(
        self,
        query: str,
        asset_type: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 5,
        score_threshold: float = 0.35,
    ) -> list[dict]:
        """
        Semantic search with optional metadata filters.

        Args:
            query:           Natural language query
            asset_type:      "turbine" | "compressor" | "pump" | "all"
            category:        "incident_report" | "technical_bulletin" |
                             "root_cause_analysis" | "procedure"
            limit:           Max results
            score_threshold: Minimum cosine similarity (0–1)

        Returns:
            List of dicts with keys: score, title, section, category,
                                     asset_type, text, chunk_idx, doc_id
        """
        conditions = []
        if asset_type and asset_type != "all":
            conditions.append(
                self._FieldCond(key="asset_type",
                                match=self._MatchVal(value=asset_type))
            )
        if category:
            conditions.append(
                self._FieldCond(key="category",
                                match=self._MatchVal(value=category))
            )

        flt = self._Filter(must=conditions) if conditions else None

        hits = self._client.search(
            collection_name=self.COLLECTION,
            query_vector=self._embed(query),
            query_filter=flt,
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )

        return [
            {
                "score":      round(h.score, 4),
                "title":      h.payload.get("title", ""),
                "section":    h.payload.get("section", ""),
                "category":   h.payload.get("category", ""),
                "asset_type": h.payload.get("asset_type", ""),
                "tags":       h.payload.get("tags", []),
                "text":       h.payload.get("text", "")[:600],   # truncate for context
                "chunk_idx":  h.payload.get("chunk_idx", 0),
                "doc_id":     h.payload.get("doc_id", ""),
            }
            for h in hits
        ]

    def format_context(self, hits: list[dict], max_chars: int = 3000) -> str:
        """
        Formats search hits into a context string to inject into an LLM prompt.
        Each hit includes source title and section for citation.
        """
        parts = []
        total = 0
        for i, h in enumerate(hits, 1):
            snippet = (
                f"[Source {i}] {h['title']} — {h['section']}\n"
                f"(Relevance: {h['score']:.2f} | Category: {h['category']})\n"
                f"{h['text']}\n"
            )
            if total + len(snippet) > max_chars:
                break
            parts.append(snippet)
            total += len(snippet)
        return "\n---\n".join(parts)
