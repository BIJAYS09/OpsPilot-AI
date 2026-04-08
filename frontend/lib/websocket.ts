/**
 * WebSocket hooks
 * useSensorStream(assetId)  — subscribe to live sensor updates for one asset
 * useAlertStream()          — subscribe to plant-wide alerts
 * useAgentStream(sessionId) — streaming agent responses token-by-token
 */

import { useEffect, useRef, useCallback, useState } from 'react'
import { TokenStore } from './api'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error'

function useWebSocket(
  path: string,
  onMessage: (data: any) => void,
  enabled = true,
) {
  const ws      = useRef<WebSocket | null>(null)
  const retries = useRef(0)
  const [status, setStatus] = useState<WsStatus>('disconnected')

  const connect = useCallback(() => {
    const token = TokenStore.get()
    if (!token || !enabled) return

    const url = `${WS_URL}${path}?token=${token}`
    const socket = new WebSocket(url)
    ws.current = socket
    setStatus('connecting')

    socket.onopen  = () => { setStatus('connected'); retries.current = 0 }
    socket.onclose = () => {
      setStatus('disconnected')
      // Exponential back-off, max 30s
      const delay = Math.min(1000 * 2 ** retries.current, 30_000)
      retries.current++
      setTimeout(connect, delay)
    }
    socket.onerror = () => setStatus('error')
    socket.onmessage = (e) => {
      try { onMessage(JSON.parse(e.data)) } catch {}
    }
  }, [path, onMessage, enabled])

  useEffect(() => {
    if (!enabled) return
    connect()
    return () => {
      ws.current?.close()
    }
  }, [connect, enabled])

  const send = useCallback((data: object) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data))
    }
  }, [])

  return { status, send }
}

// ── Sensor stream ─────────────────────────────────────────────────────────────

export interface LiveReading {
  time: string
  sensor: string
  value: number | null
  unit: string | null
  alert_level: string
  is_failure: boolean
  failure_name: string | null
  rul_hours: number | null
}

export function useSensorStream(assetId: string | null) {
  const [readings, setReadings] = useState<Record<string, LiveReading>>({})
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const handleMessage = useCallback((data: any) => {
    if (data.type === 'sensor_update' && data.asset_id === assetId) {
      const map: Record<string, LiveReading> = {}
      for (const r of data.readings ?? []) map[r.sensor] = r
      setReadings(map)
      setLastUpdate(new Date())
    }
  }, [assetId])

  const { status } = useWebSocket(
    assetId ? `/ws/sensors/${assetId}` : '',
    handleMessage,
    !!assetId,
  )

  return { readings, lastUpdate, status }
}

// ── Alert stream ──────────────────────────────────────────────────────────────

export interface LiveAlert {
  asset_id: string
  sensor: string
  value: number | null
  alert_level: string
  failure_name: string | null
  rul_hours: number | null
  timestamp: string
  id: string   // client-side dedup key
}

export function useAlertStream() {
  const [alerts, setAlerts] = useState<LiveAlert[]>([])
  const seen = useRef(new Set<string>())

  const handleMessage = useCallback((data: any) => {
    if (data.type !== 'alert_fired') return
    const id = `${data.asset_id}:${data.sensor}:${data.timestamp}`
    if (seen.current.has(id)) return
    seen.current.add(id)
    setAlerts(prev => [{ ...data, id }, ...prev].slice(0, 200))
  }, [])

  const { status } = useWebSocket('/ws/alerts', handleMessage)
  return { alerts, status }
}

// ── Agent stream ──────────────────────────────────────────────────────────────

export interface AgentChunk { type: 'chunk' | 'done' | 'error'; delta?: string; sources?: any[]; detail?: string }

export function useAgentStream(sessionId: string) {
  const [streaming, setStreaming] = useState(false)
  const [buffer,    setBuffer]    = useState('')
  const [sources,   setSources]   = useState<any[]>([])
  const sendRef = useRef<((d: object) => void) | null>(null)

  const handleMessage = useCallback((data: any) => {
    if (data.session_id !== sessionId) return
    if (data.type === 'agent_chunk') {
      setBuffer(prev => prev + (data.delta ?? ''))
    } else if (data.type === 'agent_done') {
      setStreaming(false)
      setSources(data.sources ?? [])
    } else if (data.type === 'agent_error') {
      setStreaming(false)
      setBuffer(prev => prev + `\n\n⚠ Error: ${data.detail}`)
    }
  }, [sessionId])

  const { status, send } = useWebSocket(`/ws/agent/${sessionId}`, handleMessage)
  sendRef.current = send

  const sendMessage = useCallback((message: string, assetId?: string, history?: any[]) => {
    setBuffer('')
    setSources([])
    setStreaming(true)
    sendRef.current?.({ message, asset_id: assetId, history })
  }, [])

  const reset = useCallback(() => { setBuffer(''); setSources([]); setStreaming(false) }, [])

  return { status, streaming, buffer, sources, sendMessage, reset }
}
