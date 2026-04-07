"""
REST API routes — mounted at /api/v1
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordRequestForm

from core.security import (
    authenticate_user, create_access_token, create_refresh_token,
    verify_token, get_current_user, require_role,
)
from core.config import get_settings
from schemas.models import (
    TokenResponse, RefreshRequest, UserOut,
    AssetOut,
    SensorHistoryResponse, SensorHistoryPoint,
    HealthSummaryResponse, AssetHealthItem,
    AlertsResponse, AlertItem,
    MaintenanceListResponse, MaintenanceLogOut,
    EnergyResponse, EnergyDayItem,
    ChatRequest, ChatResponse,
)
from services.sensor_service import (
    SensorService, EnergyService, MaintenanceService, AssetService,
)

settings = get_settings()

# ── Sub-routers ───────────────────────────────────────────────────────────────

auth_router   = APIRouter(prefix="/auth",        tags=["auth"])
asset_router  = APIRouter(prefix="/assets",      tags=["assets"])
sensor_router = APIRouter(prefix="/sensors",     tags=["sensors"])
energy_router = APIRouter(prefix="/energy",      tags=["energy"])
maint_router  = APIRouter(prefix="/maintenance", tags=["maintenance"])
agent_router  = APIRouter(prefix="/agent",       tags=["agent"])
health_router = APIRouter(prefix="/health",      tags=["health"])


# ═════════════════════════════════════════════════════════════════════════════
# AUTH
# ═════════════════════════════════════════════════════════════════════════════

@auth_router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = {"sub": user["email"], "role": user["role"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest):
    payload    = verify_token(body.refresh_token, expected_type="refresh")
    token_data = {"sub": payload["sub"], "role": payload["role"]}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@auth_router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)


# ═════════════════════════════════════════════════════════════════════════════
# ASSETS
# ═════════════════════════════════════════════════════════════════════════════

@asset_router.get("/", response_model=list[AssetOut])
async def list_assets(user: dict = Depends(get_current_user)):
    return AssetService.get_all()


@asset_router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(asset_id: str, user: dict = Depends(get_current_user)):
    asset = AssetService.get_one(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset {asset_id!r} not found")
    return asset


# ═════════════════════════════════════════════════════════════════════════════
# SENSORS
# ═════════════════════════════════════════════════════════════════════════════

@sensor_router.get("/health", response_model=HealthSummaryResponse)
async def asset_health(user: dict = Depends(get_current_user)):
    """Overall health summary for every asset — used by the dashboard header."""
    rows = SensorService.get_health_summary()
    items = [AssetHealthItem(**r) for r in rows]
    return HealthSummaryResponse(
        total_assets=len(items),
        critical_count=sum(1 for i in items if i.severity_score == 2),
        warning_count=sum(1 for i in items if i.severity_score == 1),
        healthy_count=sum(1 for i in items if i.severity_score == 0),
        assets=items,
    )


@sensor_router.get("/alerts", response_model=AlertsResponse)
async def get_alerts(
    asset_id: Optional[str] = Query(None),
    level: Optional[str]    = Query(None, pattern="^(WARNING|CRITICAL)$"),
    hours: int              = Query(24, ge=1, le=168),
    limit: int              = Query(200, ge=1, le=1000),
    user: dict              = Depends(get_current_user),
):
    rows = SensorService.get_alerts(asset_id, level, hours, limit)
    return AlertsResponse(
        total=len(rows),
        hours=hours,
        alerts=[AlertItem(**r) for r in rows],
    )


@sensor_router.get("/{asset_id}/latest")
async def latest_readings(
    asset_id: str,
    user: dict = Depends(get_current_user),
):
    """Latest value for every sensor on an asset."""
    rows = SensorService.get_latest(asset_id)
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for {asset_id!r}")
    return {"asset_id": asset_id, "readings": rows}


@sensor_router.get("/{asset_id}/{sensor}/history",
                   response_model=SensorHistoryResponse)
async def sensor_history(
    asset_id: str,
    sensor:   str,
    hours:    int = Query(24, ge=1, le=720),
    interval: str = Query("15 minutes"),
    user: dict    = Depends(get_current_user),
):
    rows = SensorService.get_history(asset_id, sensor, hours, interval)
    return SensorHistoryResponse(
        asset_id=asset_id,
        sensor=sensor,
        hours=hours,
        interval=interval,
        data=[SensorHistoryPoint(**r) for r in rows],
    )


@sensor_router.get("/{asset_id}/failures")
async def failure_timeline(asset_id: str, user: dict = Depends(get_current_user)):
    return SensorService.get_failure_timeline(asset_id)


# ═════════════════════════════════════════════════════════════════════════════
# ENERGY
# ═════════════════════════════════════════════════════════════════════════════

@energy_router.get("/summary", response_model=EnergyResponse)
async def energy_summary(
    days: int  = Query(7, ge=1, le=90),
    user: dict = Depends(get_current_user),
):
    rows = EnergyService.get_summary(days)
    return EnergyResponse(days=days, data=[EnergyDayItem(**r) for r in rows])


@energy_router.get("/live")
async def live_power(user: dict = Depends(get_current_user)):
    """Current power output for every asset — for the KPI header bar."""
    return EnergyService.get_live_power()


# ═════════════════════════════════════════════════════════════════════════════
# MAINTENANCE
# ═════════════════════════════════════════════════════════════════════════════

@maint_router.get("/", response_model=MaintenanceListResponse)
async def list_maintenance(
    asset_id: Optional[str] = Query(None),
    status:   Optional[str] = Query(None),
    limit:    int           = Query(50, ge=1, le=500),
    user: dict              = Depends(get_current_user),
):
    rows = MaintenanceService.get_logs(asset_id, status, limit)
    return MaintenanceListResponse(
        total=len(rows),
        logs=[MaintenanceLogOut(**r) for r in rows],
    )


@maint_router.get("/costs")
async def maintenance_costs(user: dict = Depends(get_current_user)):
    return MaintenanceService.get_cost_summary()


# ═════════════════════════════════════════════════════════════════════════════
# AGENT (HTTP fallback — use WS for streaming)
# ═════════════════════════════════════════════════════════════════════════════

@agent_router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    body: ChatRequest,
    user: dict = Depends(get_current_user),
):
    """
    Synchronous (non-streaming) agent endpoint.
    Use the WebSocket /ws/agent/{session_id} for streaming token-by-token.
    """
    try:
        from services.agent_service import AgentService
        agent  = AgentService()
        result = await agent.respond(
            session_id=body.session_id,
            message=body.message,
            asset_id=body.asset_id,
            history=[m.model_dump() for m in body.history],
        )
        return ChatResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK (no auth)
# ═════════════════════════════════════════════════════════════════════════════

@health_router.get("/")
async def health_check():
    return {
        "status": "ok",
        "app":    settings.APP_NAME,
        "version": settings.APP_VERSION,
        "time":   datetime.now(timezone.utc).isoformat(),
    }


# ── Master router (imported by main.py) ───────────────────────────────────────

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(asset_router)
api_router.include_router(sensor_router)
api_router.include_router(energy_router)
api_router.include_router(maint_router)
api_router.include_router(agent_router)
api_router.include_router(health_router)
