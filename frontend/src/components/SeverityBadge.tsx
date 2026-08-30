/**
 * SeverityBadge — renders a colored badge for anomaly/incident severity.
 * Used on incident lists, anomaly tables, and the investigation page.
 */

import { severityToClass } from '@/utils/format'

interface Props {
  severity: string
}

export default function SeverityBadge({ severity }: Props) {
  return (
    <span className={severityToClass(severity)}>
      {severity}
    </span>
  )
}
