import React from 'react'
import { Check, XCircle, ShieldAlert, CheckCircle2, Lock } from 'lucide-react'

export interface ParamRow {
  label: string
  approvedValue: string
  attemptedValue: string
  isMismatch: boolean
  approvedExtra?: string
  attemptedExtra?: string
}

interface ParamCompareProps {
  approvalId?: string
  toolName?: string
  rows: ParamRow[]
  executionCount?: number
  isStacked?: boolean // For mobile or styleguide forced device view
  subtext?: string
}

export const ParamCompare: React.FC<ParamCompareProps> = ({
  approvalId = 'APR-0002',
  rows,
  executionCount = 0,
  isStacked = false,
  subtext = 'Zero loss guaranteed. Gateway blocked call prior to external API dispatch.',
}) => {
  const hasMismatch = rows.some((r) => r.isMismatch)

  return (
    <div className="rounded-card border border-line bg-surface overflow-hidden shadow-lg">
      {/* Header */}
      <div
        className={`bg-surface2/80 border-b border-line p-3 font-mono text-[12px] ${
          isStacked
            ? 'flex flex-col gap-2'
            : 'grid grid-cols-1 sm:grid-cols-2'
        }`}
      >
        <div className="flex items-center gap-1.5 font-semibold text-ink2">
          <CheckCircle2 className="w-4 h-4 text-accent" />
          <span>APPROVED ({approvalId})</span>
        </div>
        <div
          className={`flex items-center gap-1.5 font-semibold ${
            hasMismatch ? 'text-block' : 'text-allow'
          } ${isStacked ? '' : 'sm:pl-3 sm:border-l sm:border-line'}`}
        >
          {hasMismatch ? (
            <ShieldAlert className="w-4 h-4 text-block" />
          ) : (
            <CheckCircle2 className="w-4 h-4 text-allow" />
          )}
          <span>ATTEMPTED (live intercept)</span>
        </div>
      </div>

      {/* Comparison Rows */}
      <div className="divide-y divide-line/60">
        {rows.map((row, idx) => {
          if (row.isMismatch) {
            return (
              <div
                key={idx}
                className={`p-3 bg-block/15 border-l-4 border-l-block transition-colors ${
                  isStacked
                    ? 'flex flex-col gap-2'
                    : 'grid grid-cols-1 sm:grid-cols-2'
                }`}
              >
                {/* Approved Side */}
                <div className="flex items-center justify-between sm:pr-3 text-[13px] font-mono">
                  <span className="text-ink font-medium">
                    <span className="text-ink2 text-[11px] uppercase mr-2">{row.label}:</span>
                    {row.approvedValue}
                  </span>
                  <Check className="w-4 h-4 text-accent shrink-0" />
                </div>

                {/* Attempted Side (Mismatch highlight) */}
                <div
                  className={`flex items-center justify-between text-[13px] font-mono ${
                    isStacked ? 'pt-1 border-t border-block/20' : 'sm:pl-3 sm:border-l sm:border-block/40'
                  }`}
                >
                  <span className="text-block font-bold flex items-center gap-1.5">
                    <XCircle className="w-4 h-4 text-block shrink-0" />
                    <span>{row.attemptedValue}</span>
                  </span>
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-block text-bg">
                    MISMATCH
                  </span>
                </div>
              </div>
            )
          }

          // Matching Row
          return (
            <div
              key={idx}
              className={`p-3 hover:bg-surface2/30 transition-colors ${
                isStacked
                  ? 'flex flex-col gap-1.5'
                  : 'grid grid-cols-1 sm:grid-cols-2'
              }`}
            >
              <div className="flex items-center justify-between sm:pr-3 text-[13px] font-mono">
                <span className="text-ink">
                  <span className="text-ink2 text-[11px] uppercase mr-2">{row.label}:</span>
                  {row.approvedValue}
                </span>
                <Check className="w-4 h-4 text-accent/80 shrink-0" />
              </div>
              <div
                className={`flex items-center justify-between text-[13px] font-mono ${
                  isStacked ? '' : 'sm:pl-3 sm:border-l sm:border-line'
                }`}
              >
                <span className="text-ink font-medium">{row.attemptedValue}</span>
                <Check className="w-4 h-4 text-allow shrink-0" />
              </div>
            </div>
          )
        })}
      </div>

      {/* Cryptographic Sub-guarantee Notice */}
      <div className="p-2.5 bg-surface2/40 border-t border-line font-mono text-[11px] text-ink2 flex items-center gap-2">
        <Lock className="w-3.5 h-3.5 text-accent" />
        <span>Cryptographic binding check evaluated strictly at gateway boundary.</span>
      </div>

      {/* Hero Proof Footer: Payment tool executions: N */}
      <div className="p-4 bg-surface2/90 border-t border-line flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[18px] sm:text-[20px] font-bold tracking-tight">
              Payment tool executions:{' '}
              <span
                className={`text-[22px] sm:text-[24px] font-mono ${
                  executionCount === 0 ? 'text-allow' : 'text-block'
                }`}
              >
                {executionCount}
              </span>
            </span>
          </div>
          <p className="text-[12px] text-ink2 mt-0.5">{subtext}</p>
        </div>

        <div className="px-3 py-1 rounded-pill bg-allow/10 border border-allow/30 text-allow text-[12px] font-semibold flex items-center gap-1.5 self-start sm:self-auto">
          <CheckCircle2 className="w-4 h-4" />
          <span>Tool never executed</span>
        </div>
      </div>
    </div>
  )
}
