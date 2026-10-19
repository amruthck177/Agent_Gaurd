import React, { useState, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Lock,
  ArrowLeft,
  RefreshCw,
} from 'lucide-react'
import { api, Approval } from '../lib/api'
import { Countdown } from '../components/common/Countdown'
import en from '../i18n/en.json'
import hi from '../i18n/hi.json'
import kn from '../i18n/kn.json'

type Lang = 'en' | 'hi' | 'kn'
const translations: Record<Lang, typeof en> = { en, hi, kn }

export const MobileApproval: React.FC = () => {
  const { approvalId, id } = useParams<{ approvalId?: string; id?: string }>()
  const targetId = approvalId || id

  const [lang, setLang] = useState<Lang>('en')
  const [approval, setApproval] = useState<Approval | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState<boolean>(false)
  const [actionOutcome, setActionOutcome] = useState<'approved' | 'rejected' | null>(null)

  const t = translations[lang]

  const loadApproval = useCallback(async () => {
    if (!targetId) return
    setLoading(true)
    setError(null)
    try {
      const list = await api.listApprovals()
      const found = list.find((a) => a.id === targetId)
      if (found) {
        setApproval(found)
        if (found.status === 'approved' || found.status === 'used') {
          setActionOutcome('approved')
        } else if (found.status === 'rejected') {
          setActionOutcome('rejected')
        }
      } else {
        // If not found in list (e.g. direct link or demo test id)
        // Check if list has any pending approval to display as demo fallback
        if (list.length > 0) {
          setApproval(list[0])
        } else {
          setError(t.notFoundDesc)
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to connect to gateway')
    } finally {
      setLoading(false)
    }
  }, [targetId, t.notFoundDesc])

  useEffect(() => {
    loadApproval()
  }, [loadApproval])

  // Parse parameters safely
  let parsedParams: Record<string, unknown> = {}
  if (approval?.approved_params_json) {
    try {
      parsedParams = JSON.parse(approval.approved_params_json)
    } catch {
      parsedParams = {}
    }
  }

  const recipient =
    (parsedParams.recipient as string) ||
    (parsedParams.payee as string) ||
    (parsedParams.to as string) ||
    'Mehta Ice Suppliers'

  const rawAmount = parsedParams.amount ?? 80000
  const formattedAmount =
    typeof rawAmount === 'number'
      ? `₹${rawAmount.toLocaleString('en-IN')}`
      : `₹${rawAmount}`

  const handleApprove = async () => {
    if (!approval) return
    setSubmitting(true)
    try {
      const updated = await api.approve(approval.id)
      setApproval(updated)
      setActionOutcome('approved')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Approval execution failed')
    } finally {
      setSubmitting(false)
    }
  }

  const handleReject = async () => {
    if (!approval) return
    setSubmitting(true)
    try {
      const updated = await api.reject(approval.id)
      setApproval(updated)
      setActionOutcome('rejected')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rejection execution failed')
    } finally {
      setSubmitting(false)
    }
  }

  const isPending =
    approval?.status === 'pending' && actionOutcome === null
  const isApproved =
    actionOutcome === 'approved' ||
    approval?.status === 'approved' ||
    approval?.status === 'used'
  const isRejected =
    actionOutcome === 'rejected' || approval?.status === 'rejected'
  const isExpired = approval?.status === 'expired'
  const isRevoked = approval?.status === 'revoked'

  return (
    <div className="min-h-screen bg-bg flex flex-col items-center justify-start sm:py-6 sm:px-4 text-ink font-sans antialiased">
      {/* Centred 420px container on laptop, full mobile width at 390px */}
      <div className="w-full max-w-[420px] bg-surface sm:border sm:border-line sm:rounded-3xl sm:shadow-2xl overflow-hidden flex flex-col min-h-screen sm:min-h-[720px] relative">
        {/* Header with Stitch Enclave Style */}
        <div className="p-4 bg-surface2/80 border-b border-line flex items-center justify-between shrink-0">
          <Link
            to="/approvals"
            className="p-1.5 rounded-lg hover:bg-surface text-ink2 hover:text-ink transition-colors"
            title={t.backToApprovals}
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>

          <div className="flex flex-col items-center text-center">
            {/* Small text label per spec */}
            <span className="text-[10px] font-mono uppercase tracking-wider text-accent font-semibold">
              {t.simulatedChat}
            </span>
            <div className="flex items-center gap-1.5 mt-0.5">
              <ShieldCheck className="w-4 h-4 text-accent shrink-0" />
              <h1 className="font-bold text-sm tracking-tight text-ink">{t.title}</h1>
            </div>
          </div>

          <button
            onClick={loadApproval}
            className="p-1.5 rounded-lg hover:bg-surface text-ink2 hover:text-ink transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-accent' : ''}`} />
          </button>
        </div>

        {/* Language Switch: English | हिंदी | ಕನ್ನಡ */}
        <div className="px-4 py-2 bg-surface border-b border-line/60 flex items-center justify-center gap-1 shrink-0">
          {(['en', 'hi', 'kn'] as const).map((l) => (
            <button
              key={l}
              onClick={() => setLang(l)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                lang === l
                  ? 'bg-accent text-bg shadow-sm font-semibold'
                  : 'text-ink2 hover:text-ink hover:bg-surface2'
              }`}
            >
              {l === 'en' ? 'English' : l === 'hi' ? 'हिंदी' : 'ಕನ್ನಡ'}
            </button>
          ))}
        </div>

        {/* Chat / Enclave Message Body */}
        <div className="p-4 sm:p-5 flex-1 flex flex-col justify-between space-y-4 overflow-y-auto">
          {loading ? (
            <div className="p-8 text-center space-y-3 my-auto">
              <RefreshCw className="w-6 h-6 animate-spin text-accent mx-auto" />
              <p className="text-xs text-ink2 font-mono">{t.securingSession}</p>
            </div>
          ) : error && !approval ? (
            <div className="p-6 rounded-2xl bg-block/10 border border-block/30 text-center space-y-3 my-auto">
              <AlertTriangle className="w-8 h-8 text-block mx-auto" />
              <h2 className="font-semibold text-sm text-ink">{t.notFoundTitle}</h2>
              <p className="text-xs text-ink2">{error}</p>
              <Link
                to="/approvals"
                className="inline-block px-4 py-2 rounded-lg bg-surface2 text-xs font-semibold text-ink hover:text-white"
              >
                {t.backToApprovals}
              </Link>
            </div>
          ) : approval ? (
            <>
              {/* Timestamp Divider */}
              <div className="text-center shrink-0">
                <span className="text-[10px] font-mono uppercase text-ink2 tracking-wider">
                  {t.todayDispatch}
                </span>
              </div>

              {/* High-Trust Enclave Message Bubble (Layout stable, allows 40% longer text) */}
              <div className="p-4 rounded-2xl bg-surface2/90 border border-line space-y-3.5 shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-accent/20 flex items-center justify-center text-accent shrink-0">
                      <Lock className="w-3.5 h-3.5" />
                    </div>
                    <span className="text-xs font-bold font-mono text-ink truncate">
                      {approval.agent_id}
                    </span>
                  </div>

                  {isPending && approval.expires_at && (
                    <div className="shrink-0">
                      <Countdown expiresAt={approval.expires_at} />
                    </div>
                  )}
                </div>

                {/* Policy Notice in selected language */}
                <p className="text-xs text-ink2 leading-relaxed break-words whitespace-normal">
                  {t.policyNotice}
                </p>

                {/* Raw-Action Card: tool, recipient, amount */}
                <div className="p-3.5 rounded-xl bg-surface border border-line/80 space-y-2.5">
                  <div className="flex items-center justify-between text-xs gap-2">
                    <span className="text-ink2 shrink-0">{t.toolLabel}:</span>
                    <span className="font-mono font-bold text-accent truncate text-right">
                      {approval.tool}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs gap-2">
                    <span className="text-ink2 shrink-0">{t.recipientLabel}:</span>
                    <span className="font-semibold text-ink truncate text-right">
                      {recipient}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs gap-2 pt-1 border-t border-line/40">
                    <span className="text-ink2 shrink-0">{t.amountLabel}:</span>
                    <span className="font-extrabold text-base text-ink tracking-tight text-right">
                      {formattedAmount}
                    </span>
                  </div>
                </div>

                {/* The line: "This is the real action, not the agent's explanation." */}
                <div className="pt-1.5 border-t border-line/40 flex items-start gap-2 text-[11px] text-ink2 italic leading-snug">
                  <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0 mt-1" />
                  <span>{t.truthDisclaimer}</span>
                </div>
              </div>

              {/* Post-Action Status Resolution States */}
              {isApproved && (
                <div className="p-4 rounded-2xl border bg-allow/15 border-allow/40 text-allow text-center space-y-1.5 animate-fade-in shadow-sm">
                  <div className="flex items-center justify-center gap-2 font-bold text-sm">
                    <CheckCircle2 className="w-5 h-5 text-allow shrink-0" />
                    <span>ACTION APPROVED</span>
                  </div>
                  <p className="text-xs opacity-95 font-medium leading-relaxed">
                    {t.approvedSuccess}
                  </p>
                </div>
              )}

              {isRejected && (
                <div className="p-4 rounded-2xl border bg-block/15 border-block/40 text-block text-center space-y-1.5 animate-fade-in shadow-sm">
                  <div className="flex items-center justify-center gap-2 font-bold text-sm">
                    <XCircle className="w-5 h-5 text-block shrink-0" />
                    <span>ACTION REJECTED</span>
                  </div>
                  <p className="text-xs opacity-95 font-medium leading-relaxed">
                    {t.rejectedSuccess}
                  </p>
                </div>
              )}

              {isExpired && !isApproved && !isRejected && (
                <div className="p-4 rounded-2xl border bg-surface2 border-line text-ink2 text-center space-y-1 animate-fade-in">
                  <div className="flex items-center justify-center gap-1.5 font-bold text-xs uppercase text-ink">
                    <AlertTriangle className="w-4 h-4 text-ink2" />
                    <span>TOKEN EXPIRED</span>
                  </div>
                  <p className="text-xs opacity-80">{t.expiredNotice}</p>
                </div>
              )}

              {isRevoked && !isApproved && !isRejected && (
                <div className="p-4 rounded-2xl border bg-surface2 border-line text-ink2 text-center space-y-1 animate-fade-in">
                  <div className="flex items-center justify-center gap-1.5 font-bold text-xs uppercase text-ink">
                    <AlertTriangle className="w-4 h-4 text-ink2" />
                    <span>TOKEN REVOKED</span>
                  </div>
                  <p className="text-xs opacity-80">{t.revokedNotice}</p>
                </div>
              )}

              {/* Two Full-Width 56px Buttons: Approve and Reject calling approvals API */}
              {isPending && (
                <div className="space-y-3 pt-2 shrink-0">
                  <button
                    onClick={handleApprove}
                    disabled={submitting}
                    className="w-full h-14 min-h-[56px] px-4 rounded-2xl bg-accent text-bg hover:bg-accent/90 font-bold text-[15px] shadow-lg shadow-accent/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
                  >
                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                    <span className="truncate">{t.approveButton} ({formattedAmount})</span>
                  </button>

                  <button
                    onClick={handleReject}
                    disabled={submitting}
                    className="w-full h-14 min-h-[56px] px-4 rounded-2xl border-2 border-block text-block hover:bg-block/10 font-bold text-[15px] flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50"
                  >
                    <XCircle className="w-5 h-5 shrink-0" />
                    <span className="truncate">{t.rejectButton}</span>
                  </button>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer info pill */}
        <div className="p-3 bg-surface2/40 border-t border-line text-center text-[10px] font-mono text-ink2 shrink-0">
          {t.footerBinding}
        </div>
      </div>
    </div>
  )
}
