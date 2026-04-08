# Energy Co-pilot

**AI Operations Co-pilot for Industrial Energy Plants**

An end-to-end production system that monitors industrial assets in real time, detects equipment failures before they happen, and gives plant operators an AI assistant they can ask anything — in plain language.

---

## What it does

A gas turbine at an energy plant generates thousands of sensor readings every minute. Spotting a bearing failure buried in that data — hours before it becomes a €400,000 unplanned shutdown — requires constant vigilance no human team can sustain.

Energy Co-pilot watches every asset, every sensor, all the time. When something starts drifting toward failure, it fires an alert. When an operator asks *"Why is TRB-001 vibrating above threshold?"*, an AI agent consults live sensor data and your maintenance documentation simultaneously, then streams back a precise, cited answer in seconds.

---

## Key features

**Real-time monitoring**
- WebSocket streams push live sensor readings to the dashboard every 5 seconds
- WARNING and CRITICAL alerts fire automatically based on per-sensor thresholds
- Remaining Useful Life (RUL) estimates displayed whenever a failure is active
- 7 asset types supported: turbines, compressors, pumps — extensible to any SCADA source

**AI Co-pilot (Claude-powered)**
- Natural language chat scoped to any asset or across the full plant
- Retrieval-Augmented Generation (RAG) pulls relevant maintenance docs, SOPs, and incident reports before every response
- Responses stream token-by-token with full citations back to source documents
- Conversation history maintained per session

**Multi-agent architecture**
- Master orchestrator routes tasks to specialised sub-agents
- Agent pool caching: identical task types reuse existing agents (no re-initialisation overhead)
- Agents: Anomaly Detector, Maintenance Advisor, RAG Document Q&A
- LangGraph state machine for deterministic + LLM hybrid reasoning

**Production data layer**
- TimescaleDB hypertables with automatic 1-day partitioning — queries over millions of rows in milliseconds
- Continuous aggregates (hourly sensor stats, daily energy totals) update automatically
- Qdrant vector store for semantic document search with payload-filtered retrieval
- Redis for agent state cache and pub/sub

**Full-stack web application**
- Industrial dark-theme dashboard (Next.js 14, Tailwind, Recharts)
- Live sensor charts with warn/crit reference lines
- Asset health grid, alert inbox, energy analytics, maintenance log
- Role-based access: operator / engineer / admin

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  Browser                                                            │
│  Next.js 14 · Tailwind · Recharts · Zustand · TanStack Query       │
│  WebSocket hooks (sensors, alerts, agent stream)                    │
└───────────────────────────┬─────────────────────────────────────────┘
                            │ HTTP + WebSocket
┌───────────────────────────▼─────────────────────────────────────────┐
│  Backend  (FastAPI · Python 3.12)                                   │
│                                                                     │
│  REST /api/v1/{assets,sensors,energy,maintenance,agent}             │
│  WebSocket /ws/{sensors/:id, sensors, alerts, agent/:session}       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Multi-Agent Engine  (LangGraph)                             │   │
│  │                                                              │   │
│  │  Master Orchestrator ──▶ Anomaly Agent                       │   │
│  │         │            ──▶ Maintenance Agent                   │   │
│  │         │            ──▶ RAG Agent ──▶ Qdrant                │   │
│  │         │                                                    │   │
│  │         └── Agent Pool Cache (Redis)                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Background broadcasters: sensor push (5s), alert push (10s)       │
└────────┬──────────────────┬──────────────────┬──────────────────────┘
         │                  │                  │
┌────────▼───────┐ ┌────────▼───────┐ ┌───────▼────────┐
│ TimescaleDB    │ │    Qdrant      │ │     Redis      │
│                │ │                │ │                │
│ sensor_readings│ │ energy_docs    │ │ Agent state    │
│ energy_readings│ │ (embeddings)   │ │ WS pub/sub     │
│ maintenance    │ │                │ │ Rate limiting  │
│ (hypertables)  │ │ 384-dim dense  │ │                │
└────────────────┘ └────────────────┘ └────────────────┘
```

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind | App Router, SSR, type-safe |
| Charts | Recharts | Composable, streaming-friendly |
| State | Zustand + TanStack Query | Auth store + server cache |
| Backend | FastAPI, Python 3.12 | Async, WebSocket-native, fast |
| AI | Anthropic Claude (claude-sonnet-4) | Best reasoning, streaming API |
| Agent framework | LangGraph | Stateful, deterministic + LLM hybrid |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Local, free, 384-dim |
| Vector DB | Qdrant | Fast filtered semantic search |
| Time-series DB | TimescaleDB (PostgreSQL) | SQL + hypertables + cont. aggregates |
| Cache | Redis 7 | Agent state, pub/sub, rate limiting |
| Monitoring | Grafana | TimescaleDB datasource, pre-built dashboards |
| Containers | Docker Compose | One-command startup |

---

## Quickstart

### Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- An [Anthropic API key](https://console.anthropic.com)
- 8 GB RAM recommended (sentence-transformers model + all services)

### 1 — Clone and configure

```bash
git clone https://github.com/your-org/energy-copilot.git
cd energy-copilot

cp .env.example .env
```

Edit `.env` — the three required values:

```env
SECRET_KEY=<output of: openssl rand -hex 32>
ANTHROPIC_API_KEY=sk-ant-...
TIMESCALE_PASSWORD=choose-something-strong
```

### 2 — Start all services

```bash
docker compose up --build -d

# Watch until everything is healthy (≈ 90 seconds first run)
docker compose ps
```

### 3 — Load data (first run only)

```bash
make setup
# Generates 423k sensor rows + 150 maintenance logs + 6 RAG docs
# Loads into TimescaleDB and Qdrant
# Takes 2-4 minutes (downloads embedding model on first run)
```

### 4 — Open the dashboard

| Service | URL | Credentials |
|---|---|---|
| Dashboard | http://localhost:3000 | operator@plant.com / operator123 |
| API docs | http://localhost:8000/docs | — |
| Grafana | http://localhost:3001 | admin / grafana123 |
| Qdrant UI | http://localhost:6333/dashboard | — |

---

## Demo walkthrough (for pitches)

**1. Plant health at a glance** — The overview page shows all 7 assets colour-coded by severity. Any asset in CRITICAL state pulses red. RUL (remaining useful life) is shown in hours.

**2. Live sensor stream** — Click any asset, then click a sensor. A 24-hour area chart loads. The readings at the top of the list update live every 5 seconds via WebSocket.

**3. Failure detection** — Assets with injected failure patterns (bearing wear, blade fouling, impeller wear) show orange WARNING or red CRITICAL badges. The failure name and RUL countdown are visible immediately.

**4. AI Co-pilot** — Navigate to AI Co-pilot. Select TRB-001 from the asset dropdown. Ask: *"Why is the bearing temperature rising?"* — the response streams token-by-token, cites the maintenance incident report, and gives a numbered action plan.

**5. Alert inbox** — The Alerts page shows the live stream of WARNING/CRITICAL events updating in real time, filterable by severity and time window.

---

## Project structure

```
energy-copilot/
│
├── docker-compose.yml          # wires all 5 services
├── .env.example                # template — copy to .env
├── Makefile                    # dev shortcuts
│
├── data/                       # data generation + ingestion scripts
│   ├── sensor_generator.py     # 423k synthetic sensor rows
│   ├── rag_generator.py        # maintenance reports + SOPs
│   ├── timescale_ingest.py     # loads CSVs into TimescaleDB
│   └── qdrant_ingest.py        # chunks + embeds docs into Qdrant
│
├── backend/                    # FastAPI application
│   ├── main.py                 # app factory, lifespan, middleware
│   ├── core/
│   │   ├── config.py           # Pydantic settings
│   │   ├── security.py         # JWT, bcrypt, role deps
│   │   └── database.py         # psycopg2 pool, async helpers
│   ├── schemas/models.py       # all Pydantic request/response models
│   ├── services/
│   │   ├── sensor_service.py   # TimescaleDB query layer
│   │   └── agent_service.py    # Claude API + RAG + streaming
│   └── api/
│       ├── routes/routes.py    # all REST endpoints
│       └── websockets/
│           ├── manager.py      # connection registry + broadcast
│           ├── broadcaster.py  # background sensor/alert push tasks
│           └── routes.py       # WS endpoint handlers
│
└── frontend/                   # Next.js 14 application
    ├── app/
    │   ├── login/              # login page
    │   └── dashboard/
    │       ├── page.tsx        # overview: KPIs, health grid, charts
    │       ├── assets/         # asset table + [id] detail + live charts
    │       ├── alerts/         # alert inbox with live stream
    │       ├── chat/           # AI co-pilot streaming chat
    │       ├── energy/         # production analytics
    │       └── maintenance/    # work orders + cost breakdown
    ├── components/
    │   ├── layout/             # Sidebar, Providers
    │   ├── ui/                 # KpiCard, Panel, AssetCard, badges
    │   └── charts/             # SensorChart, EnergyBarChart, Sparkline
    ├── lib/
    │   ├── api.ts              # typed REST client
    │   └── websocket.ts        # useSensorStream, useAlertStream, useAgentStream
    └── store/authStore.ts      # Zustand auth + JWT
```

---

## Connecting real SCADA data

The ingestion layer is intentionally adapter-shaped. To connect a real data source:

**OPC-UA / MQTT (most industrial plants)**
```python
# backend/services/scada_adapter.py
import asyncio
from asyncua import Client   # pip install asyncua

async def stream_opcua(endpoint: str):
    async with Client(url=endpoint) as client:
        node = await client.get_node("ns=2;i=1001")   # turbine vibration node
        while True:
            value = await node.get_value()
            # push to TimescaleDB via sensor_service
            await ingest_reading("TRB-001", "vibration_x", value)
            await asyncio.sleep(5)
```

**REST / CSV historian export**
Replace the CSV loader in `timescale_ingest.py` with a fetch from your historian API (OSIsoft PI, Honeywell Experion, Siemens WinCC).

**RAG documents**
Drop any PDF (maintenance manual, SOP, incident report) into `data/docs/` and run `qdrant_ingest.py` — it chunks, embeds, and indexes automatically.

---

## Business case

| Metric | Typical value |
|---|---|
| Unplanned turbine downtime cost | €50,000 – €500,000 per event |
| Average failures prevented per asset/year with predictive monitoring | 1–3 |
| ROI at 1 prevented failure/quarter per customer | 10–50× annual SaaS cost |
| Operator time saved on manual log review | 2–4 hours/day |

**Pricing model (proposed)**
- Per-asset SaaS: €200–500/asset/month
- 10-asset plant: €2,000–5,000/month recurring
- Enterprise (white-label, on-premise): custom

---

## Roadmap

- [ ] LangGraph full multi-agent pipeline (currently single-agent with tool routing)
- [ ] LangSmith tracing integration for agent observability
- [ ] Real OPC-UA / MQTT adapter
- [ ] Grafana pre-built dashboard provisioning
- [ ] Automated report generation (PDF, weekly email)
- [ ] Fine-tuned anomaly detection model per asset class
- [ ] Multi-tenant architecture (plant isolation, per-customer RAG collections)
- [ ] Mobile app (React Native, same WebSocket hooks)

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built with [Anthropic Claude](https://anthropic.com), FastAPI, Next.js, TimescaleDB, and Qdrant.*
