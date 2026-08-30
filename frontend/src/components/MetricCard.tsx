/**
 * MetricCard — single metric display tile used on the overview and service
 * detail pages.
 *
 * Shows a label, value, optional trend indicator, and optional sublabel.
 */

import clsx from 'clsx'

interface Props {
  label: string
  value: string | number
  sublabel?: string
  trend?: 'up' | 'down' | 'neutral'
  trendLabel?: string
  /** When true the trend direction is bad (e.g. latency going up = bad) */
  invertTrend?: boolean
  loading?: boolean
}

export default function MetricCard({
  label,
  value,
  sublabel,
  trend,
  trendLabel,
  invertTrend = false,
  loading = false,
}: Props) {
  const trendColor = (() => {
    if (!trend || trend === 'neutral') return 'text-gray-500'
    const isGood = invertTrend ? trend === 'down' : trend === 'up'
    return isGood ? 'text-green-400' : 'text-red-400'
  })()

  const trendIcon = (() => {
    if (!trend || trend === 'neutral') return null
    return trend === 'up' ? '↑' : '↓'
  })()

  return (
    <div className="card">
      <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">{label}</p>

      {loading ? (
        <div className="h-8 bg-surface-700 rounded animate-pulse w-24" />
      ) : (
        <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
      )}

      {(trendLabel || sublabel) && (
        <div className="mt-1.5 flex items-center gap-1.5">
          {trendLabel && (
            <span className={clsx('text-xs font-medium', trendColor)}>
              {trendIcon} {trendLabel}
            </span>
          )}
          {sublabel && !trendLabel && (
            <span className="text-xs text-gray-600">{sublabel}</span>
          )}
        </div>
      )}
    </div>
  )
}
