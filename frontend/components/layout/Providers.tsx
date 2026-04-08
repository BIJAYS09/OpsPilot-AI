'use client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useAuthStore } from '@/store/authStore'

const qc = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1 } },
})

export function Providers({ children }: { children: React.ReactNode }) {
  const hydrate = useAuthStore(s => s.hydrate)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    hydrate().finally(() => setReady(true))
  }, [hydrate])

  if (!ready) return (
    <div className="min-h-screen bg-bg-base flex items-center justify-center">
      <div className="flex gap-1">
        {[0,1,2].map(i => (
          <span key={i} className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse"
                style={{ animationDelay: `${i * 0.15}s` }} />
        ))}
      </div>
    </div>
  )

  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}
