import { clsx } from 'clsx'
import { ReactNode } from 'react'

// ── KPI Stat Card ─────────────────────────────────────────────────────────────
interface KpiProps {
  label: string
  value: string | number
  sub?: string
  accent?: 'ok' | 'warn' | 'danger' | 'brand' | 'default'
  pulse?: boolean
}

export function KpiCard({ label, value, sub, accent = 'default', pulse }: KpiProps) {
  const colors: Record<string, string> = {
    ok:      'text-ok',
    warn:    'text-warn',
    danger:  'text-danger',
    brand:   'text-brand',
    default: 'text-ink',
  }
  return (
    <div className="panel px-4 py-3">
      <p className="text-[10px] font-mono text-ink-faint uppercase tracking-widest mb-1">{label}</p>
      <div className="flex items-baseline gap-2">
        <span className={clsx('text-2xl font-semibold tabular-nums', colors[accent], pulse && 'animate-pulse-slow')}>
          {value}
        </span>
        {sub && <span className="text-xs text-ink-muted font-mono">{sub}</span>}
      </div>
    </div>
  )
}

// ── Alert Badge ───────────────────────────────────────────────────────────────
export function AlertBadge({ level }: { level: string }) {
  const cls: Record<string, string> = {
    NORMAL:      'badge-ok',
    WARNING:     'badge-warn',
    CRITICAL:    'badge-danger',
    MAINTENANCE: 'badge-maint',
  }
  return <span className={cls[level] ?? 'badge-maint'}>{level}</span>
}

// ── Panel with header ─────────────────────────────────────────────────────────
interface PanelProps {
  title: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}

export function Panel({ title, subtitle, action, children, className }: PanelProps) {
  return (
    <div className={clsx('panel flex flex-col', className)}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-bg-border">
        <div>
          <h3 className="text-sm font-medium text-ink">{title}</h3>
          {subtitle && <p className="text-[10px] font-mono text-ink-faint mt-0.5">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}

// ── Asset type icon ───────────────────────────────────────────────────────────
export function AssetTypeTag({ type }: { type: string }) {
  const cfg: Record<string, { label: string; color: string }> = {
    turbine:    { label: 'TURBINE',    color: 'text-brand bg-brand/10 border-brand/20' },
    compressor: { label: 'COMPRESSOR', color: 'text-purple-400 bg-purple-400/10 border-purple-400/20' },
    pump:       { label: 'PUMP',       color: 'text-teal-400 bg-teal-400/10 border-teal-400/20' },
  }
  const { label, color } = cfg[type] ?? { label: type.toUpperCase(), color: 'text-ink-muted bg-bg-muted border-bg-border' }
  return (
    <span className={clsx('text-[10px] font-mono px-1.5 py-0.5 rounded border', color)}>
      {label}
    </span>
  )
}

// ── Loading skeleton ──────────────────────────────────────────────────────────
export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx('animate-pulse bg-bg-raised rounded', className)} />
}

// ── Empty state ───────────────────────────────────────────────────────────────
export function Empty({ message }: { message: string }) {
  return (
    <div className="flex items-center justify-center h-full py-12">
      <p className="text-sm text-ink-faint font-mono">{message}</p>
    </div>
  )
}

// ── Page header ───────────────────────────────────────────────────────────────
export function PageHeader({ title, subtitle, actions }: {
  title: string; subtitle?: string; actions?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between px-6 pt-6 pb-4">
      <div>
        <h1 className="text-xl font-semibold text-ink">{title}</h1>
        {subtitle && <p className="text-xs text-ink-muted mt-0.5 font-mono">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}
