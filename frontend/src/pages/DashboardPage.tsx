/**
 * DashboardPage — Phase 14 full implementation.
 *
 * Overview dashboard stub. Shows a placeholder until Phase 14.
 */

import AppLayout from '@/components/AppLayout'

export default function DashboardPage() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Overview</h1>
          <p className="text-gray-400 text-sm mt-1">
            Platform health at a glance
          </p>
        </div>

        {/* Phase 14 — metrics cards, charts, active incidents */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {['Total Services', 'Healthy', 'Degraded', 'Active Incidents'].map((label) => (
            <div key={label} className="card">
              <p className="text-xs text-gray-500 uppercase tracking-wider mb-1">{label}</p>
              <p className="text-3xl font-bold text-white">—</p>
              <p className="text-xs text-gray-500 mt-1">Available after Phase 7</p>
            </div>
          ))}
        </div>

        <div className="card">
          <p className="text-gray-400 text-sm">
            📊 Latency and error-rate charts will render here in Phase 14.
          </p>
        </div>
      </div>
    </AppLayout>
  )
}
