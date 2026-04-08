'use client'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { getAssets, getHealthSummary } from '@/lib/api'
import { PageHeader, AssetTypeTag, AlertBadge, Skeleton } from '@/components/ui'
import { clsx } from 'clsx'

export default function AssetsPage() {
  const assets = useQuery({ queryKey: ['assets'],  queryFn: getAssets })
  const health = useQuery({ queryKey: ['health'],  queryFn: getHealthSummary, refetchInterval: 15_000 })

  const healthMap = Object.fromEntries(
    (health.data?.assets ?? []).map(a => [a.asset_id, a])
  )

  return (
    <div className="p-6 animate-fade-in">
      <PageHeader title="Assets" subtitle={`${assets.data?.length ?? 0} monitored assets`} />

      <div className="panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bg-border">
              {['Asset ID', 'Type', 'Site', 'Status', 'Failure', 'RUL', ''].map(h => (
                <th key={h} className="text-left text-[10px] font-mono text-ink-faint uppercase tracking-widest px-4 py-3">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {assets.isLoading ? (
              Array(7).fill(0).map((_, i) => (
                <tr key={i} className="border-b border-bg-border">
                  {Array(7).fill(0).map((_, j) => (
                    <td key={j} className="px-4 py-3"><Skeleton className="h-4" /></td>
                  ))}
                </tr>
              ))
            ) : assets.data?.map(a => {
              const h = healthMap[a.asset_id]
              const sev = h?.severity_score ?? 0
              return (
                <tr key={a.asset_id}
                  className="border-b border-bg-border hover:bg-bg-raised transition-colors cursor-pointer">
                  <td className="px-4 py-3 font-mono text-brand">{a.asset_id}</td>
                  <td className="px-4 py-3"><AssetTypeTag type={a.asset_type} /></td>
                  <td className="px-4 py-3 text-ink-muted">{a.site}</td>
                  <td className="px-4 py-3">
                    <AlertBadge level={sev === 2 ? 'CRITICAL' : sev === 1 ? 'WARNING' : 'NORMAL'} />
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-danger">
                    {h?.failure_name ?? <span className="text-ink-faint">—</span>}
                  </td>
                  <td className="px-4 py-3 text-xs font-mono text-warn">
                    {h?.min_rul_hours != null ? `${h.min_rul_hours.toFixed(0)}h` : <span className="text-ink-faint">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/dashboard/assets/${a.asset_id}`}
                      className="text-[10px] font-mono text-brand hover:text-brand/80 border border-brand/20 px-2 py-1 rounded hover:bg-brand/5 transition-colors">
                      VIEW →
                    </Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
