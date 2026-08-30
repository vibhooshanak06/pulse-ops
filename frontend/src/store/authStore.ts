/**
 * Auth store — lightweight token management.
 *
 * We use a simple module-level store rather than Redux or Zustand
 * because our auth state is straightforward: token in, token out.
 * React Query handles all server state; this store handles only
 * the local "is the user authenticated?" question.
 *
 * A React context wrapper is added in Phase 3 for component access.
 */

const TOKEN_KEY = 'access_token'
const PROJECT_KEY = 'active_project_id'

export const authStore = {
  getToken: (): string | null => localStorage.getItem(TOKEN_KEY),

  setToken: (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token)
  },

  clearToken: (): void => {
    localStorage.removeItem(TOKEN_KEY)
  },

  isAuthenticated: (): boolean => {
    return Boolean(localStorage.getItem(TOKEN_KEY))
  },

  getActiveProjectId: (): string | null => localStorage.getItem(PROJECT_KEY),

  setActiveProjectId: (projectId: string): void => {
    localStorage.setItem(PROJECT_KEY, projectId)
  },
}
