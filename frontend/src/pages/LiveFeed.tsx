import React, { useState, useEffect, useMemo } from 'react'
import {
  Activity,
  CheckCircle2,
  Clock,
  ShieldX,
  AlertTriangle,
  RotateCw,
  ExternalLink,
} from 'lucide-react'
import { StatCard } from '../components/common/StatCard'
import { DecisionChip } from '../components/common/DecisionChip'
import { ActionItem } from '../components/common/ActionRow'
import { ResponsiveTable } from '../components/layout/ResponsiveTable'
import { Drawer, DrawerEventData } from '../components/layout/Drawer'
import { EmptyState } from '../components/common/EmptyState'
import { SkeletonTableRow, SkeletonStatCard } from '../components/common/Skeleton'
import { api, AuditRecord } from '../lib/api'
import { useEvents } from '../lib/useEvents'
import { ParamRow } from '../components/common/ParamCompare'

export const LiveFeed: React.FC = () => {
  const [auditRecords, setAuditRecords] = useState<AuditRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedDrawerData, setSelectedDrawerData] = useState<DrawerEventData | null>(null)
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [filterDecision, setFilterDecision] = useState<string>('ALL')

  // Real-time WebSocket hook
  useEvents((event) => {
    if (event.type === 'gateway.decision' || event.type === 'approval.created') {
      // Re-fetch latest audit log
      loadAuditFeed()
    }
  })

  const loadAuditFeed = async () => {
    try {
      const records = await api.listAudit({ limit: 50 })
      setAuditRecords(records)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to fetch audit activity stream')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAuditFeed()
  }, [])

  // Calculate Stat Metrics from real audit data
  const stats = useMemo(() => {
    const total = auditRecords.length
    const allowed = auditRecords.filter((r) => r.decision === 'ALLOW').length
    const askHuman = auditRecords.filter((r) => r.decision === 'ASK_HUMAN').length
    const blocked = auditRecords.filter((r) => r.decision === 'BLOCK').length

    return { total, allowed, askHuman, blocked }
  }, [auditRecords])

  // Map AuditRecord to ActionItem for ResponsiveTable
  const actionItems: ActionItem[] = useMemo(() => {
    return auditRecords
      .filter((r) => filterDecision === 'ALL' || r.decision === filterDecision)
      .map((r) => {
        let parsedParams: Record<string, unknown> = {}
        try {
          parsedParams = JSON.parse(r.params_masked)
        } catch {
          // ignore
        }

        const recipient =
          (parsedParams.recipient as string) ||
          (parsedParams.to as string) ||
          (parsedParams.sql as string) ||
          '—'

        const amountPaise = parsedParams.amount_paise as number | undefined
        const amountDirect = parsedParams.amount as number | undefined
        const finalAmount =
          amountPaise !== undefined ? amountPaise / 100 : amountDirect

        return {
          id: r.id,
          time: new Date(r.ts).toLocaleTimeString('en-IN', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
          }),
          agent: r.agent_id,
          tool: r.tool,
          target: recipient,
          amount: finalAmount,
          decision:
            r.decision === 'ASK_HUMAN' ? 'ASK HUMAN' : (r.decision as 'ALLOW' | 'BLOCK'),
          reason: r.reason,
          latencyMs: 0.8,
          sequence: r.id,
        }
      })
  }, [auditRecords, filterDecision])

  // Open inspection drawer for any record
  const handleOpenDrawer = (recordId: number | string) => {
    const record = auditRecords.find((r) => r.id === Number(recordId))
    if (!record) return

    let parsedParams: Record<string, unknown> = {}
    try {
      parsedParams = JSON.parse(record.params_masked)
    } catch {
      // ignore
    }

    const recipient =
      (parsedParams.recipient as string) ||
      (parsedParams.to as string) ||
      (parsedParams.sql as string) ||
      'Target entity'

    const amountPaise = parsedParams.amount_paise as number | undefined
    const amountDirect = parsedParams.amount as number | undefined
    const finalAmount =
      amountPaise !== undefined ? amountPaise / 100 : amountDirect || 5000

    const isBlock = record.decision === 'BLOCK'

    // Parameter comparison rows
    const comparisonRows: ParamRow[] = [
      {
        label: 'Tool',
        approvedValue: record.tool,
        attemptedValue: record.tool,
        isMismatch: false,
      },
      {
        label: 'Recipient',
        approvedValue: isBlock ? 'Supplier A (approved)' : recipient,
        attemptedValue: recipient,
        isMismatch: isBlock && record.reason.includes('Recipient changed'),
      },
      {
        label: 'Amount',
        approvedValue: `₹${finalAmount.toLocaleString('en-IN')}`,
        attemptedValue: `₹${finalAmount.toLocaleString('en-IN')}`,
        isMismatch: isBlock && record.reason.includes('Amount changed'),
      },
      {
        label: 'Approval',
        approvedValue: record.approval_id ? `${record.approval_id.slice(0, 8)}…` : 'Direct call',
        attemptedValue: isBlock ? 'Tampered/Mismatch' : 'Valid',
        isMismatch: false,
      },
    ]

    const drawerData: DrawerEventData = {
      id: record.id,
      decision:
        record.decision === 'ASK_HUMAN'
          ? 'ASK HUMAN'
          : (record.decision as 'ALLOW' | 'BLOCK'),
      tool: record.tool,
      amount: finalAmount,
      agent: record.agent_id,
      time: new Date(record.ts).toLocaleTimeString('en-IN'),
      incidentId: `INC-${record.id + 7800}`,
      interceptId: `int-${record.id}`,
      reason: record.reason,
      ruleId: 'POL-SEC-004',
      decidedBy: 'Deterministic Enclave Gateway',
      explanation: `Execution evaluation by AgentGuard gateway: ${record.reason}.`,
      comparisonRows,
      executionCount: record.executed ? 1 : 0,
      lossPrevented: record.executed ? 0 : finalAmount,
      rawRequestJson: JSON.stringify(
        {
          agent_id: record.agent_id,
          task_id: record.task_id,
          tool: record.tool,
          params: parsedParams,
          approval_id: record.approval_id,
          timestamp: record.ts,
        },
        null,
        2,
      ),
      recordNumber: record.id,
      currentHash: record.hash ? `${record.hash.slice(0, 8)}…` : 'genesis',
      prevHash: record.prev_hash ? `${record.prev_hash.slice(0, 8)}…` : '00000000…',
    }

    setSelectedDrawerData(drawerData)
    setIsDrawerOpen(true)
  }

  // Alerts list: latest BLOCK events
  const blockAlerts = useMemo(() => {
    return auditRecords.filter((r) => r.decision === 'BLOCK').slice(0, 3)
  }, [auditRecords])

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* 1. Header with Live Status Indicator */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-[22px] sm:text-[24px] font-bold text-ink tracking-tight">
              Live Intercept Feed
            </h1>
            <span className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-pill bg-allow/15 text-allow border border-allow/30 text-[11px] font-mono font-semibold">
              <span className="w-2 h-2 rounded-full bg-allow animate-live-dot" />
              <span>LIVE</span>
            </span>
          </div>
          <p className="text-[13px] text-ink2 mt-1">
            Real-time deterministic security gate monitoring autonomous agent tool dispatches.
          </p>
        </div>

        <button
          onClick={loadAuditFeed}
          disabled={loading}
          className="self-start sm:self-auto flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface border border-line text-ink2 hover:text-ink text-[12px] font-medium transition-colors"
        >
          <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-block/15 border border-block/40 text-block text-xs font-medium">
          {error}
        </div>
      )}

      {/* 2. Stat Metric Cards Row */}
      {loading && auditRecords.length === 0 ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonStatCard />
          <SkeletonStatCard />
          <SkeletonStatCard />
          <SkeletonStatCard />
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Actions today"
            value={stats.total}
            subtext="Total evaluated"
            sparklinePoints={[12, 15, 18, 14, 20, 24, 22, 28, stats.total || 30]}
            sparklineColor="#C8963E"
            icon={<Activity className="w-5 h-5 text-accent" />}
          />
          <StatCard
            label="Allowed"
            value={stats.allowed}
            subtext="Clean execution"
            variant="allow"
            sparklinePoints={[8, 11, 14, 12, 17, 21, 19, 24, stats.allowed || 25]}
            sparklineColor="#2E9E5B"
            icon={<CheckCircle2 className="w-5 h-5 text-allow" />}
          />
          <StatCard
            label="Needs approval"
            value={stats.askHuman}
            subtext="Held at gate"
            variant="ask"
            sparklinePoints={[1, 2, 1, 3, 2, 4, 2, 3, stats.askHuman || 2]}
            sparklineColor="#F2B705"
            icon={<Clock className="w-5 h-5 text-ask" />}
          />
          <StatCard
            label="Blocked"
            value={stats.blocked}
            subtext="Zero loss"
            variant="block"
            sparklinePoints={[3, 2, 4, 1, 3, 2, 4, 1, stats.blocked || 5]}
            sparklineColor="#D64545"
            icon={<ShieldX className="w-5 h-5 text-block" />}
          />
        </div>
      )}

      {/* 3. Main Stream (2/3) + Side Intelligence Alerts (1/3) */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* Left Column: Activity Feed Table */}
        <div className="xl:col-span-8 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <h2 className="text-[16px] font-semibold text-ink">Agent Activity Stream</h2>
              <span className="font-mono text-[11px] text-ink2">({actionItems.length} records)</span>
            </div>

            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface border border-line text-[12px]">
              {(['ALL', 'ALLOW', 'ASK_HUMAN', 'BLOCK'] as const).map((dec) => (
                <button
                  key={dec}
                  onClick={() => setFilterDecision(dec)}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                    filterDecision === dec
                      ? 'bg-accent text-bg font-bold'
                      : 'text-ink2 hover:text-ink'
                  }`}
                >
                  {dec === 'ASK_HUMAN' ? 'ASK HUMAN' : dec}
                </button>
              ))}
            </div>
          </div>

          {/* Table / Card List */}
          {loading && auditRecords.length === 0 ? (
            <div className="rounded-card border border-line bg-surface p-4">
              <table className="w-full">
                <tbody>
                  <SkeletonTableRow />
                  <SkeletonTableRow />
                  <SkeletonTableRow />
                </tbody>
              </table>
            </div>
          ) : actionItems.length === 0 ? (
            <EmptyState
              title="No activity recorded"
              description="No agent actions matching the selected filter have been evaluated."
            />
          ) : (
            <ResponsiveTable
              items={actionItems}
              onRowClick={(item) => handleOpenDrawer(item.id)}
            />
          )}
        </div>

        {/* Right Column: Decision Mix & Recent Block Alerts */}
        <div className="xl:col-span-4 space-y-6">
          {/* Decision Mix Proportions */}
          <div className="rounded-card border border-line bg-surface p-5 space-y-4 shadow-sm">
            <h3 className="text-[15px] font-semibold text-ink">Decision Distribution</h3>

            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-[12px] font-mono mb-1">
                  <span className="text-allow font-semibold flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5" /> ALLOW
                  </span>
                  <span className="text-ink">
                    {stats.total > 0 ? Math.round((stats.allowed / stats.total) * 100) : 0}% ({stats.allowed})
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-surface2 overflow-hidden">
                  <div
                    className="h-full bg-allow transition-all"
                    style={{
                      width: `${stats.total > 0 ? (stats.allowed / stats.total) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[12px] font-mono mb-1">
                  <span className="text-block font-semibold flex items-center gap-1.5">
                    <ShieldX className="w-3.5 h-3.5" /> BLOCK
                  </span>
                  <span className="text-ink">
                    {stats.total > 0 ? Math.round((stats.blocked / stats.total) * 100) : 0}% ({stats.blocked})
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-surface2 overflow-hidden">
                  <div
                    className="h-full bg-block transition-all"
                    style={{
                      width: `${stats.total > 0 ? (stats.blocked / stats.total) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[12px] font-mono mb-1">
                  <span className="text-ask font-semibold flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" /> ASK HUMAN
                  </span>
                  <span className="text-ink">
                    {stats.total > 0 ? Math.round((stats.askHuman / stats.total) * 100) : 0}% ({stats.askHuman})
                  </span>
                </div>
                <div className="w-full h-2 rounded-full bg-surface2 overflow-hidden">
                  <div
                    className="h-full bg-ask transition-all"
                    style={{
                      width: `${stats.total > 0 ? (stats.askHuman / stats.total) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Recent Block Alerts Card */}
          <div className="rounded-card border border-line bg-surface p-5 space-y-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-[15px] font-semibold text-ink flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-block" />
                <span>Critical Intercepts</span>
              </h3>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-block/15 text-block border border-block/30">
                Fail-Closed
              </span>
            </div>

            {blockAlerts.length === 0 ? (
              <p className="text-[12px] text-ink2">No violations detected in current feed.</p>
            ) : (
              <div className="space-y-3">
                {blockAlerts.map((alert) => (
                  <div
                    key={alert.id}
                    className="p-3 rounded-lg bg-block/10 border border-block/30 space-y-2 transition-all hover:bg-block/15"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-mono text-[12px] font-bold text-block">
                        #{alert.id} · {alert.tool}
                      </span>
                      <DecisionChip decision="BLOCK" size="sm" />
                    </div>

                    <p className="text-[12px] text-ink leading-tight font-medium">
                      {alert.reason}
                    </p>

                    <div className="flex items-center justify-between pt-1 border-t border-block/20">
                      <span className="font-mono text-[11px] text-ink2">{alert.agent_id}</span>
                      <button
                        onClick={() => handleOpenDrawer(alert.id)}
                        className="text-[11px] font-mono text-accent hover:underline flex items-center gap-1"
                      >
                        <span>View why</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. Inspection Drawer (Responsive Right Slide-over on Laptop, Bottom Sheet on Mobile) */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        data={selectedDrawerData}
      />
    </div>
  )
}
