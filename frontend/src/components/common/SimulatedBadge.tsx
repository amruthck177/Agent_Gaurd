import React from 'react'
import { Cpu } from 'lucide-react'

interface SimulatedBadgeProps {
  label?: string
  variant?: 'footer' | 'pill'
  className?: string
}

export const SimulatedBadge: React.FC<SimulatedBadgeProps> = ({
  label = 'Simulated MVP · mock tools',
  variant = 'pill',
  className = '',
}) => {
  if (variant === 'footer') {
    return (
      <div
        className={`p-2.5 rounded-lg bg-surface2/60 border border-line flex items-center justify-between text-[11px] font-mono text-ink2 ${className}`}
      >
        <span>{label}</span>
        <Cpu className="w-3.5 h-3.5 text-accent" />
      </div>
    )
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-pill bg-surface2 border border-line text-[11px] font-mono text-ink2 ${className}`}
    >
      <Cpu className="w-3 h-3 text-accent" />
      <span>{label}</span>
    </span>
  )
}
