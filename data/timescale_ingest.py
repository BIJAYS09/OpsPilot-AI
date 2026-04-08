"""
TimescaleDB Ingestion — Energy Co-pilot
=======================================
Creates all tables (hypertables for time-series), indexes, and
continuous aggregates, then bulk-loads the three CSV files.

Run:
    python timescale_ingest.py
    python timescale_ingest.py --drop   # wipe + recreate first

Tables created
--------------
  sensor_readings   → hypertable (partitioned by time, 1-day chunks)
  maintenance_logs  → standard relational table
  energy_readings   → hypertable (partitioned by time, 1-day chunks)

Continuous aggregates (materialised views updated automatically)
  sensor_hourly     → hourly avg/min/max per asset+sensor
  energy_daily      → daily totals per asset
"""

import os
import sys
import argparse
import time
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv(Path(__file__).parent / ".env.example")

# ─── Connection ──────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(
        host=os.getenv("TIMESCALE_HOST", "localhost"),
        port=int(os.getenv("TIMESCALE_PORT", 5432)),
        dbname=os.getenv("TIMESCALE_DB", "energy_copilot"),
        user=os.getenv("TIMESCALE_USER", "postgres"),
        password=os.getenv("TIMESCALE_PASSWORD", "yourpassword"),
    )

# ─── DDL ─────────────────────────────────────────────────────────────────────

DROP_SQL = """
DROP TABLE IF EXISTS sensor_readings CASCADE;
DROP TABLE IF EXISTS maintenance_logs CASCADE;
DROP TABLE IF EXISTS energy_readings CASCADE;
"""

SCHEMA_SQL = """
-- ── TimescaleDB extension ─────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── Assets lookup (reference table) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS assets (
    asset_id        TEXT PRIMARY KEY,
    asset_type      TEXT NOT NULL,          -- turbine | compressor | pump
    site            TEXT NOT NULL,
    nominal_power   NUMERIC,
    unit            TEXT,
    installed_at    TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

-- ── Sensor readings (time-series hypertable) ──────────────────────────────
CREATE TABLE IF NOT EXISTS sensor_readings (
    time            TIMESTAMPTZ     NOT NULL,
    asset_id        TEXT            NOT NULL REFERENCES assets(asset_id),
    sensor          TEXT            NOT NULL,
    value           DOUBLE PRECISION,           -- NULL during maintenance
    unit            TEXT,
    alert_level     TEXT            NOT NULL DEFAULT 'NORMAL',
                                                -- NORMAL|WARNING|CRITICAL|MAINTENANCE
    is_failure      BOOLEAN         DEFAULT FALSE,
    failure_name    TEXT,
    rul_hours       DOUBLE PRECISION            -- remaining useful life estimate
);

-- Convert to hypertable (1-day chunks = fast range queries per day/week)
SELECT create_hypertable(
    'sensor_readings', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Indexes tuned for the most common query patterns
CREATE INDEX IF NOT EXISTS idx_sr_asset_time
    ON sensor_readings (asset_id, time DESC);

CREATE INDEX IF NOT EXISTS idx_sr_sensor_time
    ON sensor_readings (sensor, time DESC);

CREATE INDEX IF NOT EXISTS idx_sr_alert
    ON sensor_readings (alert_level, time DESC)
    WHERE alert_level IN ('WARNING', 'CRITICAL');

CREATE INDEX IF NOT EXISTS idx_sr_failure
    ON sensor_readings (asset_id, failure_name, time DESC)
    WHERE is_failure = TRUE;

-- ── Maintenance logs (relational) ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_logs (
    log_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id        TEXT            NOT NULL REFERENCES assets(asset_id),
    asset_type      TEXT,
    site            TEXT,
    log_type        TEXT,
    severity        TEXT,           -- LOW | MEDIUM | HIGH | CRITICAL
    status          TEXT,           -- COMPLETED | IN_PROGRESS | PENDING
    technician      TEXT,
    description     TEXT,
    created_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    cost_eur        NUMERIC(10, 2),
    parts_replaced  TEXT
);

CREATE INDEX IF NOT EXISTS idx_ml_asset  ON maintenance_logs (asset_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ml_status ON maintenance_logs (status, severity);

-- ── Energy readings (time-series hypertable) ──────────────────────────────
CREATE TABLE IF NOT EXISTS energy_readings (
    time            TIMESTAMPTZ     NOT NULL,
    asset_id        TEXT            NOT NULL REFERENCES assets(asset_id),
    site            TEXT,
    power_mw        DOUBLE PRECISION,
    energy_mwh      DOUBLE PRECISION,
    frequency_hz    DOUBLE PRECISION,
    voltage_kv      DOUBLE PRECISION,
    availability    SMALLINT        DEFAULT 1   -- 1 = online, 0 = offline
);

SELECT create_hypertable(
    'energy_readings', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_er_asset_time
    ON energy_readings (asset_id, time DESC);
"""

CAGG_SQL = """
-- ── Continuous aggregate: hourly sensor stats ─────────────────────────────
-- Refreshes automatically as new data arrives (no cron needed)
CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_hourly
WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time)     AS bucket,
        asset_id,
        sensor,
        AVG(value)                      AS avg_value,
        MIN(value)                      AS min_value,
        MAX(value)                      AS max_value,
        COUNT(*)                        AS sample_count,
        COUNT(*) FILTER (WHERE alert_level = 'WARNING')   AS warnings,
        COUNT(*) FILTER (WHERE alert_level = 'CRITICAL')  AS criticals
    FROM sensor_readings
    WHERE value IS NOT NULL
    GROUP BY bucket, asset_id, sensor
WITH NO DATA;

-- Auto-refresh policy: keep last 30 days up-to-date, refresh every hour
SELECT add_continuous_aggregate_policy('sensor_hourly',
    start_offset => INTERVAL '30 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ── Continuous aggregate: daily energy totals ─────────────────────────────
CREATE MATERIALIZED VIEW IF NOT EXISTS energy_daily
WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 day', time)      AS bucket,
        asset_id,
        site,
        SUM(energy_mwh)                 AS total_mwh,
        AVG(power_mw)                   AS avg_power_mw,
        MAX(power_mw)                   AS peak_power_mw,
        AVG(frequency_hz)               AS avg_freq_hz,
        SUM(availability) * 15.0 / 60  AS available_hours   -- 15-min intervals
    FROM energy_readings
    GROUP BY bucket, asset_id, site
WITH NO DATA;

SELECT add_continuous_aggregate_policy('energy_daily',
    start_offset => INTERVAL '60 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '6 hours',
    if_not_exists => TRUE
);
"""

ASSET_INSERT_SQL = """
INSERT INTO assets (asset_id, asset_type, site, nominal_power, unit) VALUES %s
ON CONFLICT (asset_id) DO NOTHING;
"""

ASSETS_DATA = [
    ("TRB-001", "turbine",    "Alpha Plant",  50,  "MW"),
    ("TRB-002", "turbine",    "Alpha Plant",  50,  "MW"),
    ("TRB-003", "turbine",    "Beta Station", 80,  "MW"),
    ("CMP-001", "compressor", "Alpha Plant",  12,  "bar"),
    ("CMP-002", "compressor", "Beta Station", 15,  "bar"),
    ("PMP-001", "pump",       "Alpha Plant",  200, "m3h"),
    ("PMP-002", "pump",       "Beta Station", 180, "m3h"),
]

# ─── Loaders ─────────────────────────────────────────────────────────────────

BATCH = 5_000   # rows per INSERT batch — safe for all three tables


def load_sensor_readings(conn, csv_path: Path):
    print(f"\n[1/3] Loading sensor_readings from {csv_path.name} ...")
    df = pd.read_csv(csv_path, parse_dates=["timestamp"], low_memory=False)
    df = df.rename(columns={
        "timestamp": "time",
        "is_failure_active": "is_failure",
    })

    # Cast types explicitly
    df["time"]         = pd.to_datetime(df["time"], utc=True)
    df["is_failure"]   = df["is_failure"].astype(bool)
    df["value"]        = pd.to_numeric(df["value"], errors="coerce")
    df["rul_hours"]    = pd.to_numeric(df["rul_hours"], errors="coerce")

    cols = ["time", "asset_id", "sensor", "value", "unit",
            "alert_level", "is_failure", "failure_name", "rul_hours"]
    df = df[cols]

    sql = """
        INSERT INTO sensor_readings
            (time, asset_id, sensor, value, unit,
             alert_level, is_failure, failure_name, rul_hours)
        VALUES %s
        ON CONFLICT DO NOTHING
    """

    rows = list(df.itertuples(index=False, name=None))
    with conn.cursor() as cur:
        for i in tqdm(range(0, len(rows), BATCH), desc="  sensor batches", unit="batch"):
            batch = rows[i: i + BATCH]
            execute_values(cur, sql, batch, page_size=BATCH)
    conn.commit()
    print(f"  ✓ {len(df):,} rows committed.")


def load_maintenance_logs(conn, csv_path: Path):
    print(f"\n[2/3] Loading maintenance_logs from {csv_path.name} ...")
    df = pd.read_csv(csv_path, parse_dates=["created_at", "completed_at"])

    df["created_at"]   = df["created_at"].where(df["completed_at"].notna(), None)
    df["completed_at"] = df["completed_at"].where(df["completed_at"].notna(), None)
    df["cost_eur"]     = pd.to_numeric(df["cost_eur"], errors="coerce")
    df = df.astype(object).where(pd.notnull(df), None)  # replace NaN → None (SQL NULL)

    cols = ["log_id", "asset_id", "asset_type", "site", "log_type",
            "severity", "status", "technician", "description",
            "created_at", "completed_at", "cost_eur", "parts_replaced"]
    df = df[cols]

    sql = """
        INSERT INTO maintenance_logs
            (log_id, asset_id, asset_type, site, log_type,
             severity, status, technician, description,
             created_at, completed_at, cost_eur, parts_replaced)
        VALUES %s
        ON CONFLICT (log_id) DO NOTHING
    """

    rows = list(df.itertuples(index=False, name=None))
    with conn.cursor() as cur:
        for i in tqdm(range(0, len(rows), BATCH), desc="  maint batches", unit="batch"):
            execute_values(cur, sql, rows[i: i + BATCH], page_size=BATCH)
    conn.commit()
    print(f"  ✓ {len(df):,} rows committed.")


def load_energy_readings(conn, csv_path: Path):
    print(f"\n[3/3] Loading energy_readings from {csv_path.name} ...")
    df = pd.read_csv(csv_path, parse_dates=["timestamp"])

    df["timestamp"]   = pd.to_datetime(df["timestamp"], utc=True)
    df["power_mw"]    = pd.to_numeric(df["power_mw"],    errors="coerce")
    df["energy_mwh"]  = pd.to_numeric(df["energy_mwh"],  errors="coerce")
    df["frequency_hz"]= pd.to_numeric(df["frequency_hz"],errors="coerce")
    df["voltage_kv"]  = pd.to_numeric(df["voltage_kv"],  errors="coerce")
    df["availability"]= df["availability"].astype(int)
    df = df.rename(columns={"timestamp": "time"})

    cols = ["time", "asset_id", "site", "power_mw",
            "energy_mwh", "frequency_hz", "voltage_kv", "availability"]
    df = df[cols]

    sql = """
        INSERT INTO energy_readings
            (time, asset_id, site, power_mw,
             energy_mwh, frequency_hz, voltage_kv, availability)
        VALUES %s
        ON CONFLICT DO NOTHING
    """

    rows = list(df.itertuples(index=False, name=None))
    with conn.cursor() as cur:
        for i in tqdm(range(0, len(rows), BATCH), desc="  energy batches", unit="batch"):
            execute_values(cur, sql, rows[i: i + BATCH], page_size=BATCH)
    conn.commit()
    print(f"  ✓ {len(df):,} rows committed.")


# ─── Verification queries ─────────────────────────────────────────────────────

VERIFY_SQL = {
    "sensor_readings row count":
        "SELECT COUNT(*) FROM sensor_readings",
    "sensor alert distribution":
        "SELECT alert_level, COUNT(*) FROM sensor_readings GROUP BY 1 ORDER BY 2 DESC",
    "active failures (latest)":
        """SELECT asset_id, failure_name, MAX(time) AS last_seen
           FROM sensor_readings WHERE is_failure = TRUE
           GROUP BY 1,2 ORDER BY 3 DESC""",
    "maintenance log summary":
        "SELECT severity, status, COUNT(*) FROM maintenance_logs GROUP BY 1,2 ORDER BY 1,2",
    "energy totals by site":
        """SELECT site, ROUND(SUM(energy_mwh)::numeric, 1) AS total_mwh
           FROM energy_readings GROUP BY site""",
    "hypertable chunks created":
        """SELECT hypertable_name, num_chunks
           FROM timescaledb_information.hypertables
           WHERE hypertable_name IN ('sensor_readings','energy_readings')""",
}


def run_verification(conn):
    print("\n── Verification queries ──────────────────────────────────")
    with conn.cursor() as cur:
        for label, sql in VERIFY_SQL.items():
            cur.execute(sql)
            rows = cur.fetchall()
            print(f"\n  {label}:")
            for r in rows:
                print("   ", " | ".join(str(c) for c in r))


# ─── Entrypoint ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Load synthetic data into TimescaleDB")
    parser.add_argument("--drop", action="store_true",
                        help="Drop and recreate all tables before loading")
    parser.add_argument("--skip-cagg", action="store_true",
                        help="Skip continuous aggregate creation (faster for dev)")
    args = parser.parse_args()

    data_dir = Path(os.getenv("DATA_DIR", "./data"))
    if not (data_dir / "sensor_readings.csv").exists():
        print(f"ERROR: {data_dir / 'sensor_readings.csv'} not found.")
        print("Run sensor_generator.py first.")
        sys.exit(1)

    print("Connecting to TimescaleDB ...")
    try:
        conn = get_conn()
        print(f"  ✓ Connected to {os.getenv('TIMESCALE_DB')} @ {os.getenv('TIMESCALE_HOST')}")
    except Exception as e:
        print(f"\nERROR: Cannot connect to TimescaleDB: {e}")
        print("Make sure Docker is running:  docker compose up -d timescaledb")
        sys.exit(1)

    with conn.cursor() as cur:
        if args.drop:
            print("\nDropping existing tables ...")
            cur.execute(DROP_SQL)
            conn.commit()

        print("\nApplying schema ...")
        cur.execute(SCHEMA_SQL)
        conn.commit()

        print("Inserting asset catalogue ...")
        execute_values(cur, ASSET_INSERT_SQL, ASSETS_DATA)
        conn.commit()

        if not args.skip_cagg:
            print("Creating continuous aggregates ...")
            cur.execute(CAGG_SQL)
            conn.commit()

    t0 = time.time()
    load_sensor_readings(conn, data_dir / "sensor_readings.csv")
    load_maintenance_logs(conn, data_dir / "maintenance_logs.csv")
    load_energy_readings(conn, data_dir / "energy_readings.csv")

    elapsed = time.time() - t0
    print(f"\n  Total load time: {elapsed:.1f}s")

    run_verification(conn)
    conn.close()
    print("\nDone. TimescaleDB is ready.")


if __name__ == "__main__":
    main()
