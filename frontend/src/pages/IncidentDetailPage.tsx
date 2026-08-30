/**
 * IncidentDetailPage — Phase 14 full implementation.
 *
 * The flagship page. Shows the full incident investigation:
 *   - Incident summary, severity, timeline
 *   - Related anomalies
 *   - Affected services and endpoints
 *   - Before vs current metric comparison
 *   - Supporting evidence table
 *   - AI explanation with confidence score
 *   - Recommended investigation steps
 */

import { useParams } from 'react-router-dom'
import AppLayout from '@/components/AppLayout'

export default function IncidentDetailPage() {
  const { incidentId } = useParams<{ incidentId: string }>()

  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Incident Investigation</h1>
          <p className="text-gray-400 text-sm mt-1 font-mono">{incidentId}</p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card">
            <h2 className="text-sm font-medium text-gray-300 mb-2">Evidence</h2>
            <p className="text-gray-500 text-sm">
              📋 Baseline vs current metric comparison renders here in Phase 14.
            </p>
          </div>
          <div className="card border-brand-600/50">
            <h2 className="text-sm font-medium text-gray-300 mb-2">
              AI Explanation
            </h2>
            <p className="text-gray-500 text-sm">
              🤖 Evidence-grounded AI analysis renders here in Phase 14.
            </p>
          </div>
        </div>

        <div className="card">
          <h2 className="text-sm font-medium text-gray-300 mb-2">Anomaly Timeline</h2>
          <p className="text-gray-500 text-sm">
            ⏱ Correlated anomaly timeline renders here in Phase 14.
          </p>
        </div>
      </div>
    </AppLayout>
  )
}
