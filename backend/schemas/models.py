"""
Pydantic v2 schemas for all API request / response models.
Keeps FastAPI routes thin — validation + serialisation happens here.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    username: str          # email used as username
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int        # seconds

class RefreshRequest(BaseModel):
    refresh_token: str

class UserOut(BaseModel):
    email: str
    full_name: str
    role: str


# ── Assets ────────────────────────────────────────────────────────────────────

class AssetOut(BaseModel):
    asset_id: str
    asset_type: str
    site: str
    nominal_power: Optional[float] = None
    unit: Optional[str] = None
    is_active: bool = True


# ── Sensor readings ───────────────────────────────────────────────────────────

class SensorReading(BaseModel):
    time: datetime
    asset_id: str
    sensor: str
    value: Optional[float] = None
    unit: Optional[str] = None
    alert_level: str = "NORMAL"
    is_failure: bool = False
    failure_name: Optional[str] = None
    rul_hours: Optional[float] = None

class SensorHistoryPoint(BaseModel):
    bucket: datetime
    avg_value: float
    min_value: float
    max_value: float
    alert_level: str

class SensorHistoryResponse(BaseModel):
    asset_id: str
    sensor: str
    hours: int
    interval: str
    data: list[SensorHistoryPoint]


# ── Asset health ──────────────────────────────────────────────────────────────

class AssetHealthItem(BaseModel):
    asset_id: str
    asset_type: str
    site: str
    severity_score: int          # 0=ok 1=warn 2=critical
    has_active_failure: bool
    failure_name: Optional[str] = None
    min_rul_hours: Optional[float] = None
    last_updated: Optional[datetime] = None

class HealthSummaryResponse(BaseModel):
    total_assets: int
    critical_count: int
    warning_count: int
    healthy_count: int
    assets: list[AssetHealthItem]


# ── Alerts ────────────────────────────────────────────────────────────────────

class AlertItem(BaseModel):
    time: datetime
    asset_id: str
    sensor: str
    value: Optional[float]
    unit: Optional[str]
    alert_level: str
    is_failure: bool
    failure_name: Optional[str]
    rul_hours: Optional[float]

class AlertsResponse(BaseModel):
    total: int
    hours: int
    alerts: list[AlertItem]


# ── Maintenance logs ──────────────────────────────────────────────────────────

class MaintenanceLogOut(BaseModel):
    log_id: str
    asset_id: str
    site: Optional[str]
    log_type: Optional[str]
    severity: Optional[str]
    status: Optional[str]
    technician: Optional[str]
    description: Optional[str]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]
    cost_eur: Optional[float]
    parts_replaced: Optional[str]

class MaintenanceListResponse(BaseModel):
    total: int
    logs: list[MaintenanceLogOut]


# ── Energy ────────────────────────────────────────────────────────────────────

class EnergyDayItem(BaseModel):
    day: datetime
    site: str
    total_mwh: float
    avg_power_mw: float
    peak_power_mw: float
    availability_pct: float

class EnergyResponse(BaseModel):
    days: int
    data: list[EnergyDayItem]


# ── WebSocket messages ────────────────────────────────────────────────────────

class WsMessageType:
    SENSOR_UPDATE   = "sensor_update"
    ALERT_FIRED     = "alert_fired"
    AGENT_CHUNK     = "agent_chunk"      # streaming token from Claude
    AGENT_DONE      = "agent_done"       # agent finished responding
    AGENT_ERROR     = "agent_error"
    HEARTBEAT       = "heartbeat"
    SUBSCRIBED      = "subscribed"
    ERROR           = "error"

class WsSensorUpdate(BaseModel):
    type: str = WsMessageType.SENSOR_UPDATE
    asset_id: str
    readings: list[dict]            # list of latest sensor dicts
    timestamp: datetime

class WsAlertFired(BaseModel):
    type: str = WsMessageType.ALERT_FIRED
    asset_id: str
    sensor: str
    value: float
    alert_level: str
    failure_name: Optional[str]
    rul_hours: Optional[float]
    timestamp: datetime

class WsAgentChunk(BaseModel):
    type: str = WsMessageType.AGENT_CHUNK
    session_id: str
    delta: str                      # partial text token

class WsAgentDone(BaseModel):
    type: str = WsMessageType.AGENT_DONE
    session_id: str
    sources: list[dict] = []        # RAG citations

class WsHeartbeat(BaseModel):
    type: str = WsMessageType.HEARTBEAT
    server_time: datetime


# ── Chat / Agent ──────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str                       # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    session_id: str
    message: str
    asset_id: Optional[str] = None  # scopes agent context to one asset
    history: list[ChatMessage] = Field(default_factory=list)

class RagHit(BaseModel):
    score: float
    title: str
    section: str
    category: str
    asset_type: str
    text: str

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[RagHit] = []
    model: str
    input_tokens: int
    output_tokens: int
