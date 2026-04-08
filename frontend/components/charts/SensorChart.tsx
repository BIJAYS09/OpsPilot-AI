'use client'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Area, AreaChart,
} from 'recharts'
import { format } from 'date-fns'
import type { HistoryPoint } from '@/lib/api'

interface Props {
  data: HistoryPoint[]
  sensor: string
  unit: string
  warnThreshold?: number
  critThreshold?: number
  color?: string
  height?: number
}

const COLORS: Record<string, string> = {
  vibration_x:          '#00c2ff',
  vibration_y:          '#00c2ff',
  temperature_bearing:  '#f59e0b',
  temperature_exhaust:  '#ef4444',
  rotation_speed:       '#10d17a',
  power_output:         '#10d17a',
  lube_oil_pressure:    '#a78bfa',
  flow_rate:            '#22d3ee',
  motor_current:        '#f97316',
  outlet_pressure:      '#a78bfa',
  inlet_pressure:       '#64748b',
  efficiency:           '#10d17a',
  default:              '#00c2ff',
}

function CustomTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload?.length) return null
  const d = payload[0]
  return (
    <div className="bg-bg-raised border border-bg-border rounded-lg px-3 py-2 text-xs font-mono shadow-card">
      <p className="text-ink-muted mb-1">{label}</p>
      <p className="text-ink">avg <span className="text-brand font-semibold">{Number(d.value).toFixed(3)}</span> {unit}</p>
      {payload[1] && <p className="text-ink-faint">min {Number(payload[1].value).toFixed(3)}</p>}
      {payload[2] && <p className="text-ink-faint">max {Number(payload[2].value).toFixed(3)}</p>}
    </div>
  )
}

export function SensorChart({ data, sensor, unit, warnThreshold, critThreshold, height = 180 }: Props) {
  const color  = COLORS[sensor] ?? COLORS.default
  const fmtd   = data.map(d => ({
    ...d,
    label: format(new Date(d.bucket), 'HH:mm'),
    avg_value: Number(d.avg_value),
    min_value: Number(d.min_value),
    max_value: Number(d.max_value),
  }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={fmtd} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id={`g-${sensor}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
        <Tooltip content={<CustomTooltip unit={unit} />} />
        {warnThreshold && (
          <ReferenceLine y={warnThreshold} stroke="#f59e0b" strokeDasharray="4 4"
            label={{ value: 'WARN', position: 'right', fill: '#f59e0b', fontSize: 9 }} />
        )}
        {critThreshold && (
          <ReferenceLine y={critThreshold} stroke="#ef4444" strokeDasharray="4 4"
            label={{ value: 'CRIT', position: 'right', fill: '#ef4444', fontSize: 9 }} />
        )}
        <Area type="monotone" dataKey="avg_value" stroke={color} strokeWidth={1.5}
          fill={`url(#g-${sensor})`} dot={false} activeDot={{ r: 3, fill: color }} />
      </AreaChart>
    </ResponsiveContainer>
  )
}

// ── Mini sparkline (for health grid) ─────────────────────────────────────────
export function Sparkline({ data, color = '#00c2ff', height = 40 }: {
  data: number[]; color?: string; height?: number
}) {
  const fmtd = data.map((v, i) => ({ v, i }))
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={fmtd}>
        <Line type="monotone" dataKey="v" stroke={color} strokeWidth={1.5}
          dot={false} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ── Energy bar chart ──────────────────────────────────────────────────────────
import { BarChart, Bar, Legend } from 'recharts'

export function EnergyBarChart({ data }: { data: any[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="label" tick={{ fontSize: 10 }} />
        <YAxis tick={{ fontSize: 10 }} />
        <Tooltip
          contentStyle={{ background: '#0d1520', border: '1px solid #1e2d42', borderRadius: 8, fontSize: 11 }}
          labelStyle={{ color: '#7a96b8' }}
          itemStyle={{ color: '#e2eaf6' }}
        />
        <Bar dataKey="Alpha Plant" fill="#00c2ff" radius={[3,3,0,0]} />
        <Bar dataKey="Beta Station" fill="#10d17a" radius={[3,3,0,0]} />
        <Legend wrapperStyle={{ fontSize: 11, color: '#7a96b8' }} />
      </BarChart>
    </ResponsiveContainer>
  )
}
