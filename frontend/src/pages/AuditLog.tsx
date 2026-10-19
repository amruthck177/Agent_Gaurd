import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  Check,
  ChevronRight,
} from 'lucide-react'
import { api, AuditRecord, AuditVerifyResponse } from '../lib/api'
import { IntegrityHero } from '../components/common/IntegrityHero'
import { AuditRow, AuditRecordItem } from '../components/common/AuditRow'
import { DecisionChip, DecisionType } from '../components/common/DecisionChip'
import { EmptyState } from '../components/common/EmptyState'
import { Skeleton } from '../components/common/Skeleton'
import { Drawer } from '../components/layout/Drawer'

export const AuditLog: React.FC = () => {
  const [records, setRecords] = useState<AuditRecord[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const [verification, setVerification] = useState<AuditVerifyResponse | null>(null)
  const [verifying, setVerifying] = useState<boolean>(false)

  // Filters
  const [search, setSearch] = useState<string>('')
  const [agentFilter, setAgentFilter] = useState<string>('ALL')
  const [decisionFilter, setDecisionFilter] = useState<string>('ALL')

  // Selected Record for Drawer
  const [selectedRecord, setSelectedRecord] = useState<AuditRecord | null>(null)
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false)

  // Copy notification
  const [copiedHash, setCopiedHash] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [recList, verifyRes] = await Promise.all([
        api.listAudit({ limit: 200 }),
        api.verifyAudit().catch(() => ({ ok: false, checked: 0, broken_at: null })),
      ])
      setRecords(recList)
      setVerification(verifyRes)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch audit log'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  const handleVerify = async () => {
    setVerifying(true)
    try {
      const res = await api.verifyAudit()
      setVerification(res)
    } catch (err) {
      setVerification({ ok: false, checked: records.length, broken_at: -1 })
    } finally {
      setVerifying(false)
    }
  }

  const handleExportCsv = () => {
    const params: Record<string, string> = {}
    if (agentFilter !== 'ALL') params.agent_id = agentFilter
    if (decisionFilter !== 'ALL') params.decision = decisionFilter
    if (search.trim()) params.search = search.trim()

    const url = api.getAuditCsvUrl(params)
    window.open(url, '_blank')
  }

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash)
    setCopiedHash(hash)
    setTimeout(() => setCopiedHash(null), 2500)
  }

  // Derive unique agents
  const availableAgents = useMemo(() => {
    const set = new Set<string>()
    records.forEach((r) => {
      if (r.agent_id) set.add(r.agent_id)
    })
    return Array.from(set).sort()
  }, [records])

  // Filter records
  const filteredRecords = useMemo(() => {
    return records.filter((r) => {
      if (agentFilter !== 'ALL' && r.agent_id !== agentFilter) return false
      if (decisionFilter !== 'ALL' && r.decision !== decisionFilter) return false
      if (search.trim()) {
        const q = search.toLowerCase()
        const matchTool = r.tool?.toLowerCase().includes(q)
        const matchAgent = r.agent_id?.toLowerCase().includes(q)
        const matchReason = r.reason?.toLowerCase().includes(q)
        const matchHash = r.hash?.toLowerCase().includes(q)
        const matchId = String(r.id).includes(q)
        if (!matchTool && !matchAgent && !matchReason && !matchHash && !matchId) {
          return false
        }
      }
      return true
    })
  }, [records, agentFilter, decisionFilter, search])

  // Head and Genesis hashes
  const headHash = records.length > 0 ? records[0].hash : '000000000000000000'
  const genesisHash = records.length > 0 ? records[records.length - 1].prev_hash : '000000000000000000'
  const isChainBroken = verification ? !verification.ok : false
  const brokenAtId = verification?.broken_at ?? undefined

  return (
    <div className="space-y-6 pb-12 max-w-7xl mx-auto">
      {/* Page Title & Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Audit Log & Ledger</h1>
          <p className="text-[13px] text-ink2 mt-1">
            Tamper-evident SHA-256 Merkle chain recording every security enforcement decision.
          </p>
        </div>

        {copiedHash && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent/15 border border-accent/40 text-accent text-xs font-mono animate-fade-in">
            <Check className="w-3.5 h-3.5" />
            <span>Copied to clipboard</span>
          </div>
        )}
      </div>

      {/* Hero: Integrity Status */}
      <IntegrityHero
        status={isChainBroken ? 'broken' : 'verified'}
        recordCount={verification?.checked ?? records.length}
        brokenRecordId={brokenAtId}
        headHash={headHash}
        genesisHash={genesisHash}
        lastVerifiedSecondsAgo={12}
        onVerify={handleVerify}
        onExportCsv={handleExportCsv}
        onCopyHash={handleCopyHash}
        isVerifying={verifying}
      />

      {/* Controls & Filter Bar */}
      <div className="p-4 rounded-xl bg-surface border border-line flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 shadow-sm">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-ink2 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search tool, agent, reason, hash, ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-surface2 border border-line text-[13px] text-ink focus:outline-none focus:border-accent"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex items-center gap-1.5 bg-surface2 px-2.5 py-1.5 rounded-lg border border-line text-[12px] text-ink2">
            <Filter className="w-3.5 h-3.5 text-accent" />
            <select
              value={agentFilter}
              onChange={(e) => setAgentFilter(e.target.value)}
              className="bg-transparent text-ink text-[12px] font-medium focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Agents</option>
              {availableAgents.map((ag) => (
                <option key={ag} value={ag}>
                  {ag}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-1.5 bg-surface2 px-2.5 py-1.5 rounded-lg border border-line text-[12px] text-ink2">
            <select
              value={decisionFilter}
              onChange={(e) => setDecisionFilter(e.target.value)}
              className="bg-transparent text-ink text-[12px] font-medium focus:outline-none cursor-pointer"
            >
              <option value="ALL">All Decisions</option>
              <option value="ALLOW">ALLOW</option>
              <option value="ASK_HUMAN">ASK HUMAN</option>
              <option value="BLOCK">BLOCK</option>
            </select>
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg border border-line hover:border-ink2 bg-surface2 text-ink2 hover:text-ink transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-accent' : ''}`} />
          </button>
        </div>
      </div>

      {/* Content Area */}
      {error ? (
        <div className="p-6 rounded-xl bg-block/10 border border-block/30 text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-block mx-auto" />
          <h3 className="font-semibold text-ink text-[15px]">Failed to Load Audit Ledger</h3>
          <p className="text-[13px] text-ink2 max-w-md mx-auto">{error}</p>
          <button
            onClick={loadData}
            className="px-4 py-2 rounded-lg bg-surface2 border border-line text-ink hover:text-white text-xs font-semibold"
          >
            Retry Connection
          </button>
        </div>
      ) : loading ? (
        <div className="p-6 rounded-xl bg-surface border border-line space-y-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : filteredRecords.length === 0 ? (
        <EmptyState
          title="No Audit Records Matched"
          description="Adjust your search filters or generate security events to view cryptographic proofs."
        />
      ) : (
        <>
          {/* Desktop Table (1440px / md breakpoint) */}
          <div className="hidden md:block rounded-xl border border-line bg-surface overflow-hidden shadow-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-line bg-surface2/60 text-[11px] font-mono uppercase tracking-wider text-ink2">
                    <th className="py-3 px-4 font-semibold">#</th>
                    <th className="py-3 px-3 font-semibold">Timestamp</th>
                    <th className="py-3 px-3 font-semibold">Agent</th>
                    <th className="py-3 px-3 font-semibold">Action / Tool</th>
                    <th className="py-3 px-3 font-semibold">Decision</th>
                    <th className="py-3 px-3 font-semibold">Enforcement Reason</th>
                    <th className="py-3 px-3 font-semibold hidden md:table-cell">Decided By</th>
                    <th className="py-3 px-3 font-semibold text-center">Current Hash</th>
                    <th className="py-3 px-3 font-semibold text-center">Prev Hash</th>
                    <th className="py-3 px-4 font-semibold text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/40">
                  {filteredRecords.map((r, index) => {
                    const isBroken = Boolean(
                      verification && !verification.ok && verification.broken_at === r.id
                    )
                    const item: AuditRecordItem = {
                      id: r.id,
                      timestamp: r.ts ? new Date(r.ts).toLocaleTimeString() : 'N/A',
                      agent: r.agent_id || 'unknown',
                      action: r.tool || 'gateway',
                      decision: r.decision as DecisionType,
                      reason: r.reason || 'Policy check',
                      decidedBy: r.approval_id ? 'Human (SMS)' : 'Automated Gate',
                      currentHash: r.hash || '',
                      prevHash: r.prev_hash || '',
                      isChainBroken: isBroken,
                    }

                    return (
                      <AuditRow
                        key={r.id}
                        record={item}
                        isLast={index === filteredRecords.length - 1}
                        onInspect={() => {
                          setSelectedRecord(r)
                          setDrawerOpen(true)
                        }}
                        onCopyHash={handleCopyHash}
                      />
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Card List (390px / sm screen per design.md 3B) */}
          <div className="md:hidden space-y-3">
            {filteredRecords.map((r) => {
              const isBroken =
                verification && !verification.ok && verification.broken_at === r.id
              const shortHash = (h: string) => (h && h.length > 10 ? `${h.slice(0, 6)}…${h.slice(-4)}` : h)

              return (
                <div
                  key={r.id}
                  onClick={() => {
                    setSelectedRecord(r)
                    setDrawerOpen(true)
                  }}
                  className={`p-4 rounded-xl border bg-surface transition-all active:scale-[0.99] cursor-pointer shadow-sm ${
                    isBroken ? 'border-block/80 bg-block/10' : 'border-line hover:border-accent/40'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-accent">#{r.id}</span>
                      <DecisionChip decision={r.decision as DecisionType} size="sm" />
                    </div>
                    <span className="text-[11px] font-mono text-ink2">
                      {r.ts ? new Date(r.ts).toLocaleTimeString() : ''}
                    </span>
                  </div>

                  <div className="flex items-baseline justify-between gap-2 mb-1">
                    <span className="font-mono text-[13px] font-semibold text-ink">{r.tool}</span>
                    <span className="text-[11px] font-mono text-ink2 px-1.5 py-0.5 rounded bg-surface2 border border-line">
                      {r.agent_id}
                    </span>
                  </div>

                  <p className="text-[12px] text-ink2 line-clamp-2 mb-3">{r.reason}</p>

                  <div className="pt-2 border-t border-line/60 flex items-center justify-between text-[11px] font-mono text-ink2">
                    <div className="flex items-center gap-1.5">
                      <span>Hash:</span>
                      <span className="text-ink">{shortHash(r.hash)}</span>
                    </div>

                    <div className="flex items-center gap-1 text-accent font-sans text-xs font-medium">
                      <span>Inspect</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* Inspect Record Drawer (Adapts: Right Drawer on Desktop, Bottom Sheet on Mobile) */}
      <Drawer
        isOpen={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        data={
          selectedRecord
            ? {
                id: selectedRecord.id,
                decision: selectedRecord.decision as DecisionType,
                tool: selectedRecord.tool || 'gateway',
                amount: 0,
                agent: selectedRecord.agent_id || 'system',
                time: selectedRecord.ts
                  ? new Date(selectedRecord.ts).toLocaleTimeString()
                  : 'N/A',
                incidentId: `INC-${selectedRecord.id}`,
                interceptId: `INT-${selectedRecord.id}`,
                reason: selectedRecord.reason || 'Security policy evaluation',
                ruleId: `POL-${selectedRecord.tool}`,
                decidedBy: selectedRecord.approval_id
                  ? 'Human Approver (SMS)'
                  : 'Gateway Rules Engine',
                explanation: selectedRecord.reason || 'Decision enforced by gateway policy.',
                comparisonRows: [],
                executionCount: selectedRecord.executed ? 1 : 0,
                lossPrevented: 0,
                rawRequestJson: selectedRecord.params_masked || '{}',
                recordNumber: selectedRecord.id,
                currentHash: selectedRecord.hash || '',
                prevHash: selectedRecord.prev_hash || '',
              }
            : null
        }
      />
    </div>
  )
}
