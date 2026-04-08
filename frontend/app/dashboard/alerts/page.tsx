'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getAlerts } from '@/lib/api'
import { useAlertStream } from '@/lib/websocket'
import { PageHeader, AlertBadge, KpiCard, Panel, Skeleton } from '@/components/ui'
import { Radio, TrendingDown, Clock } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { clsx } from 'clsx'

export default function AlertsPage() {
  const [hours, setHours]   = useState(24)
  const [level, setLevel]   = useState<'ALL' | 'WARNING' | 'CRITICAL'>('ALL')
  const [showLive, setShowLive] = useState(true)

  const historical = useQuery({
    queryKey: ['alerts', hours, level],
    queryFn:  () => getAlerts(hours, 200),
    refetchInterval: 20_000,
  })

  const { alerts: liveAlerts, status } = useAlertStream()

  const filteredLive = liveAlerts.filter(a =>
    level === 'ALL' || a.alert_level === level
  )

  const filteredHistorical = (historical.data?.alerts ?? []).filter(a =>
    level === 'ALL' || a.alert_level === level
  )

  const critCount = liveAlerts.filter(a => a.alert_level === 'CRITICAL').length
  const warnCount = liveAlerts.filter(a => a.alert_level === 'WARNING').length

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        title="Alert Inbox"
        subtitle={`Live stream · ${liveAlerts.length} events captured`}
        actions={
          <div className={clsx(
            'flex items-center gap-1.5 text-xs font-mono px-3 py-1.5 rounded-lg border',
            status === 'connected' ? 'text-ok border-ok/30 bg-ok/5' : 'text-ink-faint border-bg-border'
          )}>
            <Radio size={11} />
            {status === 'connected' ? 'LIVE STREAM' : status.toUpperCase()}
          </div>
        }
      />

      {/* KPI bar */}
      <div className="grid grid-cols-3 gap-3">
        <KpiCard label="Critical (live)" value={critCount} accent={critCount > 0 ? 'danger' : 'default'} pulse={critCount > 0} />
        <KpiCard label="Warning (live)"  value={warnCount} accent={warnCount > 0 ? 'warn'   : 'default'} />
        <KpiCard label="Historical"      value={historical.data?.total ?? '—'} sub={`${hours}h window`} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-xs text-ink-faint font-mono">FILTER:</span>
        {(['ALL', 'WARNING', 'CRITICAL'] as const).map(l => (
          <button key={l} onClick={() => setLevel(l)}
            className={clsx(
              'text-xs font-mono px-3 py-1.5 rounded-lg border transition-colors',
              level === l
                ? l === 'CRITICAL' ? 'bg-danger/15 border-danger/40 text-danger'
                  : l === 'WARNING' ? 'bg-warn/15 border-warn/40 text-warn'
                  : 'bg-brand/15 border-brand/40 text-brand'
                : 'border-bg-border text-ink-muted hover:text-ink hover:bg-bg-raised'
            )}>
            {l}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-ink-faint font-mono">WINDOW:</span>
          {[6, 24, 48].map(h => (
            <button key={h} onClick={() => setHours(h)}
              className={clsx(
                'text-xs font-mono px-2 py-1 rounded border transition-colors',
                hours === h
                  ? 'border-brand/40 bg-brand/10 text-brand'
                  : 'border-bg-border text-ink-faint hover:text-ink hover:bg-bg-raised'
              )}>
              {h}h
            </button>
          ))}
        </div>
        <button onClick={() => setShowLive(v => !v)}
          className={clsx(
            'text-xs font-mono px-3 py-1.5 rounded-lg border transition-colors',
            showLive ? 'border-ok/30 bg-ok/5 text-ok' : 'border-bg-border text-ink-faint hover:bg-bg-raised'
          )}>
          {showLive ? 'LIVE ON' : 'LIVE OFF'}
        </button>
      </div>

      {/* Live alerts */}
      {showLive && filteredLive.length > 0 && (
        <Panel title="Live Alerts" subtitle="Real-time stream — newest first">
          <div className="divide-y divide-bg-border max-h-64 overflow-y-auto">
            {filteredLive.map(a => (
              <AlertRow key={a.id}
                assetId={a.asset_id} sensor={a.sensor} value={a.value}
                unit={null} level={a.alert_level} failureName={a.failure_name}
                rulHours={a.rul_hours} time={a.timestamp} isLive />
            ))}
          </div>
        </Panel>
      )}

      {/* Historical */}
      <Panel title="Historical Alerts" subtitle={`Last ${hours} hours`}>
        {historical.isLoading ? (
          <div className="p-4 space-y-2">{Array(8).fill(0).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
        ) : !filteredHistorical.length ? (
          <div className="flex items-center justify-center py-16 text-ink-faint font-mono text-sm">No alerts in this window</div>
        ) : (
          <div className="divide-y divide-bg-border overflow-y-auto max-h-[60vh]">
            {filteredHistorical.map((a, i) => (
              <AlertRow key={i}
                assetId={a.asset_id} sensor={a.sensor} value={a.value}
                unit={a.unit} level={a.alert_level} failureName={a.failure_name}
                rulHours={a.rul_hours} time={a.time} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}

function AlertRow({ assetId, sensor, value, unit, level, failureName, rulHours, time, isLive }: {
  assetId: string; sensor: string; value: number | null; unit: string | null
  level: string; failureName: string | null; rulHours: number | null; time: string; isLive?: boolean
}) {
  return (
    <div className={clsx(
      'flex items-center gap-3 px-4 py-3 hover:bg-bg-raised transition-colors',
      isLive && 'animate-slide-in',
      level === 'CRITICAL' && 'bg-danger/3',
    )}>
      <AlertBadge level={level} />
      <div className="flex-1 min-w-0">
        <p className="text-xs font-mono">
          <span className="text-brand">{assetId}</span>
          <span className="text-ink-faint mx-1">·</span>
          <span className="text-ink">{sensor.replace(/_/g, ' ')}</span>
        </p>
        {failureName && (
          <p className="text-[10px] text-danger font-mono mt-0.5">{failureName}</p>
        )}
      </div>
      {value != null && (
        <p className="text-sm font-mono text-ink tabular-nums">
          {value.toFixed(3)} <span className="text-ink-faint text-[10px]">{unit}</span>
        </p>
      )}
      {rulHours != null && (
        <div className="flex items-center gap-1 text-warn text-[10px] font-mono">
          <TrendingDown size={10} />
          {rulHours.toFixed(0)}h
        </div>
      )}
      <div className="flex items-center gap-1 text-[10px] text-ink-faint font-mono shrink-0">
        <Clock size={9} />
        {formatDistanceToNow(new Date(time), { addSuffix: true })}
      </div>
      {isLive && <span className="w-1.5 h-1.5 rounded-full bg-ok animate-pulse" />}
    </div>
  )
}
