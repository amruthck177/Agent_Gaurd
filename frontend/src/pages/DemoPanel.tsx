import React, { useState, useCallback, useRef } from 'react'
import {
  Play,
  RotateCcw,
  ShieldAlert,
  ShieldCheck,
  Flame,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Database,
  UserX,
  Timer,
  Ban,
  RefreshCw,
  WifiOff,
  Repeat,
  DollarSign,
  Zap,
  Pause,
} from 'lucide-react'
import { api, ScenarioResult, ScenarioParamRow } from '../lib/api'
import { DecisionChip } from '../components/common/DecisionChip'
import { useEvents, WsEvent, GatewayDecisionEventData } from '../lib/useEvents'

/* ─── Scenario Definitions ──────────────────────────────────────────── */

interface ScenarioDef {
  id: string
  num: number | string
  title: string
  subtitle: string
  icon: React.ElementType
  expectedDecision: 'ALLOW' | 'ASK_HUMAN' | 'BLOCK'
  storyStep?: number  // 1-8 for the "full story" sequence
}

const SCENARIOS: ScenarioDef[] = [
  {
    id: 'run1', num: 1, title: 'Valid approved payment',
    subtitle: 'Supplier A ₹5,000 — exact params match',
    icon: CheckCircle2, expectedDecision: 'ALLOW', storyStep: 1,
  },
  {
    id: 'run2', num: 2, title: 'Supplier A approved, Supplier B attempted',
    subtitle: 'Recipient swapped after approval',
    icon: ShieldAlert, expectedDecision: 'BLOCK', storyStep: 2,
  },
  {
    id: 'run3', num: 3, title: 'Amount changed',
    subtitle: '₹5,000 approved → ₹50,000 attempted',
    icon: DollarSign, expectedDecision: 'BLOCK', storyStep: 3,
  },
  {
    id: 'run4', num: 4, title: 'Expired',
    subtitle: 'Token used after TTL expired',
    icon: Timer, expectedDecision: 'BLOCK', storyStep: 4,
  },
  {
    id: 'run5', num: 5, title: 'Revoked',
    subtitle: 'Approval revoked before execution',
    icon: Ban, expectedDecision: 'BLOCK', storyStep: 5,
  },
  {
    id: 'run6', num: 6, title: 'Read-only agent write',
    subtitle: 'Reader agent attempts payments.send',
    icon: UserX, expectedDecision: 'BLOCK', storyStep: 6,
  },
  {
    id: 'run7', num: 7, title: 'DROP TABLE',
    subtitle: 'Destructive SQL blocked by policy',
    icon: Database, expectedDecision: 'BLOCK', storyStep: 7,
  },
  {
    id: 'run8', num: 8, title: 'Payment above ₹10,000',
    subtitle: '₹80,000 triggers ASK HUMAN policy',
    icon: AlertTriangle, expectedDecision: 'ASK_HUMAN', storyStep: 8,
  },
]

const EXTRA_SCENARIOS: ScenarioDef[] = [
  {
    id: 'replay', num: 'R', title: 'Replay',
    subtitle: 'Reuse a consumed single-use token',
    icon: Repeat, expectedDecision: 'BLOCK',
  },
  {
    id: 'gateway_down', num: 'G', title: 'Gateway down',
    subtitle: 'Simulated failure → fail closed',
    icon: WifiOff, expectedDecision: 'BLOCK',
  },
]

/* ─── Story Step Captions (design.md §7) ────────────────────────── */

const STORY_CAPTIONS = [
  '1/8 — Setup: Reset demo data to genesis',
  '2/8 — Valid payment: Supplier A ₹5,000 approved & executed',
  '3/8 — Attack: Supplier B attempted with Supplier A\'s token',
  '4/8 — Amount tamper: ₹5,000 → ₹50,000',
  '5/8 — Expired token: TTL bypass attempt',
  '6/8 — Revoked: Approval withdrawn',
  '7/8 — Privilege escalation: Read-only agent writes',
  '8/8 — Destructive SQL: DROP TABLE blocked',
]

/* ─── Mini Result Card ──────────────────────────────────────────── */

interface ScenarioCardResultProps {
  result: ScenarioResult
}

const ScenarioCardResult: React.FC<ScenarioCardResultProps> = ({ result }) => {
  const decision = (result.decision || 'BLOCK') as 'ALLOW' | 'ASK_HUMAN' | 'BLOCK'
  return (
    <div className="mt-3 pt-3 border-t border-line/60 space-y-2.5 animate-fade-in">
      {/* Decision + Reason */}
      <div className="flex items-center justify-between gap-2">
        <DecisionChip decision={decision} size="sm" />
        <span className="text-[11px] text-ink2 text-right truncate flex-1 font-mono">
          {result.reason}
        </span>
      </div>

      {/* Param Compare Mini Table */}
      {result.params_compare && result.params_compare.length > 0 && (
        <div className="rounded-lg border border-line bg-surface overflow-hidden text-xs">
          <div className="grid grid-cols-3 gap-px bg-line">
            <div className="px-2 py-1.5 bg-surface2 font-mono font-semibold text-ink2 text-[10px] uppercase">Field</div>
            <div className="px-2 py-1.5 bg-surface2 font-mono font-semibold text-ink2 text-[10px] uppercase">Approved</div>
            <div className="px-2 py-1.5 bg-surface2 font-mono font-semibold text-ink2 text-[10px] uppercase">Attempted</div>
          </div>
          {result.params_compare.map((row: ScenarioParamRow, idx: number) => (
            <div
              key={idx}
              className={`grid grid-cols-3 gap-px ${
                row.mismatch ? 'bg-block/20' : 'bg-line/50'
              }`}
            >
              <div className={`px-2 py-1.5 bg-surface text-ink2 font-mono ${
                row.mismatch ? 'border-l-2 border-block' : ''
              }`}>
                {row.label}
              </div>
              <div className="px-2 py-1.5 bg-surface text-ink font-mono">{row.approved}</div>
              <div className={`px-2 py-1.5 bg-surface font-mono ${
                row.mismatch ? 'text-block font-bold' : 'text-ink'
              }`}>
                {row.attempted}
                {row.mismatch && <span className="ml-1 text-block">✗</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tool execution count */}
      <div className="flex items-center justify-between text-[11px] font-mono">
        <span className="text-ink2">Tool executions:</span>
        <span className={`font-bold ${
          result.tool_executions && result.tool_executions > 0 ? 'text-allow' : 'text-block'
        }`}>
          {result.tool_executions ?? 0}
        </span>
      </div>
    </div>
  )
}

/* ─── Mini Live Feed (last 3 decisions) ──────────────────────── */

interface LiveDecision {
  id: string
  tool: string
  decision: string
  reason: string
  ts: Date
}

const MiniLiveFeed: React.FC<{ decisions: LiveDecision[] }> = ({ decisions }) => (
  <div className="rounded-xl border border-line bg-surface overflow-hidden shadow-sm">
    <div className="px-4 py-2.5 bg-surface2/80 border-b border-line flex items-center justify-between">
      <div className="flex items-center gap-2 text-xs font-mono text-ink2">
        <Zap className="w-3.5 h-3.5 text-accent" />
        <span>LIVE FEED</span>
      </div>
      <span className="text-[10px] text-allow font-mono">● LIVE</span>
    </div>
    <div className="divide-y divide-line/50">
      {decisions.length === 0 ? (
        <div className="p-4 text-center text-xs text-ink2 font-mono">
          No decisions yet. Run a scenario to begin.
        </div>
      ) : (
        decisions.map((d) => (
          <div key={d.id} className="px-4 py-2.5 flex items-center gap-3 animate-fade-in">
            <DecisionChip
              decision={d.decision as 'ALLOW' | 'ASK_HUMAN' | 'BLOCK'}
              size="sm"
            />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-mono text-ink truncate">{d.tool}</div>
              <div className="text-[10px] text-ink2 truncate">{d.reason}</div>
            </div>
            <span className="text-[10px] font-mono text-ink2 shrink-0">
              {d.ts.toLocaleTimeString()}
            </span>
          </div>
        ))
      )}
    </div>
  </div>
)

/* ─── Main DemoPanel ────────────────────────────────────────────── */

export const DemoPanel: React.FC = () => {
  const [results, setResults] = useState<Record<string, ScenarioResult>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [expanded, setExpanded] = useState<string | null>(null)
  const [isRunningStory, setIsRunningStory] = useState(false)
  const [storyCaption, setStoryCaption] = useState('')
  const [storyStep, setStoryStep] = useState(0)
  const [liveDecisions, setLiveDecisions] = useState<LiveDecision[]>([])
  const [verifyResult, setVerifyResult] = useState<{ ok: boolean; checked: number; broken_at: number | null } | null>(null)
  const [verifyLoading, setVerifyLoading] = useState(false)
  const abortRef = useRef(false)

  // WebSocket: capture gateway decisions for the mini live feed
  useEvents(useCallback((event: WsEvent) => {
    if (event.type === 'gateway.decision' && event.data) {
      const d = event.data as GatewayDecisionEventData
      setLiveDecisions((prev) => [
        {
          id: `${Date.now()}-${Math.random()}`,
          tool: d.tool,
          decision: d.decision,
          reason: d.reason,
          ts: new Date(),
        },
        ...prev,
      ].slice(0, 3))
    }
  }, []))

  /* ─── Run a single scenario ──── */
  const runScenario = async (scenarioId: string) => {
    setLoading((prev) => ({ ...prev, [scenarioId]: true }))
    try {
      const res = await api.runScenario(scenarioId)
      setResults((prev) => ({ ...prev, [scenarioId]: res }))
      setExpanded(scenarioId)
    } catch (err) {
      setResults((prev) => ({
        ...prev,
        [scenarioId]: {
          scenario: scenarioId,
          decision: 'BLOCK',
          reason: err instanceof Error ? err.message : 'Failed',
          executed: false,
          tool_executions: 0,
        },
      }))
      setExpanded(scenarioId)
    } finally {
      setLoading((prev) => ({ ...prev, [scenarioId]: false }))
    }
  }

  /* ─── Run the full story (design.md §7, 8 steps, 1.5s pauses) ──── */
  const runFullStory = async () => {
    if (isRunningStory) {
      abortRef.current = true
      return
    }
    abortRef.current = false
    setIsRunningStory(true)
    setStoryStep(0)
    setVerifyResult(null)

    // Step 0: Reset
    setStoryCaption('0/8 — Resetting demo data...')
    try { await api.resetDemo() } catch { /* ignore */ }
    setResults({})
    setLiveDecisions([])

    await new Promise((r) => setTimeout(r, 1000))

    // Steps 1-8
    for (let i = 0; i < SCENARIOS.length; i++) {
      if (abortRef.current) break
      const sc = SCENARIOS[i]
      setStoryStep(i + 1)
      setStoryCaption(STORY_CAPTIONS[i])
      setExpanded(sc.id)

      setLoading((prev) => ({ ...prev, [sc.id]: true }))
      try {
        const res = await api.runScenario(sc.id)
        setResults((prev) => ({ ...prev, [sc.id]: res }))
      } catch { /* logged in mini feed */ }
      setLoading((prev) => ({ ...prev, [sc.id]: false }))

      if (i < SCENARIOS.length - 1) {
        await new Promise((r) => setTimeout(r, 1500))
      }
    }

    setStoryCaption(abortRef.current ? 'Story cancelled.' : '✓ Full story complete — all 8 scenarios demonstrated.')
    setIsRunningStory(false)
    setStoryStep(0)
  }

  /* ─── Utility handlers ──── */
  const handleReset = async () => {
    setLoading((prev) => ({ ...prev, reset: true }))
    try {
      await api.resetDemo()
      setResults({})
      setExpanded(null)
      setLiveDecisions([])
      setVerifyResult(null)
    } catch { /* ignore */ }
    setLoading((prev) => ({ ...prev, reset: false }))
  }

  const handleTamper = async () => {
    setLoading((prev) => ({ ...prev, tamper: true }))
    try {
      await api.tamperDemo()
      setVerifyResult(null) // force re-verify
    } catch { /* ignore */ }
    setLoading((prev) => ({ ...prev, tamper: false }))
  }

  const handleVerify = async () => {
    setVerifyLoading(true)
    try {
      const v = await api.verifyAudit()
      setVerifyResult(v)
    } catch { /* ignore */ }
    setVerifyLoading(false)
  }

  /* ─── Render ──────────────────────────────────────────────────── */

  const renderScenarioCard = (sc: ScenarioDef) => {
    const isExpanded = expanded === sc.id
    const isLoading = loading[sc.id]
    const result = results[sc.id]
    const isStoryActive = isRunningStory && storyStep === sc.storyStep
    const Icon = sc.icon

    const decColor =
      sc.expectedDecision === 'ALLOW' ? 'allow'
        : sc.expectedDecision === 'ASK_HUMAN' ? 'ask'
          : 'block'

    return (
      <div
        key={sc.id}
        className={`rounded-xl border transition-all cursor-pointer overflow-hidden ${
          isStoryActive
            ? 'border-accent ring-2 ring-accent/40 bg-surface2/90 shadow-lg'
            : isExpanded
              ? 'border-accent/60 bg-surface2/70 shadow-md'
              : 'border-line bg-surface hover:bg-surface2/50 hover:border-line/80'
        }`}
        onClick={() => !isRunningStory && setExpanded(isExpanded ? null : sc.id)}
      >
        <div className="p-4 sm:p-5 flex items-center gap-3 sm:gap-4">
          {/* Number badge */}
          <div
            className={`w-10 h-10 sm:w-11 sm:h-11 rounded-xl flex items-center justify-center font-mono text-sm font-bold shrink-0 ${
              isStoryActive
                ? 'bg-accent text-bg'
                : isExpanded
                  ? 'bg-accent/20 text-accent border border-accent/30'
                  : 'bg-surface2 text-ink2 border border-line'
            }`}
          >
            {sc.num}
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Icon className={`w-4 h-4 shrink-0 text-${decColor}`} />
              <h3 className="font-bold text-[15px] sm:text-base text-ink truncate">
                {sc.title}
              </h3>
            </div>
            <p className="text-xs sm:text-sm text-ink2 mt-0.5 truncate">{sc.subtitle}</p>
          </div>

          {/* Expected decision badge */}
          <span
            className={`px-2.5 py-1 rounded-lg text-[10px] sm:text-xs font-mono font-bold uppercase shrink-0 ${
              decColor === 'allow'
                ? 'bg-allow/15 text-allow border border-allow/30'
                : decColor === 'ask'
                  ? 'bg-ask/15 text-ask border border-ask/30'
                  : 'bg-block/15 text-block border border-block/30'
            }`}
          >
            {sc.expectedDecision.replace('_', ' ')}
          </span>
        </div>

        {/* Expanded: Run button + result */}
        {isExpanded && (
          <div className="px-4 sm:px-5 pb-4 sm:pb-5 space-y-3">
            <button
              onClick={(e) => {
                e.stopPropagation()
                runScenario(sc.id)
              }}
              disabled={isLoading || isRunningStory}
              className="w-full h-12 sm:h-14 rounded-xl bg-accent text-bg hover:bg-accent/90 font-bold text-sm flex items-center justify-center gap-2 transition-all active:scale-[0.98] disabled:opacity-50 shadow-md shadow-accent/20"
            >
              {isLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              <span>{isLoading ? 'Running...' : `Run ${sc.title}`}</span>
            </button>

            {result && <ScenarioCardResult result={result} />}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-32 sm:pb-12 max-w-7xl mx-auto">
      {/* ─── Header: Projector-sized ──────────────────────────────── */}
      <div className="rounded-2xl border border-line bg-surface p-5 sm:p-8 flex flex-col lg:flex-row lg:items-center justify-between gap-5 shadow-sm">
        <div className="space-y-2">
          {/* Status pill */}
          <div className="flex items-center gap-2.5">
            <span className="w-3 h-3 rounded-full bg-accent animate-pulse" />
            <span className="text-xs sm:text-sm font-mono font-semibold px-3 py-1 rounded-lg bg-surface2 border border-line text-accent uppercase tracking-wider">
              Agent mode: Scripted (offline-safe)
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-extrabold text-ink tracking-tight">
            Demo Panel
          </h1>
          <p className="text-sm sm:text-base text-ink2 max-w-2xl leading-relaxed">
            Run scripted attack and defense scenarios through the live gateway. Each card executes a real scenario and shows the decision, parameter comparison, and tool execution proof.
          </p>
        </div>

        {/* Control buttons */}
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <button
            onClick={handleReset}
            disabled={loading.reset || isRunningStory}
            className="h-12 sm:h-14 px-4 sm:px-5 rounded-xl border border-line hover:border-ink2 bg-surface2 text-ink font-semibold text-xs sm:text-sm flex items-center gap-2 transition-all active:scale-95 disabled:opacity-50"
          >
            <RotateCcw className={`w-4 h-4 text-ink2 ${loading.reset ? 'animate-spin' : ''}`} />
            <span>Reset demo data</span>
          </button>

          <button
            onClick={handleTamper}
            disabled={loading.tamper || isRunningStory}
            className="h-12 sm:h-14 px-4 sm:px-5 rounded-xl border border-block/50 bg-block/15 text-block hover:bg-block/25 font-semibold text-xs sm:text-sm flex items-center gap-2 transition-all active:scale-95 disabled:opacity-50"
          >
            <Flame className={`w-4 h-4 ${loading.tamper ? 'animate-bounce' : ''}`} />
            <span>Simulate tamper</span>
          </button>

          <button
            onClick={handleVerify}
            disabled={verifyLoading || isRunningStory}
            className="h-12 sm:h-14 px-4 sm:px-5 rounded-xl border border-accent/50 bg-accent/15 text-accent hover:bg-accent/25 font-semibold text-xs sm:text-sm flex items-center gap-2 transition-all active:scale-95 disabled:opacity-50"
          >
            <ShieldCheck className={`w-4 h-4 ${verifyLoading ? 'animate-spin' : ''}`} />
            <span>Verify integrity</span>
          </button>
        </div>
      </div>

      {/* ─── Verify Result Banner ──────────────────────────────── */}
      {verifyResult && (
        <div
          className={`rounded-xl border p-4 sm:p-5 flex items-center gap-3 animate-fade-in shadow-sm ${
            verifyResult.ok
              ? 'border-allow/50 bg-allow/10 text-allow'
              : 'border-block/50 bg-block/10 text-block'
          }`}
        >
          {verifyResult.ok ? (
            <ShieldCheck className="w-6 h-6 shrink-0" />
          ) : (
            <XCircle className="w-6 h-6 shrink-0" />
          )}
          <div className="flex-1">
            <div className="font-bold text-sm sm:text-base">
              {verifyResult.ok
                ? `✓ Chain intact — ${verifyResult.checked} records verified`
                : `✗ Chain broken at record #${verifyResult.broken_at}`}
            </div>
            <div className="text-xs opacity-80 font-mono">
              SHA-256 hash chain {verifyResult.ok ? 'verified' : 'compromised'}
            </div>
          </div>
        </div>
      )}

      {/* ─── Story Caption Bar ────────────────────────────────── */}
      {(isRunningStory || storyCaption) && storyCaption && (
        <div className="rounded-xl border border-accent/40 bg-accent/10 px-4 sm:px-5 py-3 sm:py-4 flex items-center gap-3 animate-fade-in">
          {isRunningStory ? (
            <RefreshCw className="w-5 h-5 text-accent animate-spin shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-accent shrink-0" />
          )}
          <span className="text-sm sm:text-base font-semibold text-ink flex-1">
            {storyCaption}
          </span>
          {isRunningStory && (
            <div className="w-32 h-2 bg-surface2 rounded-full overflow-hidden shrink-0 hidden sm:block">
              <div
                className="h-full bg-accent rounded-full transition-all duration-500"
                style={{ width: `${(storyStep / 8) * 100}%` }}
              />
            </div>
          )}
        </div>
      )}

      {/* ─── Main Grid: Scenarios (left) + Sidebar (right) ──── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Scenario Cards */}
        <div className="lg:col-span-8 space-y-3">
          <h2 className="text-base sm:text-lg font-bold text-ink flex items-center gap-2">
            <Zap className="w-4 h-4 text-accent" />
            Scenarios
          </h2>

          <div className="space-y-2.5">
            {SCENARIOS.map(renderScenarioCard)}
          </div>

          {/* Extra scenarios (Replay + Gateway down) */}
          <h3 className="text-sm font-bold text-ink2 mt-6 flex items-center gap-2 pt-3 border-t border-line/60">
            <ShieldAlert className="w-3.5 h-3.5 text-ink2" />
            Additional Scenarios
          </h3>
          <div className="space-y-2.5">
            {EXTRA_SCENARIOS.map(renderScenarioCard)}
          </div>
        </div>

        {/* Right Sidebar: Mini Live Feed + Verify */}
        <div className="lg:col-span-4 space-y-4">
          <MiniLiveFeed decisions={liveDecisions} />

          {/* Quick Stats Summary */}
          {Object.keys(results).length > 0 && (
            <div className="rounded-xl border border-line bg-surface p-4 shadow-sm space-y-3">
              <h3 className="text-xs font-mono font-bold text-ink2 uppercase tracking-wider">
                Session Summary
              </h3>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center">
                  <div className="text-xl font-bold text-allow">
                    {Object.values(results).filter((r) => r.decision === 'ALLOW').length}
                  </div>
                  <div className="text-[10px] font-mono text-ink2">ALLOW</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-ask">
                    {Object.values(results).filter((r) => r.decision === 'ASK_HUMAN').length}
                  </div>
                  <div className="text-[10px] font-mono text-ink2">ASK</div>
                </div>
                <div className="text-center">
                  <div className="text-xl font-bold text-block">
                    {Object.values(results).filter((r) => r.decision === 'BLOCK').length}
                  </div>
                  <div className="text-[10px] font-mono text-ink2">BLOCK</div>
                </div>
              </div>
              <div className="pt-2 border-t border-line/60 text-xs font-mono text-ink2 text-center">
                Tool executions: {Object.values(results).reduce((sum, r) => sum + (r.tool_executions ?? 0), 0)}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ─── Sticky Mobile "Run the full story" Button ────────── */}
      <div className="fixed bottom-0 left-0 right-0 p-4 bg-bg/95 backdrop-blur-sm border-t border-line sm:relative sm:bottom-auto sm:left-auto sm:right-auto sm:p-0 sm:bg-transparent sm:border-0 sm:backdrop-blur-none z-40 lg:hidden">
        <button
          onClick={runFullStory}
          disabled={false}
          className="w-full h-14 rounded-2xl bg-accent text-bg hover:bg-accent/90 font-bold text-[15px] flex items-center justify-center gap-2.5 transition-all active:scale-[0.98] shadow-lg shadow-accent/30"
        >
          {isRunningStory ? (
            <>
              <Pause className="w-5 h-5" />
              <span>Stop story</span>
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              <span>Run the full story</span>
            </>
          )}
        </button>
      </div>

      {/* ─── Desktop "Run the full story" (in-flow) ──────────── */}
      <div className="hidden lg:block">
        <button
          onClick={runFullStory}
          disabled={false}
          className="w-full h-16 rounded-2xl bg-accent text-bg hover:bg-accent/90 font-extrabold text-lg flex items-center justify-center gap-3 transition-all active:scale-[0.98] shadow-lg shadow-accent/30"
        >
          {isRunningStory ? (
            <>
              <Pause className="w-6 h-6" />
              <span>Stop story</span>
            </>
          ) : (
            <>
              <Play className="w-6 h-6" />
              <span>Run the full story</span>
            </>
          )}
        </button>
      </div>
    </div>
  )
}
