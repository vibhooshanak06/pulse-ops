/**
 * Services API — Phase 3+
 */
import apiClient from './client'
import type { Service, PaginatedResponse } from '@/types'

export const servicesApi = {
  list: (projectId: string) =>
    apiClient.get<PaginatedResponse<Service>>('/services', {
      params: { project_id: projectId },
    }),

  getById: (serviceId: string) =>
    apiClient.get<Service>(`/services/${serviceId}`),
}
