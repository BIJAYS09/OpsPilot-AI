"""
Dataset Preview Script
Run after sensor_generator.py and rag_generator.py
Shows sample data from each file to verify output quality.
"""

import pandas as pd
import json

print("=" * 60)
print("SENSOR READINGS — Sample (TRB-001, vibration_x)")
print("=" * 60)
df = pd.read_csv("data/sensor_readings.csv", parse_dates=["timestamp"])
sample = df[(df["asset_id"] == "TRB-001") & (df["sensor"] == "vibration_x")].iloc[::2880]
print(sample[["timestamp", "asset_id", "sensor", "value", "alert_level",
             "is_failure_active", "failure_name", "rul_hours"]].to_string(index=False))

print("\n" + "=" * 60)
print("ALERTS BREAKDOWN")
print("=" * 60)
alerts = df.dropna(subset=["value"]).groupby(["asset_id", "alert_level"]).size().unstack(fill_value=0)
print(alerts)

print("\n" + "=" * 60)
print("FAILURE EVENTS DETECTED")
print("=" * 60)
failures = df[df["is_failure_active"] == True][["asset_id", "failure_name", "timestamp"]].drop_duplicates(subset=["asset_id", "failure_name"])
print(failures.to_string(index=False))

print("\n" + "=" * 60)
print("MAINTENANCE LOGS — Sample")
print("=" * 60)
maint = pd.read_csv("data/maintenance_logs.csv")
print(maint[["asset_id", "log_type", "severity", "status", "cost_eur", "parts_replaced"]].head(8).to_string(index=False))

print("\n" + "=" * 60)
print("ENERGY READINGS — 24h sample TRB-001")
print("=" * 60)
energy = pd.read_csv("data/energy_readings.csv", parse_dates=["timestamp"])
day_sample = energy[(energy["asset_id"] == "TRB-001") &
                    (energy["timestamp"].dt.date == energy["timestamp"].dt.date.min())]
print(day_sample[["timestamp", "power_mw", "energy_mwh", "frequency_hz", "availability"]].iloc[::4].to_string(index=False))

print("\n" + "=" * 60)
print("RAG DOCUMENTS")
print("=" * 60)
with open("data/rag_documents.json") as f:
    docs = json.load(f)
for d in docs:
    preview = d["content"].strip()[:120].replace("\n", " ")
    print(f"  [{d['category']:22s}] {d['title'][:45]}")
    print(f"   Preview: {preview}...")
    print()

print("=" * 60)
print(f"Total: {len(df):,} sensor rows | {len(maint)} maint logs | {len(energy):,} energy rows | {len(docs)} RAG docs")
