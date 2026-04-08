'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getMaintenance, getAssets, type MaintenanceLog } from '@/lib/api'
import { PageHeader, KpiCard, Panel, Skeleton, Empty, AlertBadge } from '@/components/ui'
import { format, parseISO } from 'date-fns'
import { clsx } from 'clsx'
import { Wrench, Euro, CheckCircle, Clock, AlertTriangle } from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts'

const STATUS_STYLES: Record<string, string> = {
  COMPLETED:   'text-ok   bg-ok/10   border-ok/20',
  IN_PROGRESS: 'text-brand  bg-brand/10  border-brand/20',
  PENDING:     'text-warn bg-warn/10 border-warn/20',
}

const SEV_STYLES: Record<string, string> = {
  LOW:      'text-ok     bg-ok/10     border-ok/20',
  MEDIUM:   'text-brand  bg-brand/10  border-brand/20',
  HIGH:     'text-warn   bg-warn/10   border-warn/20',
  CRITICAL: 'text-danger bg-danger/10 border-danger/20',
}

export default function MaintenancePage() {
  const [assetFilter, setAssetFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)

  const assets = useQuery({ queryKey: ['assets'],      queryFn: getAssets })
  const logs   = useQuery({
    queryKey: ['maintenance', assetFilter, statusFilter],
    queryFn:  () => getMaintenance(assetFilter || undefined, 100),
    refetchInterval: 30_000,
  })

  const allLogs = logs.data?.logs ?? []
  const filtered = allLogs.filter(l =>
    (!statusFilter || l.status === statusFilter)
  )

  // KPI calculations
  const totalCost   = allLogs.reduce((s, l) => s + (l.cost_eur ?? 0), 0)
  const pending     = allLogs.filter(l => l.status === 'PENDING').length
  const inProgress  = allLogs.filter(l => l.status === 'IN_PROGRESS').length
  const critical    = allLogs.filter(l => l.severity === 'CRITICAL').length

  // Cost by asset for chart
  const costByAsset: Record<string, number> = {}
  for (const l of allLogs) {
    costByAsset[l.asset_id] = (costByAsset[l.asset_id] ?? 0) + (l.cost_eur ?? 0)
  }
  const costChart = Object.entries(costByAsset)
    .map(([name, cost]) => ({ name, cost: Math.round(cost) }))
    .sort((a, b) => b.cost - a.cost)

  return (
    <div className="p-6 space-y-5 animate-fade-in">
      <PageHeader title="Maintenance" subtitle={`${allLogs.length} work orders`} />

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total cost"   value={`€${(totalCost / 1000).toFixed(1)}k`} accent="brand" />
        <KpiCard label="Pending"      value={pending}    accent={pending > 5 ? 'warn' : 'default'} />
        <KpiCard label="In progress"  value={inProgress} accent="brand" />
        <KpiCard label="Critical jobs" value={critical}  accent={critical > 0 ? 'danger' : 'default'} pulse={critical > 0} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Log table */}
        <div className="lg:col-span-2 space-y-3">
          {/* Filters */}
          <div className="flex gap-2 flex-wrap">
            <select
              value={assetFilter}
              onChange={e => setAssetFilter(e.target.value)}
              className="bg-bg-raised border border-bg-border rounded-lg px-3 py-1.5 text-xs font-mono text-ink-muted focus:outline-none focus:border-brand/40">
              <option value="">All assets</option>
              {assets.data?.map(a => <option key={a.asset_id} value={a.asset_id}>{a.asset_id}</option>)}
            </select>

            {(['', 'PENDING', 'IN_PROGRESS', 'COMPLETED'] as const).map(s => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={clsx(
                  'text-xs font-mono px-3 py-1.5 rounded-lg border transition-colors',
                  statusFilter === s
                    ? 'border-brand/40 bg-brand/10 text-brand'
                    : 'border-bg-border text-ink-faint hover:text-ink hover:bg-bg-raised'
                )}>
                {s || 'ALL'}
              </button>
            ))}
          </div>

          <Panel title="Work Orders" subtitle={`${filtered.length} records`}>
            {logs.isLoading ? (
              <div className="p-4 space-y-2">{Array(8).fill(0).map((_, i) => <Skeleton key={i} className="h-14" />)}</div>
            ) : !filtered.length ? (
              <Empty message="No maintenance records" />
            ) : (
              <div className="divide-y divide-bg-border overflow-y-auto max-h-[65vh]">
                {filtered.map(log => (
                  <LogRow
                    key={log.log_id} log={log}
                    expanded={expanded === log.log_id}
                    onToggle={() => setExpanded(expanded === log.log_id ? null : log.log_id)}
                  />
                ))}
              </div>
            )}
          </Panel>
        </div>

        {/* Cost breakdown chart */}
        <div className="space-y-4">
          <Panel title="Cost by Asset" subtitle="Total spend (€)">
            {logs.isLoading ? (
              <div className="p-4"><Skeleton className="h-48" /></div>
            ) : !costChart.length ? (
              <Empty message="No cost data" />
            ) : (
              <div className="px-4 pb-4 pt-2">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={costChart}
                    layout="vertical"
                    margin={{ top: 0, right: 8, left: 12, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={v => `€${(v/1000).toFixed(1)}k`} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={54} />
                    <Tooltip
                      contentStyle={{ background: '#0d1520', border: '1px solid #1e2d42', borderRadius: 8, fontSize: 11 }}
                      formatter={(v: any) => [`€${Number(v).toLocaleString()}`, 'Cost']}
                    />
                    <Bar dataKey="cost" fill="#00c2ff" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Panel>

          {/* Severity breakdown */}
          <Panel title="Severity Breakdown">
            <div className="p-4 space-y-2">
              {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map(sev => {
                const count = allLogs.filter(l => l.severity === sev).length
                const pct   = allLogs.length ? (count / allLogs.length) * 100 : 0
                return (
                  <div key={sev}>
                    <div className="flex justify-between mb-1">
                      <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded border', SEV_STYLES[sev])}>
                        {sev}
                      </span>
                      <span className="text-xs font-mono text-ink-muted">{count}</span>
                    </div>
                    <div className="h-1.5 bg-bg-base rounded-full overflow-hidden">
                      <div
                        className={clsx(
                          'h-full rounded-full transition-all',
                          sev === 'CRITICAL' ? 'bg-danger'
                          : sev === 'HIGH'   ? 'bg-warn'
                          : sev === 'MEDIUM' ? 'bg-brand'
                          : 'bg-ok'
                        )}
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}

// ── Log row ───────────────────────────────────────────────────────────────────

function LogRow({ log, expanded, onToggle }: {
  log: MaintenanceLog; expanded: boolean; onToggle: () => void
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        className={clsx(
          'w-full flex items-start gap-3 px-4 py-3 hover:bg-bg-raised transition-colors text-left',
          expanded && 'bg-bg-raised border-l-2 border-brand'
        )}>
        <div className="mt-0.5">
          <Wrench size={13} className="text-ink-faint" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono text-brand">{log.asset_id}</span>
            <span className="text-xs text-ink truncate">{log.log_type}</span>
            {log.parts_replaced && log.parts_replaced !== 'None' && (
              <span className="text-[10px] text-ink-faint font-mono">· {log.parts_replaced}</span>
            )}
          </div>
          {log.description && (
            <p className="text-[10px] text-ink-muted mt-0.5 line-clamp-1">{log.description}</p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {log.severity && (
            <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded border', SEV_STYLES[log.severity] ?? '')}>
              {log.severity}
            </span>
          )}
          {log.status && (
            <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded border', STATUS_STYLES[log.status] ?? '')}>
              {log.status.replace('_', ' ')}
            </span>
          )}
          {log.cost_eur != null && (
            <span className="text-xs font-mono text-ink-muted">€{log.cost_eur.toLocaleString()}</span>
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-3 pt-1 bg-bg-raised animate-slide-in border-l-2 border-brand">
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs font-mono">
            {[
              ['Technician', log.technician],
              ['Site', log.site],
              ['Created', log.created_at ? format(parseISO(log.created_at), 'dd MMM yyyy HH:mm') : '—'],
              ['Completed', log.completed_at ? format(parseISO(log.completed_at), 'dd MMM yyyy HH:mm') : '—'],
              ['Parts', log.parts_replaced || '—'],
              ['Cost', log.cost_eur != null ? `€${log.cost_eur.toLocaleString()}` : '—'],
            ].map(([k, v]) => (
              <div key={k as string}>
                <span className="text-ink-faint">{k}: </span>
                <span className="text-ink">{v}</span>
              </div>
            ))}
          </div>
          {log.description && (
            <p className="text-[10px] text-ink-muted mt-2 border-t border-bg-border pt-2">{log.description}</p>
          )}
        </div>
      )}
    </div>
  )
}
