import React, { useState } from 'react'
import {
  Laptop,
  Tablet,
  Smartphone,
  Shield,
  Activity,
  CheckCircle2,
  Clock,
  ShieldX,
  ExternalLink,
} from 'lucide-react'
import { DecisionChip } from '../components/common/DecisionChip'
import { StatCard } from '../components/common/StatCard'
import { ActionItem } from '../components/common/ActionRow'
import { ParamCompare, ParamRow } from '../components/common/ParamCompare'
import { ReasonLine, CanonicalReason } from '../components/common/ReasonLine'
import { ApprovalCard, ApprovalCardData } from '../components/common/ApprovalCard'
import { AuditRow, AuditRecordItem } from '../components/common/AuditRow'
import { IntegrityHero } from '../components/common/IntegrityHero'
import { Countdown } from '../components/common/Countdown'
import { SimulatedBadge } from '../components/common/SimulatedBadge'
import { EmptyState } from '../components/common/EmptyState'
import { SkeletonTableRow, SkeletonStatCard } from '../components/common/Skeleton'
import { Sidebar } from '../components/layout/Sidebar'
import { IconSidebar } from '../components/layout/IconSidebar'
import { BottomTabBar } from '../components/layout/BottomTabBar'
import { Topbar } from '../components/layout/Topbar'
import { Banner } from '../components/layout/Banner'
import { ResponsiveTable } from '../components/layout/ResponsiveTable'
import { Drawer, DrawerEventData } from '../components/layout/Drawer'

type DeviceMode = 'laptop' | 'tablet' | 'mobile'

export const Styleguide: React.FC = () => {
  const [device, setDevice] = useState<DeviceMode>('laptop')
  const [theme, setTheme] = useState<'dark' | 'light'>('dark')
  const [isDrawerOpen, setIsDrawerOpen] = useState(false)
  const [isPaused, setIsPaused] = useState(false)

  // Toggle Theme helper
  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    document.documentElement.setAttribute('data-theme', next)
  }

  // Sample Data
  const sampleActions: ActionItem[] = [
    {
      id: 1,
      time: '11:43:10',
      decision: 'ALLOW',
      agent: 'accounts-agent',
      tool: 'ledger.reconcile',
      target: 'invoice_sync_8819',
      amount: undefined,
      reason: 'Read-only ledger sync within policy bounds',
      latencyMs: 1.2,
      sequence: 1044,
    },
    {
      id: 2,
      time: '11:41:02',
      decision: 'BLOCK',
      agent: 'accounts-agent',
      tool: 'payments.send',
      target: 'Supplier B',
      amount: 5000,
      reason: 'Recipient changed after approval',
      latencyMs: 0.8,
      sequence: 1043,
    },
    {
      id: 3,
      time: '11:38:22',
      decision: 'ASK HUMAN',
      agent: 'accounts-agent',
      tool: 'payments.send',
      target: 'Supplier A',
      amount: 5000,
      reason: 'Payment exceeds ₹10,000 limit: human approval required',
      latencyMs: 2.1,
      sequence: 1042,
    },
  ]

  const mismatchParamRows: ParamRow[] = [
    { label: 'Tool', approvedValue: 'payments.send', attemptedValue: 'payments.send', isMismatch: false },
    { label: 'Recipient', approvedValue: 'Supplier A', attemptedValue: 'Supplier B', isMismatch: true },
    { label: 'Amount', approvedValue: '₹5,000', attemptedValue: '₹5,000', isMismatch: false },
    { label: 'Expiry', approvedValue: '11:42 (in 06:12)', attemptedValue: 'now 11:38 (valid)', isMismatch: false },
    { label: 'Approval', approvedValue: 'APR-0002 · unused', attemptedValue: 'Tampered target', isMismatch: false },
  ]

  const matchedParamRows: ParamRow[] = [
    { label: 'Tool', approvedValue: 'payments.send', attemptedValue: 'payments.send', isMismatch: false },
    { label: 'Recipient', approvedValue: 'Supplier A', attemptedValue: 'Supplier A', isMismatch: false },
    { label: 'Amount', approvedValue: '₹5,000', attemptedValue: '₹5,000', isMismatch: false },
    { label: 'Expiry', approvedValue: '11:42 (valid)', attemptedValue: '11:38 (valid)', isMismatch: false },
    { label: 'Approval', approvedValue: 'APR-0001 · unused', attemptedValue: 'APR-0001 · match', isMismatch: false },
  ]

  const sampleApprovalData: ApprovalCardData = {
    id: 'APR-0001',
    title: 'Payment ₹80,000 to Mehta Ice Suppliers',
    amount: 80000,
    recipient: 'Mehta Ice Suppliers (mehta-ice@hdfc)',
    tool: 'payments.send',
    state: 'pending',
    tags: ['Over ₹10,000 limit', 'New payee', 'Rule: POL-PAY-002'],
    agentId: 'accounts-agent',
    expiresInSeconds: 552,
  }

  const sampleApprovedData: ApprovalCardData = {
    id: 'APR-0002',
    title: 'Payment ₹5,000 to Supplier A',
    amount: 5000,
    recipient: 'Supplier A (supplier-a@bank)',
    tool: 'payments.send',
    state: 'approved',
    tags: ['Single-use token issued'],
    agentId: 'accounts-agent',
    used: false,
  }

  const sampleAuditRecords: AuditRecordItem[] = [
    {
      id: 1043,
      timestamp: '11:44:02',
      agent: 'accounts-agent',
      action: 'payments.send',
      decision: 'ALLOW',
      reason: 'Approved single-use token verified against exact parameters',
      decidedBy: 'Deterministic Enclave',
      currentHash: '9f3a8bc721',
      prevHash: '7b1e42804d',
      isChainBroken: false,
    },
    {
      id: 1042,
      timestamp: '11:41:02',
      agent: 'accounts-agent',
      action: 'payments.send',
      decision: 'BLOCK',
      reason: 'Recipient changed after approval (Supplier B != Supplier A)',
      decidedBy: 'Approval Check',
      currentHash: '7b1e42804d',
      prevHash: '4a99182f0c',
      isChainBroken: false,
    },
    {
      id: 812,
      timestamp: '10:15:30',
      agent: 'accounts-agent',
      action: 'payments.send',
      decision: 'BLOCK',
      reason: 'Chain broken: computed hash does not match stored block pointer',
      decidedBy: 'Gateway Verifier',
      currentHash: 'e51928fa88',
      prevHash: 'INVALID_POINTER',
      isChainBroken: true,
    },
  ]

  const sampleDrawerData: DrawerEventData = {
    id: 1043,
    decision: 'BLOCK',
    tool: 'payments.send',
    amount: 5000,
    agent: 'accounts-agent',
    time: '11:41',
    incidentId: 'INC-8821',
    interceptId: 'int-1141-b8',
    reason: 'Recipient changed after approval',
    ruleId: 'POL-SEC-004',
    decidedBy: 'Approval check (Deterministic Enclave)',
    explanation:
      'The agent received human approval APR-0002 bound cryptographically to Supplier A, but attempted execution targeting Supplier B.',
    comparisonRows: mismatchParamRows,
    executionCount: 0,
    lossPrevented: 5000,
    rawRequestJson: JSON.stringify(
      {
        action: 'payments.send',
        agent_id: 'accounts-agent',
        approval_token: 'apr-0002-sk-••••3F2A',
        parameters: {
          recipient: 'Supplier B',
          amount: 5000,
          currency: 'INR',
          source_account: 'acct_ops_01',
        },
        timestamp: '2026-10-12T11:41:02.104Z',
      },
      null,
      2,
    ),
    recordNumber: 1043,
    currentHash: '9f3a8b…c21d',
    prevHash: '7b1e42…04d8',
  }

  const reasonsList: CanonicalReason[] = [
    'Recipient changed after approval',
    'Amount changed after approval',
    'Approval expired',
    'Approval revoked',
    'Approval already used (replay)',
    'Agent lacks write permission',
    'Destructive database operation prohibited',
    'Payment exceeds ₹10,000 limit: human approval required',
    'Gateway unavailable: failed closed',
  ]

  // Viewport Container Widths
  const deviceWidthClasses = {
    laptop: 'max-w-[1440px] w-full',
    tablet: 'max-w-[1024px] w-full',
    mobile: 'max-w-[390px] w-full',
  }

  return (
    <div className="min-h-screen bg-bg text-ink flex flex-col font-sans">
      {/* 1. Global Styleguide Header & Device Switcher Bar */}
      <header className="sticky top-0 z-40 bg-surface/95 backdrop-blur border-b border-line px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-4 shadow-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-accent/20 border border-accent/40 flex items-center justify-center text-accent">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-[16px] font-bold text-accent tracking-tight leading-none">
              AgentGuard Component Styleguide
            </h1>
            <p className="text-[11px] font-mono text-ink2 mt-0.5">
              Interactive Design System Validator (design.md & Stitch Export)
            </p>
          </div>
        </div>

        {/* Device Mode Switcher */}
        <div className="flex items-center gap-1.5 p-1 rounded-lg bg-surface2 border border-line">
          <button
            onClick={() => setDevice('laptop')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
              device === 'laptop'
                ? 'bg-accent text-bg font-bold shadow-sm'
                : 'text-ink2 hover:text-ink'
            }`}
          >
            <Laptop className="w-4 h-4" />
            <span>Laptop (1440)</span>
          </button>

          <button
            onClick={() => setDevice('tablet')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
              device === 'tablet'
                ? 'bg-accent text-bg font-bold shadow-sm'
                : 'text-ink2 hover:text-ink'
            }`}
          >
            <Tablet className="w-4 h-4" />
            <span>Tablet (1024)</span>
          </button>

          <button
            onClick={() => setDevice('mobile')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium transition-all ${
              device === 'mobile'
                ? 'bg-accent text-bg font-bold shadow-sm'
                : 'text-ink2 hover:text-ink'
            }`}
          >
            <Smartphone className="w-4 h-4" />
            <span>Mobile (390)</span>
          </button>
        </div>

        {/* Auxiliary Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsDrawerOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-accent/40 bg-accent/15 text-accent text-[12px] font-semibold hover:bg-accent/25 transition-all"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>Open Inspection Drawer</span>
          </button>

          <button
            onClick={toggleTheme}
            className="px-2.5 py-1.5 rounded-lg border border-line bg-surface2 text-ink2 hover:text-ink text-[12px] font-mono"
          >
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      {/* 2. Device Viewport Frame Wrapper */}
      <div className="flex-1 flex justify-center p-3 sm:p-6 lg:p-8 bg-black/40 overflow-x-auto">
        <div
          className={`bg-bg border border-line rounded-xl shadow-2xl transition-all duration-300 flex flex-col overflow-hidden min-h-[90vh] ${deviceWidthClasses[device]}`}
        >
          {/* Top Banner */}
          <Banner />

          {/* Topbar */}
          <Topbar
            isPaused={isPaused}
            onPauseAgent={() => setIsPaused(!isPaused)}
            gatewayStatus="online"
            latencyMs={0.4}
          />

          <div className="flex-1 flex min-w-0">
            {/* Sidebar conditioned on Device view */}
            {device === 'laptop' && <Sidebar currentPath="/styleguide" />}
            {device === 'tablet' && <IconSidebar currentPath="/styleguide" />}

            {/* Main Content Area */}
            <main className="flex-1 p-4 sm:p-6 lg:p-8 space-y-10 overflow-y-auto">
              {/* SECTION: DECISION CHIPS */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">1. Decision Chips (Fixed Labels & Icons)</h2>
                  <span className="text-[11px] font-mono text-ink2">ALLOW · ASK HUMAN · BLOCK</span>
                </div>
                <div className="flex flex-wrap items-center gap-4 p-4 rounded-lg bg-surface border border-line">
                  <DecisionChip decision="ALLOW" />
                  <DecisionChip decision="ASK HUMAN" />
                  <DecisionChip decision="BLOCK" />
                  <div className="h-6 w-px bg-line mx-2" />
                  <DecisionChip decision="ALLOW" size="sm" />
                  <DecisionChip decision="ASK HUMAN" size="sm" />
                  <DecisionChip decision="BLOCK" size="sm" />
                </div>
              </section>

              {/* SECTION: STAT CARDS */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">2. Stat Cards (32px Tabular Figures & Sparkline)</h2>
                  <span className="text-[11px] font-mono text-ink2">8px Grid · 12px Radius</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  <StatCard
                    label="Actions today"
                    value={142}
                    subtext="Total past 24h"
                    sparklinePoints={[18, 17, 12, 15, 8, 13, 7, 9, 4]}
                    sparklineColor="#C8963E"
                    icon={<Activity className="w-5 h-5 text-accent" />}
                  />
                  <StatCard
                    label="Allowed"
                    value={128}
                    subtext="90.1% approved"
                    variant="allow"
                    sparklinePoints={[10, 12, 14, 15, 18, 20, 22, 24, 25]}
                    sparklineColor="#2E9E5B"
                    icon={<CheckCircle2 className="w-5 h-5 text-allow" />}
                  />
                  <StatCard
                    label="Needs approval"
                    value={3}
                    subtext="Held at gate"
                    variant="ask"
                    sparklinePoints={[1, 3, 2, 4, 3, 2, 4, 2, 3]}
                    sparklineColor="#F2B705"
                    icon={<Clock className="w-5 h-5 text-ask" />}
                  />
                  <StatCard
                    label="Blocked"
                    value={11}
                    subtext="Violations prevented"
                    variant="block"
                    sparklinePoints={[2, 1, 3, 0, 2, 4, 1, 2, 1]}
                    sparklineColor="#D64545"
                    icon={<ShieldX className="w-5 h-5 text-block" />}
                  />
                </div>
              </section>

              {/* SECTION: PARAMETER COMPARISON (HERO COMPONENT) */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">
                    3. Parameter Comparison Block (Hero Component)
                  </h2>
                  <span className="text-[11px] font-mono text-ink2">
                    Approved vs Attempted · Red MISMATCH · Execution Count Proof
                  </span>
                </div>

                <div className="space-y-4">
                  <div>
                    <h3 className="text-[13px] font-mono text-ink2 mb-2 uppercase">
                      A. Mismatch Violation (Supplier A → Supplier B)
                    </h3>
                    <ParamCompare
                      approvalId="APR-0002"
                      rows={mismatchParamRows}
                      executionCount={0}
                      isStacked={device === 'mobile'}
                    />
                  </div>

                  <div>
                    <h3 className="text-[13px] font-mono text-ink2 mb-2 uppercase">
                      B. Exact Match Execution (Legitimate Payment)
                    </h3>
                    <ParamCompare
                      approvalId="APR-0001"
                      rows={matchedParamRows}
                      executionCount={1}
                      isStacked={device === 'mobile'}
                      subtext="Tool executed cleanly: exact parameters matched cryptographically."
                    />
                  </div>
                </div>
              </section>

              {/* SECTION: ACTION ROWS & RESPONSIVE TABLE */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">
                    4. Responsive Action Table (Table on Desktop · Cards on Mobile)
                  </h2>
                  <span className="text-[11px] font-mono text-ink2">52px Rows · 2px Left Border</span>
                </div>
                <ResponsiveTable
                  items={sampleActions}
                  selectedId={2}
                  onRowClick={() => setIsDrawerOpen(true)}
                  isMobileCardList={device === 'mobile'}
                />
              </section>

              {/* SECTION: REASON LINES */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">
                    5. Fixed Canonical Reason Vocabulary (design.md §4.5)
                  </h2>
                  <span className="text-[11px] font-mono text-ink2">Fixed strings & rule mapping</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4 rounded-card bg-surface border border-line">
                  {reasonsList.map((reason, idx) => (
                    <div key={idx} className="p-2.5 rounded bg-surface2/60 border border-line/60">
                      <ReasonLine
                        reason={reason}
                        ruleId={`POL-00${idx + 1}`}
                        decidedBy="Gateway Rule Engine"
                      />
                    </div>
                  ))}
                </div>
              </section>

              {/* SECTION: APPROVAL CARDS */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">
                    6. Human Approval Cards & Live Countdowns
                  </h2>
                  <span className="text-[11px] font-mono text-ink2">Single-Use Token Lifecycle</span>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <ApprovalCard
                    data={sampleApprovalData}
                    onApprove={(id) => alert(`Approved ${id}`)}
                    onReject={(id) => alert(`Rejected ${id}`)}
                  />
                  <ApprovalCard
                    data={sampleApprovedData}
                    onRevoke={(id) => alert(`Revoked ${id}`)}
                  />
                </div>
              </section>

              {/* SECTION: AUDIT ROW & INTEGRITY HERO */}
              <section className="space-y-4">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">
                    7. Cryptographic Ledger & Chain Integrity
                  </h2>
                  <span className="text-[11px] font-mono text-ink2">
                    Verified vs Broken Alert States
                  </span>
                </div>

                {/* Integrity Hero Dual Variants */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <IntegrityHero
                    status="verified"
                    recordCount={1043}
                    headHash="9f3a8bc721…d84e"
                    genesisHash="00000a417b…c92f"
                    onVerify={() => alert('Chain verification completed: 1,043 intact')}
                    onExportCsv={() => alert('Exporting audit ledger CSV')}
                  />
                  <IntegrityHero
                    status="broken"
                    recordCount={1043}
                    brokenRecordId={812}
                    headHash="e51928fa88…01d2"
                    genesisHash="00000a417b…c92f"
                    onVerify={() => alert('Forensic scan detected tamper')}
                    onExportCsv={() => alert('Exporting forensic report')}
                  />
                </div>

                {/* Audit Table with Chain Connector */}
                <div className="rounded-card border border-line bg-surface overflow-hidden">
                  <div className="p-3 bg-surface2/60 border-b border-line text-[12px] font-mono text-ink2 flex items-center justify-between">
                    <span>Cryptographic Ledger Records (Connecting Prev-Hash Anchor)</span>
                    <span className="text-accent font-semibold">Merkle SHA-256</span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="bg-surface2/40 border-b border-line text-[11px] font-mono text-ink2 uppercase tracking-wider">
                          <th className="py-2.5 px-4">Record</th>
                          <th className="py-2.5 px-3">Time</th>
                          <th className="py-2.5 px-3">Agent</th>
                          <th className="py-2.5 px-3">Action</th>
                          <th className="py-2.5 px-3">Decision</th>
                          <th className="py-2.5 px-3">Reason</th>
                          <th className="py-2.5 px-3 hidden md:table-cell">Decided By</th>
                          <th className="py-2.5 px-3 text-center">Hash</th>
                          <th className="py-2.5 px-3 text-center">Prev Hash</th>
                          <th className="py-2.5 px-3 text-right pr-4">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sampleAuditRecords.map((rec, idx) => (
                          <AuditRow
                            key={rec.id}
                            record={rec}
                            isLast={idx === sampleAuditRecords.length - 1}
                            onInspect={() => setIsDrawerOpen(true)}
                            onCopyHash={(h) => navigator.clipboard.writeText(h)}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </section>

              {/* SECTION: EMPTY STATES & SKELETONS */}
              <section className="space-y-3">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">8. Empty, Loading & Edge States</h2>
                  <span className="text-[11px] font-mono text-ink2">No blank screens (design.md §4.9)</span>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <EmptyState />
                  <div className="space-y-4">
                    <SkeletonStatCard />
                    <div className="rounded-card border border-line bg-surface p-4">
                      <table className="w-full">
                        <tbody>
                          <SkeletonTableRow />
                          <SkeletonTableRow />
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </section>

              {/* SECTION: COUNTDOWN & BADGES */}
              <section className="space-y-3 pb-12">
                <div className="border-b border-line pb-2 flex items-baseline justify-between">
                  <h2 className="text-[17px] font-bold text-accent">9. Countdown Timers & Compliance Badges</h2>
                  <span className="text-[11px] font-mono text-ink2">Honest Labelling</span>
                </div>
                <div className="flex flex-wrap items-center gap-4 p-4 rounded-card bg-surface border border-line">
                  <Countdown initialSeconds={600} />
                  <Countdown initialSeconds={0} />
                  <div className="h-6 w-px bg-line" />
                  <SimulatedBadge variant="pill" />
                  <SimulatedBadge variant="pill" label="Simulated chat" />
                </div>
              </section>
            </main>
          </div>

          {/* Mobile Bottom Tab Bar */}
          {device === 'mobile' && <BottomTabBar currentPath="/styleguide" />}
        </div>
      </div>

      {/* Slide-over Inspection Drawer / Bottom Sheet */}
      <Drawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        data={sampleDrawerData}
        onPauseAgent={() => setIsPaused(!isPaused)}
        isMobileSheet={device === 'mobile'}
      />
    </div>
  )
}
