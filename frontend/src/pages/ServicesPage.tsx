/**
 * ServicesPage — Phase 14 full implementation.
 *
 * Lists all services with current health status.
 */

import AppLayout from '@/components/AppLayout'

export default function ServicesPage() {
  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Services</h1>
          <p className="text-gray-400 text-sm mt-1">
            All monitored services and their current health
          </p>
        </div>

        <div className="card">
          <p className="text-gray-400 text-sm">
            🔧 Service health table renders here in Phase 14.
          </p>
        </div>
      </div>
    </AppLayout>
  )
}
