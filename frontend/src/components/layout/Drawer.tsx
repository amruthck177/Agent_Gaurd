import React, { useEffect } from 'react'
import { X, Copy, PauseCircle, CheckCircle2 } from 'lucide-react'
import { DecisionChip, DecisionType } from '../common/DecisionChip'
import { ParamCompare, ParamRow } from '../common/ParamCompare'
import { ReasonLine, CanonicalReason } from '../common/ReasonLine'

export interface DrawerEventData {
  id: string | number
  decision: DecisionType
  tool: string
  amount: number
  agent: string
  time: string
  incidentId: string
  interceptId: string
  reason: CanonicalReason | string
  ruleId: string
  decidedBy: string
  explanation: string
  comparisonRows: ParamRow[]
  executionCount: number
  lossPrevented: number
  rawRequestJson: string
  recordNumber: number
  currentHash: string
  prevHash: string
}

interface DrawerProps {
  isOpen: boolean
  onClose: () => void
  data: DrawerEventData | null
  onPauseAgent?: () => void
  isMobileSheet?: boolean // Forced mode for mobile switcher
}

export const Drawer: React.FC<DrawerProps> = ({
  isOpen,
  onClose,
  data,
  onPauseAgent,
  isMobileSheet = false,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen || !data) return null

  const isBlock = data.decision === 'BLOCK'

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        aria-hidden="true"
      />

      {/* Drawer Container (Right side on desktop, bottom sheet on mobile) */}
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Intercept Deep Inspection Drawer"
        className={`relative z-10 bg-surface border-line shadow-2xl flex flex-col h-full transition-transform duration-300 ease-in-out ${
          isMobileSheet
            ? 'w-full max-h-[92vh] mt-auto rounded-t-2xl border-t'
            : 'w-full sm:max-w-[480px] lg:max-w-[500px] border-l'
        }`}
      >
        {/* Mobile Drag Handle */}
        <div className="flex justify-center pt-2 sm:hidden">
          <div className="w-12 h-1.5 rounded-full bg-line" />
        </div>

        {/* HEADER */}
        <div className="p-4 sm:p-5 border-b border-line bg-surface2/60 shrink-0 space-y-2">
          <div className="flex items-center justify-between">
            <DecisionChip decision={data.decision} size="md" />
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-surface text-ink2 hover:text-ink transition-colors"
              title="Close drawer"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="pt-1">
            <h2 className="text-[18px] sm:text-[20px] font-bold text-ink tracking-tight flex items-baseline gap-2">
              <span>{data.tool}</span>
              <span className="font-mono text-accent">₹{data.amount.toLocaleString('en-IN')}</span>
            </h2>
            <div className="flex items-center gap-2 mt-1 text-ink2 font-mono text-[12px]">
              <span className="text-ink">{data.agent}</span>
              <span>·</span>
              <span>{data.time}</span>
              <span>·</span>
              <span className="text-accent">#{data.incidentId}</span>
            </div>
          </div>
        </div>

        {/* BODY (Sections 1 to 5) */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-6">
          {/* Section 1: Why */}
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-wider text-ink2 font-semibold">
                1. Why Decision Occurred
              </span>
              {isBlock && (
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-block/15 text-block border border-block/30">
                  Enclave Block
                </span>
              )}
            </div>

            <div className="bg-surface2/70 p-3.5 rounded-lg border border-line space-y-2">
              <ReasonLine
                reason={data.reason}
                ruleId={data.ruleId}
                decidedBy={data.decidedBy}
              />
              <p className="text-[12px] text-ink2 pt-2 border-t border-line/60 leading-relaxed">
                {data.explanation}
              </p>
            </div>
          </section>

          {/* Section 2: Parameter Comparison Block */}
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-wider text-ink2 font-semibold">
                2. Approved vs Attempted Parameter Audit
              </span>
              <span className="font-mono text-[10px] text-accent">Enclave Differential</span>
            </div>

            <ParamCompare
              approvalId="APR-0002"
              rows={data.comparisonRows}
              executionCount={data.executionCount}
              isStacked={isMobileSheet}
            />
          </section>

          {/* Section 3: Execution Outcome */}
          <section className="space-y-2">
            <span className="font-mono text-[11px] uppercase tracking-wider text-ink2 font-semibold">
              3. Execution Outcome Proof
            </span>
            <div className="bg-surface2/60 p-4 rounded-lg border border-line space-y-2.5">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-allow" />
                <h3 className="text-[16px] font-bold text-ink">
                  Tool executed: {data.executionCount > 0 ? 'Yes' : 'No'}
                </h3>
              </div>
              <div className="font-mono text-[12px] text-ink2 bg-surface p-2.5 rounded border border-line">
                <span>Funds transferred: </span>
                <strong className="text-ink">₹0.00</strong> · <span>Loss prevented: </span>
                <strong className="text-accent font-bold">
                  ₹{data.lossPrevented.toLocaleString('en-IN')}
                </strong>
              </div>
            </div>
          </section>

          {/* Section 4: Agent Request (Raw JSON with masked secrets) */}
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-wider text-ink2 font-semibold">
                4. Intercepted Agent Request
              </span>
              <button
                onClick={() => navigator.clipboard.writeText(data.rawRequestJson)}
                className="flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono bg-surface2 border border-line rounded text-ink2 hover:text-ink transition-colors"
              >
                <Copy className="w-3 h-3" />
                <span>Copy JSON</span>
              </button>
            </div>
            <div className="bg-bg rounded-lg border border-line p-3 font-mono text-[12px] text-ink2 overflow-x-auto">
              <pre className="text-ink2">
                <code>{data.rawRequestJson}</code>
              </pre>
            </div>
          </section>

          {/* Section 5: Cryptographic Audit Record */}
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] uppercase tracking-wider text-ink2 font-semibold">
                5. Cryptographic Audit Record
              </span>
              <span className="font-mono text-[10px] text-accent">Immutable Proof</span>
            </div>

            <div className="bg-surface2/60 p-3.5 rounded-lg border border-line space-y-2 font-mono text-[12px]">
              <div className="flex items-center justify-between">
                <span className="text-ink2">Sequence:</span>
                <span className="text-accent font-bold">#{data.recordNumber}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink2">Current hash:</span>
                <span className="text-ink font-semibold">{data.currentHash}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-ink2">Previous hash:</span>
                <span className="text-ink2">{data.prevHash}</span>
              </div>
              <div className="pt-2 border-t border-line text-[11px] text-allow flex items-center gap-1 font-sans">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>SHA-256 Hash Chain Verified</span>
              </div>
            </div>
          </section>
        </div>

        {/* FOOTER */}
        <div className="p-4 border-t border-line bg-surface2/60 shrink-0 flex items-center justify-between gap-3">
          <button
            onClick={onPauseAgent}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-block/50 bg-block/10 hover:bg-block/20 text-block text-[13px] font-semibold transition-all active:scale-95"
          >
            <PauseCircle className="w-4 h-4" />
            <span>Pause Agent</span>
          </button>

          <button
            onClick={onClose}
            className="px-5 py-2 rounded-lg bg-surface2 border border-line hover:border-ink2 text-ink text-[13px] font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </aside>
    </div>
  )
}
