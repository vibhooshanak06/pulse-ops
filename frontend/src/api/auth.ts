/**
 * Auth API — Phase 3
 */
import apiClient from './client'
import type { AuthTokens, User } from '@/types'

export const authApi = {
  register: (data: { email: string; password: string; full_name: string; org_name: string }) =>
    apiClient.post<User>('/auth/register', data),

  login: (email: string, password: string) =>
    apiClient.post<AuthTokens>('/auth/login', { email, password }),

  me: () =>
    apiClient.get<User>('/auth/me'),
}
