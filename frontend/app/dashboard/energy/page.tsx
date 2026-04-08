'use client'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getEnergySummary, getLivePower } from '@/lib/api'
import { PageHeader, KpiCard, Panel, Skeleton, Empty } from '@/components/ui'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, BarChart, Bar, Legend,
  RadialBarChart, RadialBar, LineChart, Line,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { Zap, TrendingUp, Activity, Clock } from 'lucide-react'
import { clsx } from 'clsx'

export default function EnergyPage() {
  const [days, setDays] = useState(14)

  const summary  = useQuery({ queryKey: ['energy', days], queryFn: () => getEnergySummary(days), refetchInterval: 60_000 })
  const livePower = useQuery({ queryKey: ['live-power'],  queryFn: getLivePower,                  refetchInterval: 10_000 })

  const data = summary.data?.data ?? []

  // Aggregate KPIs
  const totalMwh    = data.reduce((s, d) => s + d.total_mwh, 0)
  const peakPower   = Math.max(0, ...data.map(d => d.peak_power_mw))
  const avgAvail    = data.length ? data.reduce((s, d) => s + d.availability_pct, 0) / data.length : 0

  // Group by site for stacked chart
  const byDay: Record<string, any> = {}
  for (const d of data) {
    const label = format(parseISO(d.day as string), 'MM/dd')
    if (!byDay[label]) byDay[label] = { label }
    byDay[label][d.site] = (byDay[label][d.site] ?? 0) + d.total_mwh
  }
  const stackedData = Object.values(byDay).reverse()

  // Live power table
  const live = livePower.data ?? []
  const liveTotalMw = live.reduce((s: number, d: any) => s + (d.power_mw ?? 0), 0)

  // Availability radial data
  const availData = [
    { name: 'Available',   value: Math.round(avgAvail),       fill: '#10d17a' },
    { name: 'Unavailable', value: Math.round(100 - avgAvail), fill: '#1e2d42' },
  ]

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      <PageHeader
        title="Energy Analytics"
        subtitle="Production, availability, and grid performance"
        actions={
          <div className="flex gap-1">
            {[7, 14, 30].map(d => (
              <button key={d} onClick={() => setDays(d)}
                className={clsx(
                  'text-xs font-mono px-3 py-1.5 rounded-lg border transition-colors',
                  days === d
                    ? 'border-brand/40 bg-brand/10 text-brand'
                    : 'border-bg-border text-ink-faint hover:text-ink hover:bg-bg-raised'
                )}>
                {d}d
              </button>
            ))}
          </div>
        }
      />

      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard label={`Total production (${days}d)`} value={totalMwh.toFixed(0)} sub="MWh" accent="brand" />
        <KpiCard label="Peak output"       value={peakPower.toFixed(1)}  sub="MW"  accent="ok"   />
        <KpiCard label="Avg availability"  value={`${avgAvail.toFixed(1)}%`}        accent={avgAvail > 95 ? 'ok' : avgAvail > 85 ? 'warn' : 'danger'} />
        <KpiCard label="Live total output" value={liveTotalMw.toFixed(1)} sub="MW"  accent="brand" pulse />
      </div>

      {/* Live power table */}
      <Panel title="Live Power Output" subtitle="Current output per asset · refreshes every 10s">
        {livePower.isLoading ? (
          <div className="p-4 space-y-2">{Array(7).fill(0).map((_, i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : !live.length ? (
          <Empty message="No live power data" />
        ) : (
          <div className="divide-y divide-bg-border">
            {live.map((d: any) => {
              const pct = d.power_mw && 50 ? Math.min(100, (d.power_mw / 80) * 100) : 0
              return (
                <div key={d.asset_id} className="flex items-center gap-4 px-4 py-3">
                  <div className="w-20">
                    <p className="text-xs font-mono text-brand">{d.asset_id}</p>
                    <p className="text-[10px] text-ink-faint">{d.site}</p>
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-mono text-ink tabular-nums">
                        {d.power_mw?.toFixed(2)} MW
                      </span>
                      <span className={clsx(
                        'text-[10px] font-mono',
                        d.availability ? 'text-ok' : 'text-danger'
                      )}>
                        {d.availability ? 'ONLINE' : 'OFFLINE'}
                      </span>
                    </div>
                    <div className="h-1.5 bg-bg-base rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-brand transition-all duration-700"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                  <div className="text-right text-[10px] font-mono text-ink-faint w-24">
                    <p>{d.frequency_hz?.toFixed(3)} Hz</p>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Panel>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Production by site stacked */}
        <div className="lg:col-span-2">
          <Panel title="Daily Energy Production" subtitle="MWh by site">
            {summary.isLoading ? (
              <div className="p-4"><Skeleton className="h-52" /></div>
            ) : (
              <div className="px-4 pb-4 pt-2">
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={stackedData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip
                      contentStyle={{ background: '#0d1520', border: '1px solid #1e2d42', borderRadius: 8, fontSize: 11 }}
                      labelStyle={{ color: '#7a96b8' }} itemStyle={{ color: '#e2eaf6' }}
                    />
                    <Bar dataKey="Alpha Plant"  stackId="a" fill="#00c2ff" radius={[0,0,0,0]} />
                    <Bar dataKey="Beta Station" stackId="a" fill="#10d17a" radius={[3,3,0,0]} />
                    <Legend wrapperStyle={{ fontSize: 11, color: '#7a96b8' }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </Panel>
        </div>

        {/* Availability gauge */}
        <Panel title="Avg Availability" subtitle={`${days}-day window`}>
          {summary.isLoading ? (
            <div className="p-4"><Skeleton className="h-52" /></div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full pb-4 pt-2">
              <div className="relative">
                <ResponsiveContainer width={180} height={180}>
                  <RadialBarChart
                    cx="50%" cy="50%"
                    innerRadius="65%" outerRadius="90%"
                    startAngle={90} endAngle={-270}
                    data={availData}>
                    <RadialBar dataKey="value" cornerRadius={6} />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="text-center">
                    <p className="text-2xl font-semibold text-ok tabular-nums">{avgAvail.toFixed(1)}%</p>
                    <p className="text-[10px] font-mono text-ink-faint">AVAILABLE</p>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-x-6 gap-y-1 mt-2">
                {data.slice(0, 4).map((d, i) => (
                  <div key={i} className="text-[10px] font-mono text-ink-faint">
                    <span className={clsx(d.availability_pct > 95 ? 'text-ok' : 'text-warn')}>
                      {d.availability_pct.toFixed(0)}%
                    </span>
                    {' '}{format(parseISO(d.day as string), 'MM/dd')} · {d.site.split(' ')[0]}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      </div>

      {/* Frequency trend */}
      <Panel title="Grid Frequency Trend" subtitle="50 Hz nominal · all assets">
        {summary.isLoading ? (
          <div className="p-4"><Skeleton className="h-32" /></div>
        ) : (
          <div className="px-4 pb-4 pt-1">
            <FrequencyChart live={live} />
          </div>
        )}
      </Panel>
    </div>
  )
}

function FrequencyChart({ live }: { live: any[] }) {
  const data = live.map((d: any, i: number) => ({
    name: d.asset_id,
    freq: d.frequency_hz,
  }))
  if (!data.length) return <Empty message="No frequency data" />
  return (
    <ResponsiveContainer width="100%" height={120}>
      <BarChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} domain={[49.9, 50.1]} />
        <Tooltip
          contentStyle={{ background: '#0d1520', border: '1px solid #1e2d42', borderRadius: 8, fontSize: 11 }}
          formatter={(v: any) => [`${Number(v).toFixed(3)} Hz`, 'Frequency']}
        />
        {/* 50 Hz nominal reference would need ReferenceLine - omitted for brevity */}
        <Bar dataKey="freq" fill="#a78bfa" radius={[3,3,0,0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
