import React, { useState, useEffect, useMemo } from 'react'
import { RotateCw, Smartphone, AlertCircle, ExternalLink, QrCode as QrIcon } from 'lucide-react'
import { ApprovalCard, ApprovalCardData, ApprovalState } from '../components/common/ApprovalCard'
import { EmptyState } from '../components/common/EmptyState'
import { Skeleton } from '../components/common/Skeleton'
import { QrCode } from '../components/common/QrCode'
import { api, Approval, ApprovalStatus } from '../lib/api'
import { useEvents } from '../lib/useEvents'

export const Approvals: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ApprovalStatus>('pending')
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)

  // Live WebSocket
  useEvents((event) => {
    if (event.type === 'approval.created' || event.type === 'approval.updated') {
      loadApprovals()
    }
  })

  const loadApprovals = async () => {
    try {
      const data = await api.listApprovals()
      setApprovals(data)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load approvals')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadApprovals()
  }, [])

  // Filter approvals by tab
  const filteredApprovals = useMemo(() => {
    return approvals.filter((a) => a.status === activeTab)
  }, [approvals, activeTab])

  // Count by status
  const counts = useMemo(() => {
    const c: Record<string, number> = {
      pending: 0,
      approved: 0,
      rejected: 0,
      expired: 0,
      revoked: 0,
    }
    approvals.forEach((a) => {
      if (c[a.status] !== undefined) c[a.status]++
    })
    return c
  }, [approvals])

  // Approve action
  const handleApprove = async (id: string) => {
    setActionLoadingId(id)
    try {
      await api.approve(id)
      await loadApprovals()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Approve failed')
    } finally {
      setActionLoadingId(null)
    }
  }

  // Reject action
  const handleReject = async (id: string) => {
    setActionLoadingId(id)
    try {
      await api.reject(id)
      await loadApprovals()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Reject failed')
    } finally {
      setActionLoadingId(null)
    }
  }

  // Revoke action
  const handleRevoke = async (id: string) => {
    setActionLoadingId(id)
    try {
      await api.revoke(id)
      await loadApprovals()
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Revoke failed')
    } finally {
      setActionLoadingId(null)
    }
  }

  // Helper to map backend approval to ApprovalCardData
  const mapToCardData = (ap: Approval): ApprovalCardData => {
    let params: Record<string, unknown> = {}
    try {
      params = JSON.parse(ap.approved_params_json)
    } catch {
      // ignore
    }

    const recipient =
      (params.recipient as string) || (params.to as string) || (params.sql as string) || 'Recipient'
    const amount = (params.amount as number) || (params.amount_paise ? (params.amount_paise as number) / 100 : 5000)

    // Calculate remaining seconds if expires_at exists
    let remainingSeconds = 600
    if (ap.expires_at) {
      const diff = Math.floor((new Date(ap.expires_at).getTime() - Date.now()) / 1000)
      remainingSeconds = Math.max(0, diff)
    }

    return {
      id: ap.id,
      title: `Payment ₹${amount.toLocaleString('en-IN')} to ${recipient}`,
      amount,
      recipient,
      tool: ap.tool,
      state: ap.status as ApprovalState,
      tags: ['Single-use token', `Agent: ${ap.agent_id}`],
      agentId: ap.agent_id,
      expiresInSeconds: remainingSeconds,
      used: ap.used_at !== null,
    }
  }

  const tabs: { id: ApprovalStatus; label: string; count: number }[] = [
    { id: 'pending', label: 'Pending', count: counts.pending },
    { id: 'approved', label: 'Approved', count: counts.approved },
    { id: 'rejected', label: 'Rejected', count: counts.rejected },
    { id: 'expired', label: 'Expired', count: counts.expired },
    { id: 'revoked', label: 'Revoked', count: counts.revoked },
  ]

  // First pending approval for live preview
  const firstPending = filteredApprovals[0] ? mapToCardData(filteredApprovals[0]) : null

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-[22px] sm:text-[24px] font-bold text-ink tracking-tight">
              Human Approvals Console
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-accent/15 border border-accent/30 text-accent text-[11px] font-mono font-semibold">
              Cryptographically Bound
            </span>
          </div>
          <p className="text-[13px] text-ink2 mt-1">
            Single-use cryptographic authorizations for sensitive agent tool actions.
          </p>
        </div>

        <button
          onClick={loadApprovals}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-line text-ink2 hover:text-ink text-[12px] font-medium transition-colors"
        >
          <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-line overflow-x-auto pb-1">
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-t-lg font-medium text-[13px] transition-all border-b-2 whitespace-nowrap ${
                isActive
                  ? 'border-accent text-accent bg-surface2/60 font-semibold shadow-sm'
                  : 'border-transparent text-ink2 hover:text-ink hover:bg-surface/50'
              }`}
            >
              <span>{tab.label}</span>
              <span
                className={`px-1.5 py-0.2 rounded-full font-mono text-[10px] font-bold ${
                  isActive
                    ? 'bg-accent/20 text-accent'
                    : 'bg-surface2 text-ink2'
                }`}
              >
                {tab.count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Main Grid: Approvals List (65%) + Phone Preview (35%) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Approvals List */}
        <div className="xl:col-span-8 space-y-5">
          {error ? (
            <div className="p-4 rounded-xl bg-block/15 border border-block/40 text-block text-xs font-medium flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          ) : loading && approvals.length === 0 ? (
            <div className="space-y-4">
              <Skeleton className="h-48 w-full rounded-card" />
              <Skeleton className="h-48 w-full rounded-card" />
            </div>
          ) : filteredApprovals.length === 0 ? (
            <EmptyState
              title={`No ${activeTab} approvals`}
              description={`There are currently no authorization records in "${activeTab}" status.`}
            />
          ) : (
            <div className="space-y-5">
              {filteredApprovals.map((ap) => {
                const cardData = mapToCardData(ap)
                const isOperating = actionLoadingId === ap.id

                return (
                  <div key={ap.id} className={isOperating ? 'opacity-50 pointer-events-none' : ''}>
                    <ApprovalCard
                      data={cardData}
                      onApprove={handleApprove}
                      onReject={handleReject}
                      onRevoke={handleRevoke}
                    />
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Live Smartphone Approver Simulator (design.md §5.3 / 3B) */}
        <div className="xl:col-span-4 space-y-4 xl:sticky xl:top-24">
          {/* Local QR Code Card opening /m/:approvalId */}
          <div className="p-4 rounded-2xl bg-surface border border-line shadow-sm space-y-3">
            <div className="flex items-center justify-between text-xs font-mono text-ink2">
              <span className="flex items-center gap-1.5 font-bold text-ink">
                <QrIcon className="w-4 h-4 text-accent" />
                <span>Mobile Enclave QR</span>
              </span>
              <span className="text-[10px] px-2 py-0.5 rounded bg-surface2 text-accent border border-line font-mono font-semibold">
                Offline Local QR
              </span>
            </div>

            <div className="flex flex-col sm:flex-row xl:flex-col items-center gap-3 pt-1">
              <div className="shrink-0">
                <QrCode
                  value={`${window.location.origin}/m/${firstPending?.id || approvals[0]?.id || 'APR-0001'}`}
                  size={120}
                />
              </div>

              <div className="space-y-2 text-center sm:text-left xl:text-center flex-1">
                <p className="text-xs text-ink2 leading-relaxed">
                  Scan with smartphone to review and sign action tokens on{' '}
                  <code className="text-accent font-mono">
                    /m/{firstPending?.id || approvals[0]?.id || 'APR-0001'}
                  </code>
                  .
                </p>

                <a
                  href={`/m/${firstPending?.id || approvals[0]?.id || 'APR-0001'}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface2 hover:bg-surface2/80 text-ink text-xs font-semibold border border-line transition-all active:scale-95"
                >
                  <span>Open Mobile Screen</span>
                  <ExternalLink className="w-3.5 h-3.5 text-accent" />
                </a>
              </div>
            </div>
          </div>

          <div className="hidden xl:block space-y-3">
          <div className="flex items-center justify-between text-[12px] font-mono text-ink2 px-1">
            <span className="flex items-center gap-1.5">
              <Smartphone className="w-4 h-4 text-accent" />
              <span>Approver Mobile Screen</span>
            </span>
            <span className="text-[10px] bg-surface2 px-2 py-0.5 rounded border border-line">
              Simulated
            </span>
          </div>

          {/* Smartphone Frame Container */}
          <div className="w-full max-w-[360px] mx-auto rounded-[32px] border-4 border-line bg-surface p-4 shadow-2xl relative overflow-hidden">
            {/* Speaker notch */}
            <div className="w-24 h-3.5 bg-line rounded-full mx-auto mb-3" />

            {/* Chat Mock */}
            <div className="space-y-3 text-[12px]">
              <div className="flex items-center justify-between text-[10px] text-ink2 border-b border-line pb-1">
                <span>AgentGuard Alerts</span>
                <span className="text-allow">● Verified Enclave</span>
              </div>

              {firstPending ? (
                <div className="p-3.5 rounded-xl bg-surface2 border border-line space-y-2.5">
                  <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-ask/15 text-ask border border-ask/30 font-bold">
                    ACTION HELD AT GATE
                  </span>
                  <div className="font-semibold text-ink text-[13px]">{firstPending.title}</div>
                  <div className="text-[11px] text-ink2 font-mono">
                    Tool: <strong className="text-accent">{firstPending.tool}</strong>
                  </div>
                  <div className="text-[10px] text-ink2 border-t border-line/60 pt-1.5">
                    "This is the real action, not the agent's explanation."
                  </div>
                  <div className="pt-1 flex gap-2">
                    <button
                      onClick={() => handleApprove(firstPending.id)}
                      className="flex-1 py-1.5 rounded-lg bg-accent text-bg font-bold text-[11px] text-center"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleReject(firstPending.id)}
                      className="px-3 py-1.5 rounded-lg border border-block/50 text-block font-semibold text-[11px] text-center"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-6 text-center text-ink2 text-[12px]">
                  No pending action waiting on mobile.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  )
}
