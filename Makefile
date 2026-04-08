# ─────────────────────────────────────────────────────────
#  Energy Co-pilot — Makefile
#  Usage: make <target>
# ─────────────────────────────────────────────────────────

.PHONY: help up down build logs shell-backend shell-db data load clean restart

help:
	@echo ""
	@echo "  Energy Co-pilot — available commands"
	@echo ""
	@echo "  make up          Start all containers (detached)"
	@echo "  make build       Rebuild images and start"
	@echo "  make down        Stop all containers"
	@echo "  make restart     Restart backend only (fast iteration)"
	@echo "  make logs        Tail logs for all services"
	@echo "  make data        Generate synthetic datasets"
	@echo "  make load        Load data into TimescaleDB + Qdrant"
	@echo "  make setup       data + load (first-time setup)"
	@echo "  make shell-back  Shell into backend container"
	@echo "  make shell-db    psql into TimescaleDB"
	@echo "  make clean       Remove containers + volumes (destructive!)"
	@echo ""

# ── Lifecycle ─────────────────────────────────────────────

up:
	docker compose up -d

build:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose restart backend

logs:
	docker compose logs -f --tail=100

# ── First-time data setup ─────────────────────────────────

data:
	@echo "Generating synthetic datasets..."
	docker compose exec backend python /app/data/sensor_generator.py
	docker compose exec backend python /app/data/rag_generator.py
	@echo "Done — data/ directory populated."

load:
	@echo "Loading data into TimescaleDB..."
	docker compose exec backend python /app/data/timescale_ingest.py
	@echo "Loading docs into Qdrant..."
	docker compose exec backend python /app/data/qdrant_ingest.py --no-smoke-test
	@echo "Done — databases ready."

setup: data load
	@echo ""
	@echo "  Setup complete. Open http://localhost:3000"
	@echo "  Login: operator@plant.com / operator123"
	@echo ""

# ── Shells ────────────────────────────────────────────────

shell-back:
	docker compose exec backend /bin/bash

shell-db:
	docker compose exec timescaledb psql -U $${TIMESCALE_USER:-postgres} -d $${TIMESCALE_DB:-energy_copilot}

# ── Status + health ───────────────────────────────────────

status:
	@docker compose ps
	@echo ""
	@echo "Backend health:"
	@curl -sf http://localhost:8000/api/v1/health/ | python3 -m json.tool || echo "  not reachable"

# ── Clean ─────────────────────────────────────────────────

clean:
	@echo "WARNING: This will delete all containers AND data volumes."
	@read -p "Type 'yes' to confirm: " c; [ "$$c" = "yes" ] && docker compose down -v || echo "Aborted."
