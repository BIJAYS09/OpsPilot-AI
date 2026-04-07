"""
Energy Co-pilot — FastAPI Application
======================================
Start with:
    uvicorn main:app --reload --port 8000

Swagger UI:  http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
WS test:     ws://localhost:8000/ws/sensors/TRB-001?token=<JWT>
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from core.config import get_settings
from core.database import init_db, close_db
from api.routes.routes import api_router
from api.websockets.routes import router as ws_router
from api.websockets.broadcaster import start_broadcasters

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger   = logging.getLogger(__name__)
settings = get_settings()


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    try:
        init_db()
        logger.info("Database pool ready.")
    except Exception as e:
        logger.warning("DB init failed (%s) — running without TimescaleDB.", e)

    await start_broadcasters()
    logger.info("App ready.")

    yield   # ← app is running

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    close_db()


# ── App factory ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Real-time AI Operations Co-pilot for industrial energy plants.\n\n"
        "- **REST** endpoints under `/api/v1/`\n"
        "- **WebSocket** streams under `/ws/`\n"
        "- Auth: OAuth2 password flow → Bearer JWT\n\n"
        "Demo credentials: `operator@plant.com / operator123`"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(api_router)
app.include_router(ws_router, prefix="/ws")

# ── Root ──────────────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root():
    return {
        "app":     settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs":    "/docs",
        "ws":      "/ws/sensors/{asset_id}?token=<JWT>",
    }
