/**
 * StatusBadge — renders colored badges for health status and incident status.
 */

import { healthToClass, incidentStatusToClass } from '@/utils/format'

interface HealthProps {
  type: 'health'
  status: string
}

interface IncidentProps {
  type: 'incident'
  status: string
}

type Props = HealthProps | IncidentProps

export default function StatusBadge(props: Props) {
  const cssClass =
    props.type === 'health'
      ? healthToClass(props.status)
      : incidentStatusToClass(props.status)

  return <span className={cssClass}>{props.status}</span>
}
