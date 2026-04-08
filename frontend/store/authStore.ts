import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { TokenStore, login as apiLogin, getMe } from '@/lib/api'

interface User { email: string; full_name: string; role: string }

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      loading: false,

      login: async (email, password) => {
        set({ loading: true })
        try {
          const { access_token, refresh_token } = await apiLogin(email, password)
          TokenStore.set(access_token, refresh_token)
          const user = await getMe()
          set({ user, loading: false })
        } catch (e) {
          set({ loading: false })
          throw e
        }
      },

      logout: () => {
        TokenStore.clear()
        set({ user: null })
        window.location.href = '/login'
      },

      hydrate: async () => {
        const token = TokenStore.get()
        if (!token) return
        try {
          const user = await getMe()
          set({ user })
        } catch {
          TokenStore.clear()
        }
      },
    }),
    { name: 'auth', partialize: (s) => ({ user: s.user }) }
  )
)
