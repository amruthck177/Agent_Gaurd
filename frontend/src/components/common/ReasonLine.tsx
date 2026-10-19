import React from 'react'
import {
  AlertTriangle,
  Ban,
  Clock,
  Database,
  Repeat,
  ShieldAlert,
  WifiOff,
  UserCheck,
} from 'lucide-react'

export type CanonicalReason =
  | 'Recipient changed after approval'
  | 'Amount changed after approval'
  | 'Approval expired'
  | 'Approval revoked'
  | 'Approval already used (replay)'
  | 'Agent lacks write permission'
  | 'Destructive database operation prohibited'
  | 'Payment exceeds ₹10,000 limit: human approval required'
  | 'Gateway unavailable: failed closed'

interface ReasonLineProps {
  reason: CanonicalReason | string
  ruleId?: string
  decidedBy?: string
  className?: string
}

export const ReasonLine: React.FC<ReasonLineProps> = ({
  reason,
  ruleId,
  decidedBy,
  className = '',
}) => {
  const getIcon = () => {
    switch (reason) {
      case 'Recipient changed after approval':
      case 'Amount changed after approval':
        return <AlertTriangle className="w-4 h-4 text-block shrink-0 mt-0.5" />
      case 'Approval expired':
        return <Clock className="w-4 h-4 text-ask shrink-0 mt-0.5" />
      case 'Approval revoked':
        return <Ban className="w-4 h-4 text-block shrink-0 mt-0.5" />
      case 'Approval already used (replay)':
        return <Repeat className="w-4 h-4 text-block shrink-0 mt-0.5" />
      case 'Agent lacks write permission':
        return <ShieldAlert className="w-4 h-4 text-block shrink-0 mt-0.5" />
      case 'Destructive database operation prohibited':
        return <Database className="w-4 h-4 text-block shrink-0 mt-0.5" />
      case 'Payment exceeds ₹10,000 limit: human approval required':
        return <UserCheck className="w-4 h-4 text-ask shrink-0 mt-0.5" />
      case 'Gateway unavailable: failed closed':
        return <WifiOff className="w-4 h-4 text-block shrink-0 mt-0.5" />
      default:
        return <ShieldAlert className="w-4 h-4 text-ink2 shrink-0 mt-0.5" />
    }
  }

  const getTextColor = () => {
    if (reason.includes('₹10,000') || reason.includes('expired')) {
      return 'text-ask'
    }
    return 'text-block'
  }

  return (
    <div className={`space-y-1.5 ${className}`}>
      <div className={`flex items-start gap-2 font-semibold text-[14px] ${getTextColor()}`}>
        {getIcon()}
        <span>{reason}</span>
      </div>

      {(ruleId || decidedBy) && (
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {ruleId && (
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface2 border border-line text-ink">
              Rule: <strong className="text-accent">{ruleId}</strong>
            </span>
          )}
          {decidedBy && (
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface2 border border-line text-ink2">
              Decided by: <strong className="text-ink">{decidedBy}</strong>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
