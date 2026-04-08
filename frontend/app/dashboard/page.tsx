'use client'
import { useQuery } from '@tanstack/react-query'
import { getHealthSummary, getAlerts, getEnergySummary } from '@/lib/api'
import { KpiCard, Panel, PageHeader, Skeleton, Empty } from '@/components/ui'
import { AssetCard } from '@/components/ui/AssetCard'
import { AlertBadge } from '@/components/ui'
import { EnergyBarChart } from '@/components/charts/SensorChart'
import { format } from 'date-fns'

export default function DashboardPage() {
  const health = useQuery({ queryKey: ['health'],  queryFn: getHealthSummary, refetchInterval: 15_000 })
  const alerts = useQuery({ queryKey: ['alerts'],  queryFn: () => getAlerts(6, 30), refetchInterval: 15_000 })
  const energy = useQuery({ queryKey: ['energy7'], queryFn: () => getEnergySummary(7), refetchInterval: 60_000 })

  // Reshape energy for grouped bar chart
  const energyChart = (() => {
    if (!energy.data) return []
    const byDay: Record<string, any> = {}
    for (const d of energy.data.data) {
      const label = format(new Date(d.day), 'MM/dd')
      if (!byDay[label]) byDay[label] = { label }
      byDay[label][d.site] = d.total_mwh
    }
    return Object.values(byDay).reverse()
  })()

  const h = health.data

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <PageHeader
        title="Plant Overview"
        subtitle={`Last updated: ${new Date().toLocaleTimeString()}`}
      />

      {/* KPI bar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label="Total Assets"   value={h?.total_assets ?? '—'} />
        <KpiCard label="Critical"       value={h?.critical_count ?? '—'} accent={h?.critical_count ? 'danger' : 'default'} pulse={!!h?.critical_count} />
        <KpiCard label="Warning"        value={h?.warning_count  ?? '—'} accent={h?.warning_count  ? 'warn'   : 'default'} />
        <KpiCard label="Healthy"        value={h?.healthy_count  ?? '—'} accent="ok" />
      </div>

      {/* Asset health grid */}
      <Panel title="Asset Health" subtitle="Click any asset to view live sensor data">
        {health.isLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 p-4">
            {Array(7).fill(0).map((_, i) => <Skeleton key={i} className="h-32" />)}
          </div>
        ) : !h?.assets.length ? (
          <Empty message="No assets found" />
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 p-4">
            {h.assets.map(a => <AssetCard key={a.asset_id} asset={a} />)}
          </div>
        )}
      </Panel>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent alerts */}
        <Panel title="Recent Alerts" subtitle="Last 6 hours">
          {alerts.isLoading ? (
            <div className="p-4 space-y-2">{Array(4).fill(0).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
          ) : !alerts.data?.alerts.length ? (
            <Empty message="No alerts in last 6 hours" />
          ) : (
            <div className="divide-y divide-bg-border overflow-y-auto max-h-72">
              {alerts.data.alerts.map((a, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-2.5 hover:bg-bg-raised transition-colors">
                  <AlertBadge level={a.alert_level} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-mono text-ink truncate">
                      <span className="text-brand">{a.asset_id}</span> · {a.sensor}
                    </p>
                    {a.failure_name && (
                      <p className="text-[10px] text-danger">{a.failure_name}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs font-mono text-ink">{a.value?.toFixed(3) ?? 'N/A'} <span className="text-ink-faint">{a.unit}</span></p>
                    {a.rul_hours != null && (
                      <p className="text-[10px] font-mono text-warn">RUL {a.rul_hours.toFixed(0)}h</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        {/* Energy chart */}
        <Panel title="Energy Production" subtitle="7-day MWh by site">
          {energy.isLoading ? (
            <div className="p-4"><Skeleton className="h-48" /></div>
          ) : (
            <div className="px-4 pb-4 pt-2">
              <EnergyBarChart data={energyChart} />
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
