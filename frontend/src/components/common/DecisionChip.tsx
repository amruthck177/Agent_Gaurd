import React from 'react'
import { CheckCircle2, Clock, ShieldX } from 'lucide-react'

export type DecisionType = 'ALLOW' | 'ASK HUMAN' | 'BLOCK' | 'ASK_HUMAN'

interface DecisionChipProps {
  decision: DecisionType
  size?: 'sm' | 'md'
  className?: string
}

export const DecisionChip: React.FC<DecisionChipProps> = ({
  decision,
  size = 'md',
  className = '',
}) => {
  const configs = {
    ALLOW: {
      label: 'ALLOW',
      colorClasses: 'bg-allow/15 text-allow border-allow/40',
      icon: CheckCircle2,
    },
    'ASK HUMAN': {
      label: 'ASK HUMAN',
      colorClasses: 'bg-ask/15 text-ask border-ask/40',
      icon: Clock,
    },
    ASK_HUMAN: {
      label: 'ASK HUMAN',
      colorClasses: 'bg-ask/15 text-ask border-ask/40',
      icon: Clock,
    },
    BLOCK: {
      label: 'BLOCK',
      colorClasses: 'bg-block/15 text-block border-block/40',
      icon: ShieldX,
    },
  }

  const config = configs[decision] || configs.BLOCK
  const IconComponent = config.icon

  const sizeClasses = size === 'sm'
    ? 'h-6 px-2 text-[11px] gap-1'
    : 'h-7 px-2.5 text-[12px] gap-1.5'

  return (
    <span
      className={`inline-flex items-center font-semibold rounded-pill border select-none tracking-wide ${sizeClasses} ${config.colorClasses} ${className}`}
      aria-label={`Decision: ${config.label}`}
    >
      <IconComponent className={size === 'sm' ? 'w-3.5 h-3.5 stroke-[2]' : 'w-4 h-4 stroke-[2]'} />
      <span>{config.label}</span>
    </span>
  )
}
