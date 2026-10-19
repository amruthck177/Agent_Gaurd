import React from 'react'
import { CheckCircle2, XCircle, Ban, ShieldCheck, Lock } from 'lucide-react'
import { Countdown } from './Countdown'
import { DecisionChip } from './DecisionChip'

export type ApprovalState = 'pending' | 'approved' | 'rejected' | 'expired' | 'revoked'

export interface ApprovalCardData {
  id: string
  title: string
  amount: number
  recipient: string
  tool: string
  state: ApprovalState
  tags?: string[]
  createdAt?: string
  expiresInSeconds?: number
  agentId?: string
  used?: boolean
}

interface ApprovalCardProps {
  data: ApprovalCardData
  onApprove?: (id: string) => void
  onReject?: (id: string) => void
  onRevoke?: (id: string) => void
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  data,
  onApprove,
  onReject,
  onRevoke,
}) => {
  const isPending = data.state === 'pending'
  const isApproved = data.state === 'approved'

  return (
    <div className="rounded-card border border-line bg-surface overflow-hidden shadow-xl transition-all">
      {/* Top Gradient Edge for Pending */}
      {isPending && <div className="h-1 bg-gradient-to-r from-ask via-accent to-ask" />}

      <div className="p-5 sm:p-6 space-y-5">
        {/* Header: Chip + ID + Countdown */}
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line/60">
          <div className="flex items-center gap-2.5">
            {isPending ? (
              <DecisionChip decision="ASK HUMAN" size="sm" />
            ) : isApproved ? (
              <DecisionChip decision="ALLOW" size="sm" />
            ) : (
              <DecisionChip decision="BLOCK" size="sm" />
            )}
            <span className="font-mono text-[12px] text-ink2">{data.id}</span>
          </div>

          {isPending && (
            <Countdown initialSeconds={data.expiresInSeconds || 540} />
          )}

          {isApproved && (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill bg-allow/15 text-allow border border-allow/30 text-[11px] font-mono font-semibold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>{data.used ? 'Token Used' : 'Unused Single-Use'}</span>
            </span>
          )}
        </div>

        {/* Title and Amount */}
        <div>
          <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
            <h3 className="text-[17px] sm:text-[18px] font-semibold text-ink tracking-tight">
              {data.title}
            </h3>
            <span className="text-[22px] sm:text-[24px] font-mono font-bold text-accent tabular-nums">
              ₹{data.amount.toLocaleString('en-IN')}
            </span>
          </div>

          {/* Trigger Chips */}
          {data.tags && data.tags.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mt-3">
              {data.tags.map((tag, idx) => (
                <span
                  key={idx}
                  className="px-2.5 py-0.5 rounded text-[11px] font-medium bg-ask/10 border border-ask/30 text-ask"
                >
                  {tag}
                </span>
              ))}
              {data.agentId && (
                <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface2 border border-line text-ink2">
                  Agent: {data.agentId}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Enclave Bound Parameters Grid */}
        <div className="rounded-lg bg-surface2/60 border border-line p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-line/60 text-[11px] font-mono uppercase tracking-wider text-ink2">
            <span>Enclave Bound Parameters</span>
            <span className="text-accent flex items-center gap-1">
              <Lock className="w-3 h-3" />
              <span>HMAC-SHA256 Bound</span>
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[13px] font-mono">
            <div>
              <span className="block text-[11px] text-ink2">Tool Target</span>
              <span className="text-ink font-semibold">{data.tool}</span>
            </div>
            <div>
              <span className="block text-[11px] text-ink2">Recipient Account</span>
              <span className="text-ink font-semibold">{data.recipient}</span>
            </div>
            <div>
              <span className="block text-[11px] text-ink2">Calculated Amount</span>
              <span className="text-accent font-bold">₹{data.amount.toLocaleString('en-IN')}.00 INR</span>
            </div>
            <div>
              <span className="block text-[11px] text-ink2">Single-Use Token</span>
              <span className="text-ink2">Cryptographically locked</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        {isPending && (
          <div className="pt-2 flex flex-col sm:flex-row items-center gap-3">
            <button
              onClick={() => onApprove?.(data.id)}
              className="w-full sm:w-auto flex-1 h-11 px-6 rounded-lg bg-accent text-bg hover:bg-accent/90 font-semibold text-[14px] flex items-center justify-center gap-2 transition-all active:scale-95 shadow-md shadow-accent/10 focus-accent"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Approve (₹{data.amount.toLocaleString('en-IN')})</span>
            </button>
            <button
              onClick={() => onReject?.(data.id)}
              className="w-full sm:w-auto h-11 px-5 rounded-lg border border-block/60 text-block hover:bg-block/10 font-semibold text-[14px] flex items-center justify-center gap-2 transition-all active:scale-95"
            >
              <XCircle className="w-4 h-4" />
              <span>Reject</span>
            </button>
          </div>
        )}

        {isApproved && !data.used && (
          <div className="pt-2">
            <button
              onClick={() => onRevoke?.(data.id)}
              className="h-10 px-4 rounded-lg border border-block/50 text-block hover:bg-block/10 font-semibold text-[13px] flex items-center gap-2 transition-all active:scale-95"
            >
              <Ban className="w-4 h-4" />
              <span>Revoke Approval Token</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
