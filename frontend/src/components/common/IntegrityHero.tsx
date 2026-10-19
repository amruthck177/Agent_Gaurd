import React from 'react'
import {
  ShieldCheck,
  ShieldAlert,
  Copy,
  Download,
  RotateCw,
  Lock,
} from 'lucide-react'

export interface IntegrityHeroProps {
  status: 'verified' | 'broken'
  recordCount: number
  brokenRecordId?: number
  headHash?: string
  genesisHash?: string
  lastVerifiedSecondsAgo?: number
  onVerify?: () => void
  onExportCsv?: () => void
  onCopyHash?: (h: string) => void
  isVerifying?: boolean
}

export const IntegrityHero: React.FC<IntegrityHeroProps> = ({
  status,
  recordCount,
  brokenRecordId = 812,
  headHash = '9f3a8bc721…d84e',
  genesisHash = '00000a417b…c92f',
  lastVerifiedSecondsAgo = 8,
  onVerify,
  onExportCsv,
  onCopyHash,
  isVerifying = false,
}) => {
  const isVerified = status === 'verified'

  const borderClass = isVerified
    ? 'border-allow/50 shadow-[0_0_24px_-10px_rgba(46,158,91,0.25)]'
    : 'border-block/60 shadow-[0_0_24px_-10px_rgba(214,69,69,0.3)]'

  const bannerBg = isVerified
    ? 'bg-allow/15 border-allow/30 text-allow'
    : 'bg-block/15 border-block/40 text-block'

  return (
    <div className={`rounded-card border bg-surface p-5 sm:p-6 relative overflow-hidden transition-all ${borderClass}`}>
      {/* Subtle Glow */}
      <div
        className={`absolute top-0 right-0 w-48 h-48 rounded-full pointer-events-none blur-3xl opacity-10 ${
          isVerified ? 'bg-allow' : 'bg-block'
        }`}
      />

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
        {/* Left Side: Status Info */}
        <div className="space-y-4 max-w-2xl">
          <div className="flex items-center gap-2.5">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isVerified ? 'bg-allow shadow-[0_0_8px_#2E9E5B]' : 'bg-block animate-ping'
              }`}
            />
            <h2 className="text-[18px] sm:text-[20px] font-bold text-ink tracking-tight">
              Cryptographic Ledger Integrity
            </h2>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-surface2 border border-line text-accent">
              SHA-256 Merkle Chain
            </span>
          </div>

          {/* Banner */}
          <div className={`p-4 rounded-lg border flex items-center gap-3.5 ${bannerBg}`}>
            {isVerified ? (
              <ShieldCheck className="w-6 h-6 text-allow shrink-0" />
            ) : (
              <ShieldAlert className="w-6 h-6 text-block shrink-0" />
            )}
            <div>
              <div className="font-semibold text-[15px]">
                {isVerified
                  ? `Verified: ${recordCount.toLocaleString('en-IN')} records, chain intact`
                  : `Chain broken at record #${brokenRecordId}`}
              </div>
              <p className="text-[12px] opacity-80 mt-0.5">
                {isVerified
                  ? 'All sequential block hashes match cryptographic back-pointers. Zero mutable storage.'
                  : 'Computed prev_hash does not match stored block pointer. Fail-closed safety enforced.'}
              </p>
            </div>
          </div>

          {/* Forensic Proof Details (Hashes) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
            <div className="p-2.5 rounded bg-surface2/60 border border-line text-[12px]">
              <span className="text-[11px] text-ink2 block">Head Hash (Latest Block)</span>
              <div className="font-mono font-medium text-ink flex items-center justify-between mt-1">
                <span className="truncate">{headHash}</span>
                <button
                  onClick={() => onCopyHash?.(headHash)}
                  className="text-ink2 hover:text-accent ml-1"
                  title="Copy Head Hash"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <div className="p-2.5 rounded bg-surface2/60 border border-line text-[12px]">
              <span className="text-[11px] text-ink2 block">Root Genesis Hash</span>
              <div className="font-mono font-medium text-ink flex items-center justify-between mt-1">
                <span className="truncate">{genesisHash}</span>
                <button
                  onClick={() => onCopyHash?.(genesisHash)}
                  className="text-ink2 hover:text-accent ml-1"
                  title="Copy Genesis Hash"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Side: Action Buttons */}
        <div className="flex flex-col sm:flex-row lg:flex-col gap-3 shrink-0 lg:w-48">
          <button
            onClick={onVerify}
            disabled={isVerifying}
            className="h-11 px-4 rounded-lg bg-accent text-bg hover:bg-accent/90 font-semibold text-[13px] flex items-center justify-center gap-2 transition-all active:scale-95 shadow-md shadow-accent/10 focus-accent disabled:opacity-50"
          >
            <RotateCw className={`w-4 h-4 ${isVerifying ? 'animate-spin' : ''}`} />
            <span>{isVerifying ? 'Verifying...' : 'Verify integrity'}</span>
          </button>

          <button
            onClick={onExportCsv}
            className="h-11 px-4 rounded-lg border border-line hover:border-ink2 bg-surface2 text-ink hover:text-white font-medium text-[13px] flex items-center justify-center gap-2 transition-colors active:scale-95"
          >
            <Download className="w-4 h-4 text-ink2" />
            <span>Export CSV</span>
          </button>

          <div className="pt-2 border-t border-line/60 font-mono text-[11px] text-ink2 text-center lg:text-left flex items-center justify-center lg:justify-start gap-1">
            <Lock className="w-3 h-3 text-accent" />
            <span>
              {isVerified ? `Synced (${lastVerifiedSecondsAgo}s ago)` : 'Tamper Alert'}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
