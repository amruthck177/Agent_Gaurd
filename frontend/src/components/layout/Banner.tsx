import React, { useState } from 'react'
import { X, ShieldCheck } from 'lucide-react'

interface BannerProps {
  message?: string
  badgeText?: string
}

export const Banner: React.FC<BannerProps> = ({
  message = 'Enforcement runs in code at the gateway, outside the AI. Errors fail closed.',
  badgeText = 'ISO/IEC 42001 Guard',
}) => {
  const [isDismissed, setIsDismissed] = useState(false)

  if (isDismissed) return null

  return (
    <div
      role="region"
      aria-label="Security Architecture Banner"
      className="bg-surface2/95 border-b border-line px-4 sm:px-8 py-2 flex items-center justify-between text-xs transition-all relative z-20"
    >
      <div className="flex items-center gap-2.5 truncate pr-2">
        <span className="hidden sm:inline-flex px-2 py-0.5 rounded-pill text-[10px] font-mono font-bold uppercase tracking-wider bg-accent/15 text-accent border border-accent/30 shrink-0">
          {badgeText}
        </span>
        <ShieldCheck className="w-4 h-4 text-accent shrink-0 sm:hidden" />
        <span className="text-ink text-[12px] truncate">{message}</span>
      </div>

      <button
        onClick={() => setIsDismissed(true)}
        className="text-ink2 hover:text-ink p-1 rounded hover:bg-surface transition-colors shrink-0"
        title="Dismiss banner"
        aria-label="Dismiss banner"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
