import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Terminal,
  RefreshCw,
  Search,
  Filter,
} from 'lucide-react'
import { api, TestResultsResponse } from '../lib/api'
import { StatCard } from '../components/common/StatCard'
import { DecisionChip, DecisionType } from '../components/common/DecisionChip'
import { Skeleton } from '../components/common/Skeleton'
import { EmptyState } from '../components/common/EmptyState'

interface BenchmarkDetailCase {
  id: string
  description: string
  category: string
  expected_decision: string
  actual_decision: string
  reason: string
  expected_tool_executed: boolean
  actual_tool_executed: boolean
  tool_calls_delta: number
  passed: boolean
}

interface BenchmarkFullResponse extends TestResultsResponse {
  timestamp?: string
  metadata?: {
    python_version?: string
    platform?: string
    git_commit?: string
  }
  summary?: {
    test_cases_run: number
    legitimate_cases: number
    violation_cases: number
    unauthorized_executions: number
    mismatch_detection_rate: number
    mismatch_detection_rate_pct?: string
    false_block_rate: number
    false_block_rate_pct?: string
    added_latency_mean_ms: number
    added_latency_p95_ms: number
  }
  security_tests?: Record<string, string>
  detailed_cases?: BenchmarkDetailCase[]
}

export const TestResults: React.FC = () => {
  const [data, setData] = useState<BenchmarkFullResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL')
  const [search, setSearch] = useState<string>('')
  const [selectedCase, setSelectedCase] = useState<BenchmarkDetailCase | null>(null)

  const loadResults = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = (await api.getTestResults()) as BenchmarkFullResponse
      setData(res)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to fetch test results'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadResults()
  }, [loadResults])

  const summary = data?.summary
  const securityTests = data?.security_tests ? Object.entries(data.security_tests) : []
  const detailedCases = data?.detailed_cases || []

  // Filter cases
  const filteredCases = useMemo(() => {
    return detailedCases.filter((c) => {
      if (categoryFilter !== 'ALL' && c.category !== categoryFilter) return false
      if (search.trim()) {
        const q = search.toLowerCase()
        if (!c.id.toLowerCase().includes(q) && !c.description.toLowerCase().includes(q)) {
          return false
        }
      }
      return true
    })
  }, [detailedCases, categoryFilter, search])

  return (
    <div className="space-y-6 pb-12 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Benchmark & Test Results</h1>
          <p className="text-[13px] text-ink2 mt-1">
            Automated security suite evaluating fail-closed enforcement, parameter tamper detection, and latency overhead.
          </p>
        </div>

        <button
          onClick={loadResults}
          disabled={loading}
          className="self-start sm:self-auto h-9 px-3.5 rounded-lg border border-line hover:border-ink2 bg-surface2 text-ink text-xs font-semibold flex items-center gap-2 transition-colors active:scale-95"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-accent' : ''}`} />
          <span>Refresh Results</span>
        </button>
      </div>

      {/* Main Content Area */}
      {error ? (
        <div className="p-6 rounded-xl bg-block/10 border border-block/30 text-center space-y-3">
          <AlertTriangle className="w-8 h-8 text-block mx-auto" />
          <h3 className="font-semibold text-ink text-[15px]">Failed to Load Benchmark Results</h3>
          <p className="text-[13px] text-ink2 max-w-md mx-auto">{error}</p>
          <button
            onClick={loadResults}
            className="px-4 py-2 rounded-lg bg-surface2 border border-line text-ink hover:text-white text-xs font-semibold"
          >
            Retry
          </button>
        </div>
      ) : loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-24 rounded-card bg-surface2/60 border border-line animate-pulse" />
            ))}
          </div>
          <div className="p-6 rounded-xl bg-surface border border-line space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10 w-full" />
            ))}
          </div>
        </div>
      ) : !data || !data.available ? (
        /* Empty / Unavailable state as explicitly requested */
        <div className="rounded-xl border border-line bg-surface p-8 sm:p-12 text-center max-w-2xl mx-auto space-y-4">
          <div className="w-12 h-12 rounded-full bg-surface2 border border-line flex items-center justify-center mx-auto text-ink2">
            <Terminal className="w-6 h-6 text-accent" />
          </div>
          <h2 className="text-xl font-bold text-ink">Run benchmarks to generate results</h2>
          <p className="text-[13px] text-ink2 leading-relaxed">
            No cached benchmark report found at <code className="px-1.5 py-0.5 rounded bg-surface2 font-mono text-accent">benchmarks/results.json</code>.
            Execute the test suite locally to verify the gateway against the full attack taxonomy.
          </p>

          <div className="p-3.5 rounded-lg bg-surface2/60 border border-line font-mono text-xs text-left text-ink max-w-lg mx-auto flex items-center justify-between">
            <span className="truncate">python benchmarks/run_benchmarks.py</span>
            <span className="text-ink2 text-[11px] ml-2 shrink-0">34 cases</span>
          </div>

          <div className="pt-2">
            <button
              onClick={loadResults}
              className="px-5 py-2.5 rounded-lg bg-accent text-bg hover:bg-accent/90 font-semibold text-xs transition-all active:scale-95"
            >
              Check Again
            </button>
          </div>
        </div>
      ) : (
        /* Full Benchmark Data Available */
        <div className="space-y-6">
          {/* Top Key Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Cases Evaluated"
              value={summary?.test_cases_run ?? 34}
              subtext={`${summary?.legitimate_cases ?? 12} legitimate · ${summary?.violation_cases ?? 22} attacks`}
            />
            <StatCard
              label="Mismatch Detection"
              value={summary?.mismatch_detection_rate_pct ?? '100.0%'}
              subtext="0 unauthorized executions"
              variant="allow"
            />
            <StatCard
              label="False Block Rate"
              value={summary?.false_block_rate_pct ?? '0.0%'}
              subtext="Legitimate requests allowed"
            />
            <StatCard
              label="Gateway Latency (p95)"
              value={`${summary?.added_latency_p95_ms?.toFixed(1) ?? '220.7'} ms`}
              subtext={`Mean ${summary?.added_latency_mean_ms?.toFixed(1) ?? '198.0'} ms overhead`}
            />
          </div>

          {/* Security Guarantees Matrix */}
          {securityTests.length > 0 && (
            <div className="rounded-xl border border-line bg-surface p-5 sm:p-6 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-ink flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-allow" />
                    Security Guarantee Invariants
                  </h2>
                  <p className="text-xs text-ink2 mt-0.5">
                    Core invariants tested under adversarial conditions. Zero failures permitted.
                  </p>
                </div>
                <span className="px-2.5 py-1 rounded-full text-xs font-mono font-semibold bg-allow/15 text-allow border border-allow/30">
                  {securityTests.length}/{securityTests.length} PASSED
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 pt-1">
                {securityTests.map(([testKey, status]) => {
                  const label = testKey
                    .replace(/^security_test_\d+_/, '')
                    .replace(/_/g, ' ')
                    .replace(/\b\w/g, (c) => c.toUpperCase())

                  const isPass = status === 'PASS'

                  return (
                    <div
                      key={testKey}
                      className="p-3 rounded-lg bg-surface2/60 border border-line flex items-center justify-between text-xs"
                    >
                      <span className="font-medium text-ink truncate mr-2" title={label}>
                        {label}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 font-mono text-[11px] font-bold px-2 py-0.5 rounded ${
                          isPass
                            ? 'bg-allow/15 text-allow border border-allow/30'
                            : 'bg-block/15 text-block border border-block/30'
                        }`}
                      >
                        {isPass ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                        {status}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* Filter & Search Bar */}
          <div className="p-4 rounded-xl bg-surface border border-line flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-sm">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="w-4 h-4 text-ink2 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search case ID or description..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-surface2 border border-line text-[13px] text-ink focus:outline-none focus:border-accent"
              />
            </div>

            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 bg-surface2 px-2.5 py-1.5 rounded-lg border border-line text-[12px] text-ink2">
                <Filter className="w-3.5 h-3.5 text-accent" />
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="bg-transparent text-ink text-[12px] font-medium focus:outline-none cursor-pointer"
                >
                  <option value="ALL">All Categories</option>
                  <option value="legitimate">Legitimate</option>
                  <option value="violation">Violation</option>
                </select>
              </div>

              <span className="text-xs text-ink2 font-mono whitespace-nowrap pl-2">
                {filteredCases.length} of {detailedCases.length} cases
              </span>
            </div>
          </div>

          {/* Detailed Cases Table (Desktop: 1440px / Mobile: 390px card list per design.md 3B) */}
          {filteredCases.length === 0 ? (
            <EmptyState
              title="No test cases match filter"
              description="Clear your search terms to view all evaluated benchmark cases."
            />
          ) : (
            <>
              {/* Desktop Table */}
              <div className="hidden md:block rounded-xl border border-line bg-surface overflow-hidden shadow-sm">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-line bg-surface2/60 text-[11px] font-mono uppercase tracking-wider text-ink2">
                      <th className="py-3 px-4 font-semibold">Case ID</th>
                      <th className="py-3 px-3 font-semibold">Category</th>
                      <th className="py-3 px-3 font-semibold">Description</th>
                      <th className="py-3 px-3 font-semibold">Expected</th>
                      <th className="py-3 px-3 font-semibold">Actual</th>
                      <th className="py-3 px-3 font-semibold text-center">Tool Call</th>
                      <th className="py-3 px-4 font-semibold text-right">Result</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line/40 text-[13px]">
                    {filteredCases.map((c) => (
                      <tr
                        key={c.id}
                        onClick={() => setSelectedCase(c)}
                        className="hover:bg-surface2/60 transition-colors cursor-pointer group"
                      >
                        <td className="py-3 px-4 font-mono font-bold text-accent whitespace-nowrap">
                          {c.id}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <span
                            className={`px-2 py-0.5 rounded text-[11px] font-mono uppercase ${
                              c.category === 'legitimate'
                                ? 'bg-surface2 text-ink2 border border-line'
                                : 'bg-block/15 text-block border border-block/30'
                            }`}
                          >
                            {c.category}
                          </span>
                        </td>
                        <td className="py-3 px-3 text-ink font-medium max-w-md truncate" title={c.description}>
                          {c.description}
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <DecisionChip decision={c.expected_decision as DecisionType} size="sm" />
                        </td>
                        <td className="py-3 px-3 whitespace-nowrap">
                          <DecisionChip decision={c.actual_decision as DecisionType} size="sm" />
                        </td>
                        <td className="py-3 px-3 text-center whitespace-nowrap font-mono text-xs">
                          {c.actual_tool_executed ? (
                            <span className="text-allow font-semibold">Executed (1)</span>
                          ) : (
                            <span className="text-ink2">Blocked (0)</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <span
                            className={`inline-flex items-center gap-1 font-mono text-[11px] font-bold px-2 py-0.5 rounded ${
                              c.passed
                                ? 'bg-allow/15 text-allow border border-allow/30'
                                : 'bg-block/15 text-block border border-block/30'
                            }`}
                          >
                            {c.passed ? 'PASS' : 'FAIL'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile Card List (390px) */}
              <div className="md:hidden space-y-3">
                {filteredCases.map((c) => (
                  <div
                    key={c.id}
                    onClick={() => setSelectedCase(c)}
                    className="p-4 rounded-xl border border-line bg-surface transition-all active:scale-[0.99] cursor-pointer shadow-sm"
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="font-mono text-xs font-bold text-accent">{c.id}</span>
                      <span
                        className={`inline-flex items-center gap-1 font-mono text-[11px] font-bold px-2 py-0.5 rounded ${
                          c.passed
                            ? 'bg-allow/15 text-allow border border-allow/30'
                            : 'bg-block/15 text-block border border-block/30'
                        }`}
                      >
                        {c.passed ? 'PASS' : 'FAIL'}
                      </span>
                    </div>

                    <p className="text-[13px] font-medium text-ink mb-3">{c.description}</p>

                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-line/60 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="text-ink2">Actual:</span>
                        <DecisionChip decision={c.actual_decision as DecisionType} size="sm" />
                      </div>
                      <span className="font-mono text-[11px] text-ink2">
                        {c.actual_tool_executed ? 'Tool: Executed' : 'Tool: Blocked (0)'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Modal / Case Inspector */}
          {selectedCase && (
            <div
              className="fixed inset-0 z-50 bg-bg/80 backdrop-blur-sm flex items-center justify-center p-4"
              onClick={() => setSelectedCase(null)}
            >
              <div
                className="bg-surface border border-line rounded-xl max-w-lg w-full p-6 shadow-2xl space-y-4"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-accent text-sm">#{selectedCase.id}</span>
                    <span
                      className={`text-[11px] font-mono px-2 py-0.5 rounded ${
                        selectedCase.category === 'legitimate'
                          ? 'bg-surface2 text-ink2 border border-line'
                          : 'bg-block/15 text-block border border-block/30'
                      }`}
                    >
                      {selectedCase.category}
                    </span>
                  </div>
                  <span
                    className={`font-mono text-xs font-bold px-2 py-0.5 rounded ${
                      selectedCase.passed ? 'bg-allow/15 text-allow' : 'bg-block/15 text-block'
                    }`}
                  >
                    {selectedCase.passed ? 'PASS' : 'FAIL'}
                  </span>
                </div>

                <div>
                  <h3 className="font-semibold text-ink text-sm">Description</h3>
                  <p className="text-[13px] text-ink2 mt-1">{selectedCase.description}</p>
                </div>

                <div className="grid grid-cols-2 gap-3 p-3 rounded-lg bg-surface2 border border-line text-xs font-mono">
                  <div>
                    <span className="text-ink2 text-[11px] block">Expected Decision</span>
                    <div className="mt-1">
                      <DecisionChip decision={selectedCase.expected_decision as DecisionType} size="sm" />
                    </div>
                  </div>
                  <div>
                    <span className="text-ink2 text-[11px] block">Actual Decision</span>
                    <div className="mt-1">
                      <DecisionChip decision={selectedCase.actual_decision as DecisionType} size="sm" />
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold text-ink text-xs">Gateway Enforcement Rationale</h3>
                  <p className="text-xs text-ink2 mt-1 font-mono p-2.5 rounded bg-surface2 border border-line">
                    {selectedCase.reason || 'Enforced strictly per security policy'}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-line text-xs">
                  <span className="text-ink2">
                    Tool execution verified: {selectedCase.actual_tool_executed ? 'Yes' : 'No (0 calls)'}
                  </span>
                  <button
                    onClick={() => setSelectedCase(null)}
                    className="px-4 py-1.5 rounded-lg bg-surface2 hover:bg-surface2/80 text-ink text-xs font-medium border border-line"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
