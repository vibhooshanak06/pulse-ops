/**
 * LoadingSpinner — inline loading indicator.
 * Used by React Query loading states throughout the dashboard.
 */

interface Props {
  size?: 'sm' | 'md' | 'lg'
  label?: string
}

const sizeMap = {
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-10 h-10',
}

export default function LoadingSpinner({ size = 'md', label }: Props) {
  return (
    <div className="flex items-center justify-center gap-2" role="status" aria-label={label ?? 'Loading'}>
      <svg
        className={`${sizeMap[size]} animate-spin text-brand-500`}
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
        />
      </svg>
      {label && <span className="text-sm text-gray-400">{label}</span>}
    </div>
  )
}
