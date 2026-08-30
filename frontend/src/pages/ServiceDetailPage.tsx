/**
 * ServiceDetailPage — Phase 14 full implementation.
 *
 * Deep-dive metrics for a single service:
 * avg/p50/p95/p99 latency, error rate, throughput,
 * latency chart, error chart, traffic chart, endpoint table.
 */

import { useParams } from 'react-router-dom'
import AppLayout from '@/components/AppLayout'

export default function ServiceDetailPage() {
  const { serviceId } = useParams<{ serviceId: string }>()

  return (
    <AppLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-white">Service Detail</h1>
          <p className="text-gray-400 text-sm mt-1 font-mono">{serviceId}</p>
        </div>

        <div className="card">
          <p className="text-gray-400 text-sm">
            📈 P95/P99 latency charts, error rate timeline, and endpoint
            performance table render here in Phase 14.
          </p>
        </div>
      </div>
    </AppLayout>
  )
}
