'use client'
import { clsx } from 'clsx'
import Link from 'next/link'
import { AlertTriangle, CheckCircle, Clock, TrendingDown } from 'lucide-react'
import type { AssetHealthItem } from '@/lib/api'
import { AssetTypeTag } from '@/components/ui'

interface Props { asset: AssetHealthItem }

const SEVERITY = {
  0: { border: 'border-ok/20',     bg: 'hover:bg-ok/5',     ring: 'bg-ok',     icon: CheckCircle,     iconColor: 'text-ok'    },
  1: { border: 'border-warn/30',   bg: 'hover:bg-warn/5',   ring: 'bg-warn',   icon: AlertTriangle,   iconColor: 'text-warn'  },
  2: { border: 'border-danger/40', bg: 'hover:bg-danger/5', ring: 'bg-danger', icon: AlertTriangle,   iconColor: 'text-danger' },
} as const

export function AssetCard({ asset }: Props) {
  const sev = SEVERITY[asset.severity_score as 0|1|2] ?? SEVERITY[0]
  const Icon = sev.icon

  return (
    <Link href={`/dashboard/assets/${asset.asset_id}`}>
      <div className={clsx(
        'panel border px-4 py-4 cursor-pointer transition-all duration-200',
        sev.border, sev.bg,
        asset.severity_score === 2 && 'shadow-glow-err',
        asset.severity_score === 1 && 'shadow-glow-warn',
      )}>
        {/* Header row */}
        <div className="flex items-start justify-between mb-3">
          <div>
            <p className="text-sm font-semibold text-ink font-mono">{asset.asset_id}</p>
            <p className="text-[10px] text-ink-muted mt-0.5">{asset.site}</p>
          </div>
          <div className="flex items-center gap-2">
            <AssetTypeTag type={asset.asset_type} />
            <div className={clsx('w-2 h-2 rounded-full', sev.ring,
              asset.severity_score > 0 && 'animate-pulse')} />
          </div>
        </div>

        {/* Status line */}
        <div className="flex items-center gap-2 mb-3">
          <Icon size={13} className={sev.iconColor} />
          <span className={clsx('text-xs font-medium', sev.iconColor)}>
            {asset.severity_score === 0 ? 'Healthy'
             : asset.severity_score === 1 ? 'Warning'
             : 'Critical'}
          </span>
        </div>

        {/* Failure info */}
        {asset.has_active_failure && asset.failure_name && (
          <div className="text-[10px] font-mono text-danger bg-danger/5 border border-danger/15 rounded px-2 py-1 mb-2">
            {asset.failure_name}
          </div>
        )}

        {/* RUL */}
        {asset.min_rul_hours != null && (
          <div className="flex items-center gap-1.5 text-[10px] font-mono text-warn">
            <TrendingDown size={10} />
            RUL: <span className="font-semibold">{asset.min_rul_hours.toFixed(0)}h</span>
          </div>
        )}

        {/* Last update */}
        {asset.last_updated && (
          <div className="flex items-center gap-1 text-[9px] text-ink-faint mt-2 font-mono">
            <Clock size={9} />
            {new Date(asset.last_updated).toLocaleTimeString()}
          </div>
        )}
      </div>
    </Link>
  )
}
