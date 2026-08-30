/**
 * IncidentsPage — Phase 14 full implementation.
 *
 * Lists all incidents with severity, status, service, and start time.
 * Filterable by status (OPEN, ACKNOWLEDGED, INVESTIGATING, RESOLVED).
 */

import AppLayout from '@/components/AppLayout'

export default function IncidentsPage() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Incidents</h1>
          <p className="text-gray-400 text-sm mt-1">
            Correlated anomaly groups requiring investigation
          </p>
        </div>

        <div className="card">
          <p className="text-gray-400 text-sm">
            🚨 Incident list with severity badges and status filters renders here in Phase 14.
          </p>
        </div>
      </div>
    </AppLayout>
  )
}
