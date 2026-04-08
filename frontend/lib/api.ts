/**
 * API client — typed wrappers around the FastAPI backend.
 * Reads token from localStorage. Throws on 4xx/5xx.
 */

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ── Auth token storage ────────────────────────────────────────────────────────

export const TokenStore = {
  get:     () => typeof window !== 'undefined' ? localStorage.getItem('access_token')  : null,
  getRefresh: () => typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null,
  set:     (a: string, r: string) => { localStorage.setItem('access_token', a); localStorage.setItem('refresh_token', r) },
  clear:   () => { localStorage.removeItem('access_token'); localStorage.removeItem('refresh_token') },
}

// ── Core fetch wrapper ────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = TokenStore.get()
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers || {}),
  }
  const res = await fetch(`${API}${path}`, { ...opts, headers })

  if (res.status === 401) {
    TokenStore.clear()
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const form = new FormData()
  form.append('username', email)
  form.append('password', password)
  const res = await fetch(`${API}/api/v1/auth/token`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Invalid credentials')
  return res.json()
}

export async function getMe() {
  return apiFetch<{ email: string; full_name: string; role: string }>('/api/v1/auth/me')
}

// ── Assets ────────────────────────────────────────────────────────────────────

export interface Asset {
  asset_id: string
  asset_type: 'turbine' | 'compressor' | 'pump'
  site: string
  nominal_power: number | null
  unit: string | null
  is_active: boolean
}

export const getAssets = () => apiFetch<Asset[]>('/api/v1/assets/')

// ── Sensors ───────────────────────────────────────────────────────────────────

export interface SensorReading {
  time: string
  asset_id: string
  sensor: string
  value: number | null
  unit: string | null
  alert_level: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'MAINTENANCE'
  is_failure: boolean
  failure_name: string | null
  rul_hours: number | null
}

export interface AssetHealthItem {
  asset_id: string
  asset_type: string
  site: string
  severity_score: number
  has_active_failure: boolean
  failure_name: string | null
  min_rul_hours: number | null
  last_updated: string | null
}

export interface HealthSummary {
  total_assets: number
  critical_count: number
  warning_count: number
  healthy_count: number
  assets: AssetHealthItem[]
}

export interface HistoryPoint {
  bucket: string
  avg_value: number
  min_value: number
  max_value: number
  alert_level: string
}

export interface AlertItem {
  time: string
  asset_id: string
  sensor: string
  value: number | null
  unit: string | null
  alert_level: string
  is_failure: boolean
  failure_name: string | null
  rul_hours: number | null
}

export const getHealthSummary = () => apiFetch<HealthSummary>('/api/v1/sensors/health')
export const getLatestReadings = (assetId: string) =>
  apiFetch<{ asset_id: string; readings: SensorReading[] }>(`/api/v1/sensors/${assetId}/latest`)
export const getSensorHistory = (assetId: string, sensor: string, hours = 24) =>
  apiFetch<{ data: HistoryPoint[] }>(`/api/v1/sensors/${assetId}/${sensor}/history?hours=${hours}&interval=30+minutes`)
export const getAlerts = (hours = 24, limit = 100) =>
  apiFetch<{ total: number; alerts: AlertItem[] }>(`/api/v1/sensors/alerts?hours=${hours}&limit=${limit}`)
export const getFailureTimeline = (assetId: string) =>
  apiFetch<any[]>(`/api/v1/sensors/${assetId}/failures`)

// ── Energy ────────────────────────────────────────────────────────────────────

export interface EnergyDay {
  day: string
  site: string
  total_mwh: number
  avg_power_mw: number
  peak_power_mw: number
  availability_pct: number
}

export const getEnergySummary = (days = 7) =>
  apiFetch<{ data: EnergyDay[] }>(`/api/v1/energy/summary?days=${days}`)
export const getLivePower = () => apiFetch<any[]>('/api/v1/energy/live')

// ── Maintenance ───────────────────────────────────────────────────────────────

export interface MaintenanceLog {
  log_id: string
  asset_id: string
  site: string | null
  log_type: string | null
  severity: string | null
  status: string | null
  technician: string | null
  description: string | null
  created_at: string | null
  completed_at: string | null
  cost_eur: number | null
  parts_replaced: string | null
}

export const getMaintenance = (assetId?: string, limit = 20) => {
  const q = new URLSearchParams({ limit: String(limit) })
  if (assetId) q.set('asset_id', assetId)
  return apiFetch<{ total: number; logs: MaintenanceLog[] }>(`/api/v1/maintenance/?${q}`)
}

// ── Agent ─────────────────────────────────────────────────────────────────────

export interface ChatMessage { role: 'user' | 'assistant'; content: string }

export async function agentChat(
  sessionId: string,
  message: string,
  assetId?: string,
  history: ChatMessage[] = [],
) {
  return apiFetch<{ session_id: string; answer: string; sources: any[] }>('/api/v1/agent/chat', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, message, asset_id: assetId, history }),
  })
}
