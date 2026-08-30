// ─── Auth ─────────────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  full_name: string
  created_at: string
}

export interface Organization {
  id: string
  name: string
  slug: string
  created_at: string
}

export interface Project {
  id: string
  organization_id: string
  name: string
  slug: string
  created_at: string
}

export interface AuthTokens {
  access_token: string
  token_type: string
}

// ─── Services ─────────────────────────────────────────────────────────────────

export type HealthStatus = 'healthy' | 'degraded' | 'critical' | 'unknown'

export interface Service {
  id: string
  project_id: string
  name: string
  description?: string
  health_status: HealthStatus
  created_at: string
}

export interface Endpoint {
  id: string
  service_id: string
  path: string
  method: string
  created_at: string
}

// ─── Metrics ──────────────────────────────────────────────────────────────────

export interface MetricAggregate {
  id: string
  service_id: string
  endpoint_id?: string
  window_start: string
  window_end: string
  request_count: number
  avg_latency_ms: number
  p50_latency_ms: number
  p95_latency_ms: number
  p99_latency_ms: number
  error_count: number
  error_rate: number
  throughput_rpm: number
}

export interface ServiceMetrics {
  service: Service
  current: {
    avg_latency_ms: number
    p50_latency_ms: number
    p95_latency_ms: number
    p99_latency_ms: number
    error_rate: number
    request_count: number
    throughput_rpm: number
  }
  time_series: MetricAggregate[]
}

export interface OverviewMetrics {
  total_services: number
  healthy_services: number
  degraded_services: number
  critical_services: number
  active_incidents: number
  total_requests_last_hour: number
  avg_error_rate: number
}

// ─── Anomalies ────────────────────────────────────────────────────────────────

export type AnomalySeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type AnomalyMetricType = 'latency' | 'error_rate' | 'throughput' | 'request_count'

export interface Anomaly {
  id: string
  service_id: string
  endpoint_id?: string
  metric_type: AnomalyMetricType
  severity: AnomalySeverity
  anomaly_score: number
  baseline_value: number
  current_value: number
  deviation_percent: number
  detected_at: string
  resolved_at?: string
  incident_id?: string
}

// ─── Incidents ────────────────────────────────────────────────────────────────

export type IncidentStatus = 'OPEN' | 'ACKNOWLEDGED' | 'INVESTIGATING' | 'RESOLVED'
export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export interface Incident {
  id: string
  title: string
  service_id: string
  service_name: string
  severity: IncidentSeverity
  status: IncidentStatus
  started_at: string
  acknowledged_at?: string
  resolved_at?: string
  anomaly_count: number
  affected_endpoints: string[]
}

export interface IncidentEvidence {
  id: string
  incident_id: string
  baseline_metrics: Record<string, number>
  current_metrics: Record<string, number>
  metric_changes: Record<string, { baseline: number; current: number; change_percent: number }>
  affected_services: string[]
  affected_endpoints: string[]
  anomaly_timeline: Array<{
    timestamp: string
    metric_type: string
    severity: AnomalySeverity
    value: number
    baseline: number
  }>
  collected_at: string
}

export interface AiExplanation {
  id: string
  incident_id: string
  summary: string
  probable_causes: Array<{
    description: string
    confidence: number
    supporting_evidence: string[]
  }>
  confidence: number
  recommended_actions: string[]
  limitations: string
  generated_at: string
  model_used: string
}

export interface IncidentDetail extends Incident {
  anomalies: Anomaly[]
  evidence?: IncidentEvidence
  ai_explanation?: AiExplanation
}

// ─── API Response wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ApiError {
  detail: string
  status_code?: number
}
