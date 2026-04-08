'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { useAlertStream } from '@/lib/websocket'
import {
  LayoutDashboard, Gauge, AlertTriangle, MessageSquare,
  Wrench, Zap, LogOut, Radio,
} from 'lucide-react'
import { clsx } from 'clsx'

const NAV = [
  { href: '/dashboard',         label: 'Overview',    icon: LayoutDashboard },
  { href: '/dashboard/assets',  label: 'Assets',      icon: Gauge },
  { href: '/dashboard/alerts',  label: 'Alerts',      icon: AlertTriangle },
  { href: '/dashboard/energy',  label: 'Energy',      icon: Zap },
  { href: '/dashboard/maintenance', label: 'Maintenance', icon: Wrench },
  { href: '/dashboard/chat',    label: 'AI Co-pilot', icon: MessageSquare },
]

export function Sidebar() {
  const pathname = usePathname()
  const logout   = useAuthStore(s => s.logout)
  const user     = useAuthStore(s => s.user)
  const { alerts, status } = useAlertStream()

  const critCount = alerts.filter(a => a.alert_level === 'CRITICAL').length
  const warnCount = alerts.filter(a => a.alert_level === 'WARNING').length

  return (
    <aside className="w-56 shrink-0 bg-bg-surface border-r border-bg-border flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-bg-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-brand/10 border border-brand/30 flex items-center justify-center">
            <Zap size={14} className="text-brand" />
          </div>
          <div>
            <p className="text-xs font-semibold text-ink tracking-wide">ENERGY</p>
            <p className="text-[10px] text-ink-muted font-mono tracking-widest">CO-PILOT</p>
          </div>
        </div>
      </div>

      {/* Live status pill */}
      <div className="px-4 pt-3 pb-1">
        <div className={clsx(
          'flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded border',
          status === 'connected'
            ? 'text-ok bg-ok/5 border-ok/20'
            : 'text-ink-faint bg-bg-muted border-bg-border'
        )}>
          <Radio size={9} className={status === 'connected' ? 'text-ok' : 'text-ink-faint'} />
          {status === 'connected' ? 'LIVE' : status.toUpperCase()}
          {critCount > 0 && (
            <span className="ml-auto text-danger font-bold">{critCount} CRIT</span>
          )}
          {critCount === 0 && warnCount > 0 && (
            <span className="ml-auto text-warn">{warnCount} WARN</span>
          )}
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = href === '/dashboard' ? pathname === href : pathname.startsWith(href)
          const isAlerts = href.includes('alerts')
          return (
            <Link key={href} href={href} className={clsx(
              'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all',
              active
                ? 'bg-brand/10 text-brand border border-brand/20'
                : 'text-ink-muted hover:text-ink hover:bg-bg-raised',
            )}>
              <Icon size={15} className={active ? 'text-brand' : ''} />
              <span className="flex-1">{label}</span>
              {isAlerts && critCount > 0 && (
                <span className="text-[10px] font-mono bg-danger/20 text-danger px-1.5 py-0.5 rounded">
                  {critCount}
                </span>
              )}
            </Link>
          )
        })}
      </nav>

      {/* User footer */}
      <div className="px-4 py-4 border-t border-bg-border">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium text-ink">{user?.full_name ?? '—'}</p>
            <p className="text-[10px] font-mono text-ink-faint uppercase">{user?.role}</p>
          </div>
          <button onClick={logout}
            className="p-1.5 rounded-lg hover:bg-bg-raised text-ink-faint hover:text-danger transition-colors">
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  )
}
