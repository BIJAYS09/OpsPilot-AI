"""
Synthetic Industrial Sensor Data Generator
Energy / Industrial AI Co-pilot Project

Generates realistic time-series data for:
  - Turbines (vibration, RPM, temperature, power output)
  - Compressors (pressure, flow rate, temperature)
  - Pumps (flow, pressure, motor current)

Includes: normal operation, gradual degradation, sudden failures, maintenance windows
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from faker import Faker
import random
import json
from pathlib import Path

fake = Faker()
rng = np.random.default_rng(seed=42)

# ─── Asset catalogue ──────────────────────────────────────────────────────────

ASSETS = [
    {"id": "TRB-001", "type": "turbine",    "site": "Alpha Plant",  "unit": "MW",  "nominal_power": 50},
    {"id": "TRB-002", "type": "turbine",    "site": "Alpha Plant",  "unit": "MW",  "nominal_power": 50},
    {"id": "TRB-003", "type": "turbine",    "site": "Beta Station", "unit": "MW",  "nominal_power": 80},
    {"id": "CMP-001", "type": "compressor", "site": "Alpha Plant",  "unit": "bar", "nominal_power": 12},
    {"id": "CMP-002", "type": "compressor", "site": "Beta Station", "unit": "bar", "nominal_power": 15},
    {"id": "PMP-001", "type": "pump",       "site": "Alpha Plant",  "unit": "m3h", "nominal_power": 200},
    {"id": "PMP-002", "type": "pump",       "site": "Beta Station", "unit": "m3h", "nominal_power": 180},
]

# ─── Sensor specs per asset type ─────────────────────────────────────────────

SENSOR_SPECS = {
    "turbine": {
        "temperature_bearing":  {"nominal": 65.0,  "std": 3.0,  "unit": "°C",  "warn": 85,  "crit": 95},
        "temperature_exhaust":  {"nominal": 520.0, "std": 15.0, "unit": "°C",  "warn": 580, "crit": 620},
        "vibration_x":          {"nominal": 1.8,   "std": 0.3,  "unit": "mm/s","warn": 4.5, "crit": 7.1},
        "vibration_y":          {"nominal": 1.9,   "std": 0.3,  "unit": "mm/s","warn": 4.5, "crit": 7.1},
        "rotation_speed":       {"nominal": 3000,  "std": 10.0, "unit": "RPM", "warn": 3100,"crit": 3200},
        "power_output":         {"nominal": 1.0,   "std": 0.05, "unit": "pu",  "warn": 0.5, "crit": 0.3},
        "lube_oil_pressure":    {"nominal": 3.2,   "std": 0.2,  "unit": "bar", "warn": 2.5, "crit": 2.0},
    },
    "compressor": {
        "inlet_pressure":       {"nominal": 1.0,   "std": 0.05, "unit": "bar", "warn": 0.8, "crit": 0.6},
        "outlet_pressure":      {"nominal": 1.0,   "std": 0.04, "unit": "pu",  "warn": 0.8, "crit": 0.6},
        "temperature_stage1":   {"nominal": 90.0,  "std": 5.0,  "unit": "°C",  "warn": 120, "crit": 140},
        "temperature_stage2":   {"nominal": 140.0, "std": 6.0,  "unit": "°C",  "warn": 175, "crit": 195},
        "vibration":            {"nominal": 2.1,   "std": 0.4,  "unit": "mm/s","warn": 5.0, "crit": 8.0},
        "motor_current":        {"nominal": 1.0,   "std": 0.06, "unit": "pu",  "warn": 1.15,"crit": 1.3},
        "flow_rate":            {"nominal": 1.0,   "std": 0.04, "unit": "pu",  "warn": 0.7, "crit": 0.5},
    },
    "pump": {
        "flow_rate":            {"nominal": 1.0,   "std": 0.05, "unit": "pu",  "warn": 0.7, "crit": 0.5},
        "inlet_pressure":       {"nominal": 2.0,   "std": 0.1,  "unit": "bar", "warn": 1.5, "crit": 1.2},
        "outlet_pressure":      {"nominal": 1.0,   "std": 0.04, "unit": "pu",  "warn": 0.75,"crit": 0.6},
        "motor_current":        {"nominal": 1.0,   "std": 0.05, "unit": "pu",  "warn": 1.2, "crit": 1.4},
        "temperature_bearing":  {"nominal": 55.0,  "std": 3.0,  "unit": "°C",  "warn": 75,  "crit": 85},
        "vibration":            {"nominal": 1.5,   "std": 0.3,  "unit": "mm/s","warn": 4.0, "crit": 6.5},
        "efficiency":           {"nominal": 0.88,  "std": 0.02, "unit": "%",   "warn": 0.75,"crit": 0.65},
    },
}

# ─── Failure scenario library ─────────────────────────────────────────────────

FAILURE_SCENARIOS = {
    "turbine": [
        {
            "name": "Bearing wear",
            "affected": ["vibration_x", "vibration_y", "temperature_bearing"],
            "drift_multiplier": [3.5, 3.2, 1.4],
            "onset_hours": 72,  # gradual onset over 72 hrs
        },
        {
            "name": "Blade fouling",
            "affected": ["power_output", "rotation_speed", "temperature_exhaust"],
            "drift_multiplier": [0.85, 0.97, 1.08],
            "onset_hours": 120,
        },
        {
            "name": "Lube oil leak",
            "affected": ["lube_oil_pressure", "temperature_bearing"],
            "drift_multiplier": [0.6, 1.5],
            "onset_hours": 24,
        },
    ],
    "compressor": [
        {
            "name": "Valve degradation",
            "affected": ["outlet_pressure", "temperature_stage1", "motor_current"],
            "drift_multiplier": [0.9, 1.25, 1.18],
            "onset_hours": 96,
        },
        {
            "name": "Intercooler fouling",
            "affected": ["temperature_stage2", "flow_rate"],
            "drift_multiplier": [1.3, 0.88],
            "onset_hours": 80,
        },
    ],
    "pump": [
        {
            "name": "Impeller wear",
            "affected": ["flow_rate", "efficiency", "vibration"],
            "drift_multiplier": [0.78, 0.82, 2.2],
            "onset_hours": 60,
        },
        {
            "name": "Seal failure",
            "affected": ["inlet_pressure", "motor_current", "temperature_bearing"],
            "drift_multiplier": [0.7, 1.25, 1.4],
            "onset_hours": 18,
        },
    ],
}

# ─── Core signal generator ────────────────────────────────────────────────────

def make_base_signal(nominal, std, n, asset_type, sensor_name):
    """Gaussian noise around nominal + low-freq drift + diurnal cycle."""
    noise = rng.normal(0, std, n)

    # Slow drift representing ageing / load changes
    drift = 0.3 * std * np.sin(np.linspace(0, 2 * np.pi, n))

    # Diurnal load cycle (turbines and compressors track grid demand)
    if asset_type in ("turbine", "compressor") and sensor_name in (
        "power_output", "rotation_speed", "outlet_pressure", "flow_rate"
    ):
        hours = np.linspace(0, n / 12, n)  # assuming 5-min samples
        diurnal = 0.04 * nominal * np.sin(2 * np.pi * (hours - 8) / 24)
    else:
        diurnal = 0.0

    return nominal + noise + drift + diurnal


def inject_failure(signal, spec, scenario, n_points, failure_start_idx):
    """
    Gradually drifts a signal from its nominal toward a failure value.
    Uses a sigmoid ramp so the early onset looks subtle (hard to spot manually).
    """
    onset_samples = max(1, int(scenario["onset_hours"] * 12))  # 5-min intervals
    ramp_end = min(failure_start_idx + onset_samples, n_points)
    ramp_len = ramp_end - failure_start_idx

    x = np.linspace(-6, 6, ramp_len)
    sigmoid = 1 / (1 + np.exp(-x))

    target_multiplier = scenario["drift_multiplier"][
        scenario["affected"].index(
            next(k for k in scenario["affected"] if k in spec)
        )
    ] if any(k in spec for k in scenario["affected"]) else 1.0

    nominal = spec["nominal"]
    target = nominal * target_multiplier

    modified = signal.copy()
    modified[failure_start_idx:ramp_end] = (
        nominal + sigmoid * (target - nominal) +
        rng.normal(0, spec["std"] * 0.5, ramp_len)
    )
    if ramp_end < n_points:
        modified[ramp_end:] = target + rng.normal(0, spec["std"] * 0.8, n_points - ramp_end)

    return modified


def get_alert_level(value, spec):
    lo = value < spec["nominal"]  # below nominal is bad for pressure/flow
    sensors_low_is_bad = {"power_output", "flow_rate", "efficiency",
                          "lube_oil_pressure", "inlet_pressure", "outlet_pressure"}

    sensor_key = None
    for k in sensors_low_is_bad:
        if k in str(spec):
            sensor_key = k
            break

    crit_val = spec["crit"]
    warn_val = spec["warn"]

    # For ratio sensors (pu), low values are bad
    if spec["unit"] in ("pu", "%") or spec.get("_key") in sensors_low_is_bad:
        if value <= crit_val:
            return "CRITICAL"
        elif value <= warn_val:
            return "WARNING"
    else:
        # High values are bad (temperature, vibration, pressure-high)
        if value >= crit_val:
            return "CRITICAL"
        elif value >= warn_val:
            return "WARNING"

    return "NORMAL"


# ─── Main generation function ─────────────────────────────────────────────────

def generate_asset_timeseries(asset, days=30, interval_minutes=5):
    """
    Returns a DataFrame with columns:
        timestamp, asset_id, asset_type, site, sensor, value, unit,
        alert_level, is_failure_active, failure_name, rul_hours
    """
    n = int(days * 24 * 60 / interval_minutes)
    timestamps = [
        datetime(2024, 1, 1) + timedelta(minutes=i * interval_minutes)
        for i in range(n)
    ]

    asset_type = asset["type"]
    specs = SENSOR_SPECS[asset_type]
    scenarios = FAILURE_SCENARIOS[asset_type]

    # Decide if / when failure happens (70% chance per asset over 30 days)
    failure_event = None
    if rng.random() < 0.70:
        scenario = random.choice(scenarios)
        failure_start_idx = int(rng.uniform(0.3, 0.8) * n)
        failure_event = {
            "scenario": scenario,
            "start_idx": failure_start_idx,
            "name": scenario["name"],
        }

    # Maintenance windows (2-4 per month, ~4-8 hrs each)
    maint_windows = []
    n_maint = rng.integers(2, 5)
    for _ in range(n_maint):
        start = int(rng.uniform(0, 0.95) * n)
        duration = int(rng.uniform(4, 9) * 60 / interval_minutes)
        maint_windows.append((start, start + duration))

    rows = []

    for sensor_name, spec in specs.items():
        signal = make_base_signal(spec["nominal"], spec["std"], n, asset_type, sensor_name)

        # Inject failure drift if this sensor is affected
        if failure_event and sensor_name in failure_event["scenario"]["affected"]:
            idx = failure_event["scenario"]["affected"].index(sensor_name)
            drift_mult = failure_event["scenario"]["drift_multiplier"][idx]
            onset_samples = max(1, int(failure_event["scenario"]["onset_hours"] * 12))
            fstart = failure_event["start_idx"]
            ramp_end = min(fstart + onset_samples, n)
            ramp_len = ramp_end - fstart

            x = np.linspace(-5, 5, ramp_len)
            sigmoid = 1 / (1 + np.exp(-x))
            target = spec["nominal"] * drift_mult

            signal[fstart:ramp_end] = (
                spec["nominal"] + sigmoid * (target - spec["nominal"]) +
                rng.normal(0, spec["std"] * 0.5, ramp_len)
            )
            if ramp_end < n:
                signal[ramp_end:] = target + rng.normal(0, spec["std"] * 0.8, n - ramp_end)

        for i in range(n):
            # Maintenance window → NaN / flat line (asset offline)
            in_maint = any(s <= i < e for s, e in maint_windows)
            if in_maint:
                value = None
                alert = "MAINTENANCE"
            else:
                value = round(float(signal[i]), 4)
                # Derive alert
                if spec["unit"] in ("pu", "%"):
                    if value <= spec["crit"]:
                        alert = "CRITICAL"
                    elif value <= spec["warn"]:
                        alert = "WARNING"
                    else:
                        alert = "NORMAL"
                else:
                    if value >= spec["crit"]:
                        alert = "CRITICAL"
                    elif value >= spec["warn"]:
                        alert = "WARNING"
                    else:
                        alert = "NORMAL"

            is_failure = (
                failure_event is not None and
                i >= failure_event["start_idx"] and
                sensor_name in failure_event["scenario"]["affected"]
            )

            # RUL estimate (hours until expected failure for affected sensors)
            if failure_event and sensor_name in failure_event["scenario"]["affected"]:
                rul = max(0, (failure_event["start_idx"] - i) * interval_minutes / 60)
            else:
                rul = None

            rows.append({
                "timestamp": timestamps[i],
                "asset_id": asset["id"],
                "asset_type": asset["type"],
                "site": asset["site"],
                "sensor": sensor_name,
                "value": value,
                "unit": spec["unit"],
                "alert_level": alert,
                "is_failure_active": is_failure,
                "failure_name": failure_event["name"] if is_failure else None,
                "rul_hours": round(rul, 1) if rul is not None else None,
            })

    return pd.DataFrame(rows)


def generate_maintenance_logs(assets, n_logs=120):
    """Generates a realistic maintenance log table."""
    log_types = [
        "Scheduled inspection", "Oil change", "Filter replacement",
        "Bearing replacement", "Vibration check", "Calibration",
        "Emergency repair", "Seal replacement", "Blade cleaning",
        "Pressure test", "Thermal imaging survey", "Lubrication service",
    ]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    statuses = ["COMPLETED", "COMPLETED", "COMPLETED", "PENDING", "IN_PROGRESS"]

    logs = []
    for _ in range(n_logs):
        asset = random.choice(assets)
        date = fake.date_time_between(start_date="-60d", end_date="now")
        severity = random.choices(severities, weights=[40, 35, 20, 5])[0]
        logs.append({
            "log_id": fake.uuid4(),
            "asset_id": asset["id"],
            "asset_type": asset["type"],
            "site": asset["site"],
            "log_type": random.choice(log_types),
            "severity": severity,
            "status": random.choice(statuses),
            "technician": fake.name(),
            "description": fake.sentence(nb_words=12),
            "created_at": date,
            "completed_at": date + timedelta(hours=rng.uniform(1, 8)) if random.random() > 0.2 else None,
            "cost_eur": round(rng.uniform(200, 15000), 2) if severity in ("HIGH", "CRITICAL") else round(rng.uniform(50, 1500), 2),
            "parts_replaced": random.choice([
                "Bearing set", "Oil filter", "Seal kit", "None",
                "Vibration sensor", "Pressure transducer", "None", "None",
            ]),
        })
    return pd.DataFrame(logs)


def generate_energy_readings(assets, days=30, interval_minutes=15):
    """15-min energy production/consumption readings per asset."""
    n = int(days * 24 * 60 / interval_minutes)
    timestamps = [
        datetime(2024, 1, 1) + timedelta(minutes=i * interval_minutes)
        for i in range(n)
    ]
    rows = []
    for asset in assets:
        nominal_mw = asset.get("nominal_power", 50)
        for i, ts in enumerate(timestamps):
            hour = ts.hour
            # Grid demand curve (peaks 8-10am and 6-8pm)
            demand_factor = 0.6 + 0.35 * (
                np.exp(-((hour - 9) ** 2) / 8) +
                np.exp(-((hour - 19) ** 2) / 8)
            )
            output = nominal_mw * demand_factor * rng.uniform(0.92, 1.04)
            rows.append({
                "timestamp": ts,
                "asset_id": asset["id"],
                "site": asset["site"],
                "power_mw": round(max(0, output), 3),
                "energy_mwh": round(max(0, output) * (interval_minutes / 60), 4),
                "frequency_hz": round(rng.normal(50.0, 0.05), 3),
                "voltage_kv": round(rng.normal(110, 0.5), 2),
                "availability": 1 if rng.random() > 0.02 else 0,
            })
    return pd.DataFrame(rows)


# ─── Run ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    output_dir = Path("./data")
    output_dir.mkdir(exist_ok=True)

    print("Generating sensor time-series...")
    all_sensor_dfs = []
    for asset in ASSETS:
        print(f"  → {asset['id']} ({asset['type']})")
        df = generate_asset_timeseries(asset, days=30)
        all_sensor_dfs.append(df)

    sensor_df = pd.concat(all_sensor_dfs, ignore_index=True)
    sensor_df.to_csv(output_dir / "sensor_readings.csv", index=False)
    print(f"  Saved {len(sensor_df):,} sensor rows → data/sensor_readings.csv")

    print("\nGenerating maintenance logs...")
    maint_df = generate_maintenance_logs(ASSETS, n_logs=150)
    maint_df.to_csv(output_dir / "maintenance_logs.csv", index=False)
    print(f"  Saved {len(maint_df)} log entries → data/maintenance_logs.csv")

    print("\nGenerating energy readings...")
    energy_df = generate_energy_readings(ASSETS, days=30)
    energy_df.to_csv(output_dir / "energy_readings.csv", index=False)
    print(f"  Saved {len(energy_df):,} energy rows → data/energy_readings.csv")

    # ── Summary stats ──
    print("\n── Dataset summary ──────────────────────────────────")
    print(f"Assets:           {len(ASSETS)} ({len([a for a in ASSETS if a['type']=='turbine'])} turbines, "
          f"{len([a for a in ASSETS if a['type']=='compressor'])} compressors, "
          f"{len([a for a in ASSETS if a['type']=='pump'])} pumps)")
    print(f"Sensor readings:  {len(sensor_df):,} rows  |  "
          f"{sensor_df['asset_id'].nunique()} assets  |  "
          f"{sensor_df['sensor'].nunique()} sensor types")

    alert_dist = sensor_df.dropna(subset=["value"])["alert_level"].value_counts()
    for level, count in alert_dist.items():
        pct = count / len(sensor_df.dropna(subset=["value"])) * 100
        print(f"  {level:<12}: {count:>8,}  ({pct:.1f}%)")

    failures = sensor_df[sensor_df["is_failure_active"] == True]["failure_name"].dropna().unique()
    print(f"\nInjected failures: {list(failures)}")
    print(f"Maintenance logs: {len(maint_df)}  |  Energy rows: {len(energy_df):,}")
    print("\nDone.")
