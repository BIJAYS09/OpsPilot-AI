'use client'
import { use, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getLatestReadings, getSensorHistory, getFailureTimeline } from '@/lib/api'
import { useSensorStream } from '@/lib/websocket'
import {
  Panel, AlertBadge, AssetTypeTag, PageHeader, Skeleton, Empty,
} from '@/components/ui'
import { SensorChart } from '@/components/charts/SensorChart'
import { Radio, TrendingDown, ChevronDown, ChevronUp } from 'lucide-react'
import { clsx } from 'clsx'
import { formatDistanceToNow } from 'date-fns'

export default function AssetDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const [expanded, setExpanded] = useState<string | null>(null)

  const latest   = useQuery({ queryKey: ['latest', id],   queryFn: () => getLatestReadings(id), refetchInterval: 10_000 })
  const failures = useQuery({ queryKey: ['failures', id], queryFn: () => getFailureTimeline(id) })

  const histQ = useQuery({
    queryKey: ['history', id, expanded],
    queryFn:  () => getSensorHistory(id, expanded!, 24),
    enabled:  !!expanded,
  })

  // Live stream overlay — merges into latest readings
  const { readings: liveReadings, lastUpdate, status } = useSensorStream(id)

  const readings = latest.data?.readings?.map(r => {
    const live = liveReadings[r.sensor]
    return live ? { ...r, ...live } : r
  }) ?? []

  const assetType = readings[0]?.asset_id
    ? (id.includes('TRB') ? 'turbine' : id.includes('CMP') ? 'compressor' : 'pump')
    : 'unknown'

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader
        title={id}
        subtitle={lastUpdate ? `Live · ${formatDistanceToNow(lastUpdate, { addSuffix: true })}` : 'Loading...'}
        actions={
          <div className="flex items-center gap-2">
            <AssetTypeTag type={assetType} />
            <div className={clsx(
              'flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded border',
              status === 'connected'
                ? 'text-ok border-ok/20 bg-ok/5'
                : 'text-ink-faint border-bg-border bg-bg-muted'
            )}>
              <Radio size={9} />
              {status === 'connected' ? 'LIVE' : status.toUpperCase()}
            </div>
          </div>
        }
      />

      {/* Active failure banner */}
      {readings.some(r => r.is_failure) && (
        <div className="flex items-center gap-3 bg-danger/5 border border-danger/30 rounded-panel px-4 py-3 animate-slide-in">
          <div className="w-2 h-2 rounded-full bg-danger animate-pulse" />
          <div className="flex-1">
            <p className="text-sm font-medium text-danger">Active Failure Detected</p>
            <p className="text-xs font-mono text-danger/80">
              {readings.find(r => r.is_failure)?.failure_name}
            </p>
          </div>
          {readings.find(r => r.rul_hours != null) && (
            <div className="flex items-center gap-1 text-warn font-mono text-sm">
              <TrendingDown size={14} />
              RUL: {readings.find(r => r.rul_hours != null)?.rul_hours?.toFixed(0)}h
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Sensor list */}
        <div className="lg:col-span-1">
          <Panel title="Sensor Readings" subtitle="Click a sensor to see 24h chart">
            {latest.isLoading ? (
              <div className="p-3 space-y-2">{Array(6).fill(0).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
            ) : !readings.length ? (
              <Empty message="No readings available" />
            ) : (
              <div className="divide-y divide-bg-border/60">
                {readings.map(r => (
                  <button
                    key={r.sensor}
                    onClick={() => setExpanded(expanded === r.sensor ? null : r.sensor)}
                    className={clsx(
                      'w-full flex items-center gap-3 px-4 py-3 hover:bg-bg-raised transition-colors text-left',
                      expanded === r.sensor && 'bg-bg-raised border-l-2 border-brand'
                    )}>
                    <div className={clsx('w-1.5 h-1.5 rounded-full shrink-0',
                      r.alert_level === 'CRITICAL' ? 'bg-danger animate-pulse'
                      : r.alert_level === 'WARNING'  ? 'bg-warn animate-pulse'
                      : 'bg-ok'
                    )} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-mono text-ink-muted truncate">{r.sensor.replace(/_/g, ' ')}</p>
                      <p className={clsx('text-sm font-semibold tabular-nums',
                        r.alert_level === 'CRITICAL' ? 'text-danger'
                        : r.alert_level === 'WARNING' ? 'text-warn'
                        : 'text-ink'
                      )}>
                        {r.value != null ? r.value.toFixed(3) : 'N/A'}
                        <span className="text-[10px] text-ink-faint ml-1">{r.unit}</span>
                      </p>
                    </div>
                    <AlertBadge level={r.alert_level} />
                    {expanded === r.sensor ? <ChevronUp size={12} className="text-ink-faint" /> : <ChevronDown size={12} className="text-ink-faint" />}
                  </button>
                ))}
              </div>
            )}
          </Panel>
        </div>

        {/* Chart area */}
        <div className="lg:col-span-2 space-y-4">
          {expanded ? (
            <Panel
              title={expanded.replace(/_/g, ' ')}
              subtitle="24-hour history · 30-min buckets"
            >
              <div className="p-4">
                {histQ.isLoading ? <Skeleton className="h-44" /> :
                 !histQ.data?.data.length ? <Empty message="No history data" /> : (
                  <SensorChart
                    data={histQ.data.data}
                    sensor={expanded}
                    unit={readings.find(r => r.sensor === expanded)?.unit ?? ''}
                    height={200}
                  />
                )}
              </div>
            </Panel>
          ) : (
            <div className="panel flex items-center justify-center h-64 border-dashed">
              <p className="text-sm text-ink-faint font-mono">← Select a sensor to view history</p>
            </div>
          )}

          {/* Failure timeline */}
          {failures.data && failures.data.length > 0 && (
            <Panel title="Failure Timeline">
              <div className="divide-y divide-bg-border">
                {failures.data.map((f: any, i: number) => (
                  <div key={i} className="px-4 py-3 flex items-start gap-4">
                    <div className="w-2 h-2 mt-1 rounded-full bg-danger shrink-0" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-danger">{f.failure_name}</p>
                      <p className="text-[10px] font-mono text-ink-faint mt-0.5">
                        First detected: {new Date(f.first_detected).toLocaleString()}
                        · {f.affected_readings?.toLocaleString()} affected readings
                      </p>
                    </div>
                    {f.min_rul_hours != null && (
                      <span className="text-xs font-mono text-warn">RUL {f.min_rul_hours.toFixed(0)}h</span>
                    )}
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}
