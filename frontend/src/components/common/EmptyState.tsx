import React from 'react'
import { ShieldCheck } from 'lucide-react'

interface EmptyStateProps {
  title?: string
  description?: string
  icon?: React.ReactNode
  action?: React.ReactNode
  className?: string
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title = 'Nothing waiting for you',
  description = 'All autonomous agent actions have been processed within verified policies.',
  icon,
  action,
  className = '',
}) => {
  return (
    <div
      className={`rounded-card border border-line/60 bg-surface/80 p-8 sm:p-12 text-center flex flex-col items-center justify-center space-y-3 ${className}`}
    >
      <div className="w-12 h-12 rounded-full bg-allow/15 border border-allow/30 text-allow flex items-center justify-center shadow-inner">
        {icon || <ShieldCheck className="w-6 h-6 text-allow" />}
      </div>
      <h3 className="text-[17px] font-semibold text-ink">{title}</h3>
      <p className="text-[13px] text-ink2 max-w-sm leading-relaxed">{description}</p>
      {action && <div className="pt-2">{action}</div>}
    </div>
  )
}
