/**
 * Incidents API — Phase 11
 */
import apiClient from './client'
import type { Incident, IncidentDetail, PaginatedResponse } from '@/types'

export const incidentsApi = {
  list: (projectId: string, status?: string) =>
    apiClient.get<PaginatedResponse<Incident>>('/incidents', {
      params: { project_id: projectId, status },
    }),

  getById: (incidentId: string) =>
    apiClient.get<IncidentDetail>(`/incidents/${incidentId}`),

  updateStatus: (incidentId: string, status: string) =>
    apiClient.patch(`/incidents/${incidentId}/status`, { status }),

  triggerAiExplanation: (incidentId: string) =>
    apiClient.post(`/incidents/${incidentId}/explain`),
}
