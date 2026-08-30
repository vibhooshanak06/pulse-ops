/**
 * Metrics API — Phase 7
 */
import apiClient from './client'
import type { OverviewMetrics, ServiceMetrics } from '@/types'

export const metricsApi = {
  getOverview: (projectId: string) =>
    apiClient.get<OverviewMetrics>(`/metrics/overview`, { params: { project_id: projectId } }),

  getServiceMetrics: (serviceId: string, windowMinutes = 60) =>
    apiClient.get<ServiceMetrics>(`/metrics/services/${serviceId}`, {
      params: { window_minutes: windowMinutes },
    }),
}
