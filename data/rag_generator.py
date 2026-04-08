"""
RAG Knowledge Base Generator
Generates realistic maintenance reports, failure incident logs,
and equipment documentation for the Qdrant vector store.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from faker import Faker

fake = Faker()
random.seed(99)

# ─── Templates ────────────────────────────────────────────────────────────────

TURBINE_FAILURE_REPORTS = [
    {
        "title": "Incident Report: Turbine TRB-001 Bearing Failure – Alpha Plant",
        "body": """
INCIDENT SUMMARY
Date: {date}
Asset: TRB-001 | Gas Turbine | Alpha Plant
Severity: HIGH
Root Cause: Stage-2 bearing wear due to lubrication starvation

SYMPTOMS OBSERVED
Vibration levels on X-axis rose gradually from 1.8 mm/s to 4.9 mm/s over 68 hours.
Bearing temperature increased from 65°C to 88°C (WARNING threshold: 85°C).
Lube oil pressure dropped from 3.2 bar to 2.6 bar three days prior to shutdown.

ROOT CAUSE ANALYSIS
Inspection revealed partial blockage in the lube oil filter (82% clogged).
The restricted oil flow caused thermal stress on stage-2 bearing races.
Micro-pitting observed on inner race surface under borescope inspection.

CORRECTIVE ACTIONS TAKEN
1. Replaced stage-2 bearing assembly (SKF 6316-2Z, Part No. TRB-BRG-002)
2. Replaced lube oil filter and flushed entire lubrication circuit
3. Refilled with Mobil DTE 832 turbine oil (180 litres)
4. Reset vibration alarm thresholds to 4.0 mm/s (Warning) / 6.5 mm/s (Critical)

PREVENTIVE RECOMMENDATIONS
- Reduce lube oil filter inspection interval from 90 days to 45 days
- Install differential pressure sensor across oil filter (target: <0.8 bar drop)
- Schedule next bearing inspection at 4,000 operating hours

DOWNTIME: 14.5 hours | COST: €18,400 (parts: €6,200 + labour: €12,200)
""",
    },
    {
        "title": "Maintenance Report: Blade Fouling Investigation – TRB-003",
        "body": """
MAINTENANCE WORK ORDER: MWO-2024-0342
Date: {date}
Asset: TRB-003 | Gas Turbine 80MW | Beta Station
Type: Corrective Maintenance

BACKGROUND
Operator reported gradual power output degradation over 14 days.
Output declined from 79.2 MW to 71.8 MW (9.3% reduction).
Exhaust temperature increased by 18°C above baseline with no load change.
Compressor discharge pressure ratio dropped from 18.2 to 17.4.

INSPECTION FINDINGS
Borescope inspection of compressor section revealed:
- Stage 1-3 blades: Heavy fouling deposit (estimated 0.4mm layer)
- Deposit composition: mineral dust, hydrocarbon residue, salt crystals
- No physical damage to blade profiles detected

CLEANING PROCEDURE
Method: Online water washing (Rochem TC-11 detergent, 2% solution)
Duration: 4 washing cycles × 8 minutes each
Water temperature: 25°C, injection pressure: 45 bar
Post-wash soak: 30 minutes before restart

RESULTS
Post-cleaning power output: 78.9 MW (recovery: 7.1 MW / 98.9% of baseline)
Exhaust temperature: Returned to baseline ±3°C
Compressor pressure ratio: 18.1 (within acceptable range)

SCHEDULED ACTIONS
- Online washing: Every 500 operating hours
- Offline washing: Every 2,000 operating hours
- Air intake filter inspection: Monthly

DOWNTIME: 6 hours | COST: €4,100
""",
    },
]

COMPRESSOR_REPORTS = [
    {
        "title": "Technical Bulletin: Compressor Valve Degradation Patterns – CMP Series",
        "body": """
TECHNICAL BULLETIN TB-COMP-2024-07
Subject: Early Detection of Valve Degradation in Reciprocating Compressors
Applies to: CMP-001, CMP-002 (Ariel JGC/2 compressor units)

OVERVIEW
This bulletin describes the sensor signature patterns associated with valve
degradation in reciprocating compressors based on fleet data from 2022-2024.
Early identification can reduce unplanned downtime by up to 73%.

EARLY WARNING INDICATORS (12-96 hours before failure)
1. Outlet pressure: Gradual decline of 5-12% from baseline (most reliable indicator)
2. Stage 1 temperature: Rise of 15-30°C above ambient-corrected baseline
3. Motor current: Increase of 8-18% above nominal (energy compensation for leakage)
4. Inter-stage pressure differential: Reduction of >10% from commissioning baseline

ADVANCED WARNING (4-24 hours before failure)
- Outlet pressure drops >15% with simultaneous temperature spike >25°C
- Motor current exceeds 115% of nameplate rating
- Audible knock detected during valve operation phase

RECOMMENDED ACTIONS BY STAGE
Stage 1 (subtle drift, >96hrs to failure): Increase monitoring frequency to 15-min
Stage 2 (clear trend, 24-96hrs): Schedule valve inspection within 48 hours
Stage 3 (threshold breach, <24hrs): Take unit offline for immediate valve replacement

VALVE REPLACEMENT PROCEDURE
Parts required: Suction valve set (Part: ARJ-SV-08), Discharge valve set (Part: ARJ-DV-08)
Estimated replacement time: 6-8 hours (single cylinder), 18-24 hours (full overhaul)
Torque specification: 85 Nm (valve cap bolts), 120 Nm (cylinder head bolts)

CONTACT: Rotating Equipment Engineering | ext. 4471
""",
    },
]

PUMP_REPORTS = [
    {
        "title": "Failure Analysis: Pump PMP-002 Mechanical Seal Failure",
        "body": """
ROOT CAUSE ANALYSIS REPORT
Date: {date}
Asset: PMP-002 | Centrifugal Pump 180 m³/h | Beta Station
Failure mode: Mechanical seal leak leading to bearing contamination

FAILURE TIMELINE
T-72h: Inlet pressure begins declining (2.0 → 1.7 bar, below 1.5 bar WARNING)
T-48h: Motor current increases 12% above nominal (bearing friction increase)
T-24h: Bearing temperature reaches 74°C (WARNING threshold: 75°C)
T-6h:  Visible seal leak detected by operator during rounds
T-0:   Emergency shutdown initiated

PHYSICAL INSPECTION
Mechanical seal faces: Severe scoring on stationary face (silicon carbide)
Cause: Ingress of process fluid particulates (sand, 150-400 micron)
Secondary damage: Bearing contamination by leaked process fluid
Bearing condition: Pitting on outer race, replacement required

5-WHY ANALYSIS
Why did the seal fail? → Hard particle ingress caused face scoring
Why were particles present? → Inlet strainer basket damaged (3 mesh sections missing)
Why was the strainer damaged? → Fatigue from water hammer events
Why did water hammer occur? → Fast-closing valve (CV-12) operating without soft-close
Why no soft-close? → Valve actuator not upgraded during 2022 pump replacement

CORRECTIVE ACTIONS
Immediate: Replace mechanical seal (Part: JohnCrane T2800, 75mm)
Short-term: Replace inlet strainer basket, inspect all strainers
Long-term: Install soft-close actuator on CV-12 (budgeted Q2 2024)

DOWNTIME: 22 hours | COST: €31,700
""",
    },
]

OPERATING_PROCEDURES = [
    {
        "title": "Standard Operating Procedure: Turbine Emergency Shutdown",
        "body": """
SOP-TRB-ES-001 | Revision 4 | Approved: {date}
TURBINE EMERGENCY SHUTDOWN PROCEDURE

APPLICABLE UNITS: TRB-001, TRB-002 (Alpha Plant), TRB-003 (Beta Station)

AUTOMATIC TRIP CONDITIONS (system initiates shutdown automatically)
- Exhaust temperature > 620°C (any thermocouple)
- Vibration amplitude > 7.1 mm/s (bearing 1 or 2)
- Lube oil pressure < 2.0 bar
- Overspeed > 3,200 RPM
- Flame failure (loss of combustion signal)
- Generator differential protection trip

MANUAL SHUTDOWN PROCEDURE
1. Notify control room operator and shift supervisor immediately
2. Press red EMERGENCY STOP button on local control panel
3. Confirm fuel gas isolation valve has closed (indicator lamp: OFF)
4. Monitor turbine rundown on DCS (normal coast-down: 8-12 minutes to rest)
5. Engage turning gear after speed < 50 RPM to prevent rotor bow
6. Maintain lube oil circulation for minimum 30 minutes post-trip
7. Record DCS alarm list and timestamp of shutdown in logbook

POST-TRIP CHECKLIST
[ ] Vibration levels returning to <0.5 mm/s (rotor at rest)
[ ] Exhaust temperature declining at normal rate (>3°C/min)
[ ] Lube oil temperature < 55°C before turning gear stop
[ ] Complete incident report within 4 hours of event
[ ] Notify maintenance team if trip caused by equipment fault

DO NOT RESTART without: Written clearance from shift supervisor + maintenance sign-off
""",
    },
    {
        "title": "Procedure: Compressor Startup After Maintenance",
        "body": """
SOP-CMP-START-003 | Compressor Cold Startup After Maintenance
Applies to: CMP-001 (Alpha Plant), CMP-002 (Beta Station)

PRE-START VERIFICATION CHECKLIST
[ ] All maintenance work orders closed and signed off
[ ] Isolation blinds removed, all flanges re-bolted to correct torque
[ ] Lube oil level: Full (between MIN and MAX on sight glass)
[ ] Lube oil pre-circulation: Run for minimum 10 minutes before start
[ ] Suction scrubber drained and valved in
[ ] Discharge check valve: Free movement confirmed
[ ] Unloaders activated (start in unloaded condition)
[ ] Control panel: All alarms acknowledged, no active trips

STARTUP SEQUENCE
Step 1: Close suction valve to 20% open
Step 2: Start motor (confirm current < 180% FLA within 8 seconds)
Step 3: Allow unit to reach operating speed (target: 985 RPM ±10)
Step 4: Check lube oil pressure: must be >3.0 bar within 30 seconds
Step 5: Gradually open suction valve over 5 minutes to full open
Step 6: Engage unloaders one cylinder at a time (30-second intervals)
Step 7: Monitor inter-stage pressures and temperatures for 15 minutes

ACCEPTANCE CRITERIA AFTER START
- Stage 1 outlet temperature: ≤ 95°C (after 15 min stabilisation)
- Stage 2 outlet temperature: ≤ 145°C
- Outlet pressure: Within ±5% of setpoint
- Vibration: < 3.0 mm/s all measurement points
- Motor current: ≤ 105% of baseline

Any parameter outside acceptance criteria: Return to maintenance hold
""",
    },
]


def generate_all_documents():
    docs = []
    date_recent = datetime.now() - timedelta(days=random.randint(5, 60))

    for tmpl in TURBINE_FAILURE_REPORTS:
        docs.append({
            "doc_id": fake.uuid4(),
            "title": tmpl["title"],
            "content": tmpl["body"].format(date=date_recent.strftime("%Y-%m-%d")),
            "category": "incident_report",
            "asset_type": "turbine",
            "tags": ["failure", "turbine", "maintenance"],
        })

    for tmpl in COMPRESSOR_REPORTS:
        docs.append({
            "doc_id": fake.uuid4(),
            "title": tmpl["title"],
            "content": tmpl["body"].format(date=date_recent.strftime("%Y-%m-%d")),
            "category": "technical_bulletin",
            "asset_type": "compressor",
            "tags": ["valve", "compressor", "preventive"],
        })

    for tmpl in PUMP_REPORTS:
        docs.append({
            "doc_id": fake.uuid4(),
            "title": tmpl["title"],
            "content": tmpl["body"].format(date=date_recent.strftime("%Y-%m-%d")),
            "category": "root_cause_analysis",
            "asset_type": "pump",
            "tags": ["seal", "pump", "rca"],
        })

    for tmpl in OPERATING_PROCEDURES:
        docs.append({
            "doc_id": fake.uuid4(),
            "title": tmpl["title"],
            "content": tmpl["body"].format(date=date_recent.strftime("%Y-%m-%d")),
            "category": "procedure",
            "asset_type": "all",
            "tags": ["SOP", "safety", "operations"],
        })

    return docs


if __name__ == "__main__":
    output_dir = Path("./data")
    output_dir.mkdir(exist_ok=True)

    docs = generate_all_documents()
    with open(output_dir / "rag_documents.json", "w") as f:
        json.dump(docs, f, indent=2, default=str)

    print(f"Generated {len(docs)} RAG documents → data/rag_documents.json")
    for d in docs:
        print(f"  [{d['category']:20s}] {d['title'][:60]}")
