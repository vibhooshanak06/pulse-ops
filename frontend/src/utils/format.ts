/**
 * Display formatting utilities.
 *
 * Centralizing formatting keeps the components clean and ensures
 * consistent number/date display across the dashboard.
 */

/**
 * Format a latency value with appropriate unit.
 * Under 1000ms → show as ms, over 1000ms → show as seconds.
 */
export function formatLatency(ms: number): string {
  if (ms >= 1000) {
    return `${(ms / 1000).toFixed(2)}s`
  }
  return `${Math.round(ms)}ms`
}

/**
 * Format an error rate as a percentage string.
 * e.g. 0.154 → "15.4%"
 */
export function formatErrorRate(rate: number): string {
  return `${(rate * 100).toFixed(2)}%`
}

/**
 * Format requests per minute.
 */
export function formatThroughput(rpm: number): string {
  if (rpm >= 1000) {
    return `${(rpm / 1000).toFixed(1)}k rpm`
  }
  return `${Math.round(rpm)} rpm`
}

/**
 * Format a relative time string ("2 minutes ago", "just now").
 */
export function formatRelativeTime(isoString: string): string {
  const now = Date.now()
  const then = new Date(isoString).getTime()
  const diffSeconds = Math.floor((now - then) / 1000)

  if (diffSeconds < 60) return 'just now'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`
  return `${Math.floor(diffSeconds / 86400)}d ago`
}

/**
 * Format a date for display in metric charts.
 */
export function formatChartTime(isoString: string): string {
  const d = new Date(isoString)
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
}

/**
 * Format a percentage change for display.
 * Positive → red (bad for latency/errors), with + prefix.
 */
export function formatChangePercent(percent: number): string {
  const sign = percent >= 0 ? '+' : ''
  return `${sign}${percent.toFixed(1)}%`
}

/**
 * Map a severity string to a Tailwind CSS class.
 */
export function severityToClass(severity: string): string {
  const map: Record<string, string> = {
    CRITICAL: 'badge-critical',
    HIGH: 'badge-high',
    MEDIUM: 'badge-medium',
    LOW: 'badge-low',
  }
  return map[severity.toUpperCase()] ?? 'badge-low'
}

/**
 * Map a health status to a Tailwind CSS class.
 */
export function healthToClass(status: string): string {
  const map: Record<string, string> = {
    healthy: 'badge-healthy',
    degraded: 'badge-degraded',
    critical: 'badge-critical',
    unknown: 'badge-unknown',
  }
  return map[status.toLowerCase()] ?? 'badge-unknown'
}

/**
 * Map an incident status to a Tailwind CSS class.
 */
export function incidentStatusToClass(status: string): string {
  const map: Record<string, string> = {
    OPEN: 'badge-open',
    ACKNOWLEDGED: 'badge-acknowledged',
    INVESTIGATING: 'badge-investigating',
    RESOLVED: 'badge-resolved',
  }
  return map[status.toUpperCase()] ?? 'badge-open'
}
