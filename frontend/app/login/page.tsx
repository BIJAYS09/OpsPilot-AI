'use client'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/store/authStore'
import { Zap, Eye, EyeOff, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'

const DEMO_USERS = [
  { label: 'Operator',  email: 'operator@plant.com',  password: 'operator123' },
  { label: 'Engineer',  email: 'engineer@plant.com',  password: 'engineer123' },
  { label: 'Admin',     email: 'admin@plant.com',     password: 'admin123'    },
]

export default function LoginPage() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [showPw,   setShowPw]   = useState(false)
  const [error,    setError]    = useState('')
  const { login, loading, user } = useAuthStore()
  const router = useRouter()

  useEffect(() => { if (user) router.replace('/dashboard') }, [user, router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    try {
      await login(email, password)
      router.replace('/dashboard')
    } catch {
      setError('Invalid email or password')
    }
  }

  function fillDemo(u: typeof DEMO_USERS[0]) {
    setEmail(u.email); setPassword(u.password); setError('')
  }

  return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center px-4">
      {/* Background grid */}
      <div className="absolute inset-0 bg-[linear-gradient(rgba(0,194,255,0.03)_1px,transparent_1px),linear-gradient(90deg,rgba(0,194,255,0.03)_1px,transparent_1px)] bg-[size:48px_48px] pointer-events-none" />

      <div className="w-full max-w-sm relative">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-brand/10 border border-brand/30 mb-4">
            <Zap size={22} className="text-brand" />
          </div>
          <h1 className="text-2xl font-semibold text-ink">Energy Co-pilot</h1>
          <p className="text-xs text-ink-muted font-mono mt-1">AI OPERATIONS PLATFORM</p>
        </div>

        {/* Card */}
        <div className="panel px-6 py-7 space-y-5">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-[10px] font-mono text-ink-faint uppercase tracking-widest mb-1.5">
                Email
              </label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                required autoFocus
                className="w-full bg-bg-base border border-bg-border rounded-lg px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20 transition-colors"
                placeholder="you@plant.com"
              />
            </div>

            <div>
              <label className="block text-[10px] font-mono text-ink-faint uppercase tracking-widest mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password} onChange={e => setPassword(e.target.value)}
                  required
                  className="w-full bg-bg-base border border-bg-border rounded-lg px-3 py-2.5 pr-10 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/20 transition-colors"
                  placeholder="••••••••"
                />
                <button type="button" onClick={() => setShowPw(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink transition-colors">
                  {showPw ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 text-danger text-xs bg-danger/5 border border-danger/20 rounded-lg px-3 py-2">
                <AlertCircle size={13} />
                {error}
              </div>
            )}

            <button
              type="submit" disabled={loading}
              className={clsx(
                'w-full py-2.5 rounded-lg text-sm font-medium transition-all',
                loading
                  ? 'bg-brand/20 text-brand/50 cursor-not-allowed'
                  : 'bg-brand text-bg-base hover:bg-brand/90 active:scale-[0.98]'
              )}>
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-3.5 h-3.5 border-2 border-brand/30 border-t-brand rounded-full animate-spin" />
                  Signing in...
                </span>
              ) : 'Sign In'}
            </button>
          </form>

          {/* Demo logins */}
          <div>
            <p className="text-[10px] font-mono text-ink-faint uppercase tracking-widest mb-2">
              Demo accounts
            </p>
            <div className="grid grid-cols-3 gap-2">
              {DEMO_USERS.map(u => (
                <button key={u.email} onClick={() => fillDemo(u)}
                  className="text-[10px] font-mono py-1.5 rounded-lg border border-bg-border bg-bg-raised text-ink-muted hover:text-ink hover:border-brand/30 transition-colors">
                  {u.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
