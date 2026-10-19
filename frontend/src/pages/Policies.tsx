import React, { useState, useEffect, useMemo } from 'react'
import {
  Plus,
  RotateCw,
  Edit2,
  X,
  Save,
  AlertCircle,
} from 'lucide-react'
import { DecisionChip, DecisionType } from '../components/common/DecisionChip'
import { EmptyState } from '../components/common/EmptyState'
import { Skeleton } from '../components/common/Skeleton'
import { api, Policy, Decision } from '../lib/api'

export const Policies: React.FC = () => {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string>('all')

  // Edit / Create modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingPolicy, setEditingPolicy] = useState<Partial<Policy> | null>(null)
  const [saving, setSaving] = useState(false)

  const loadPolicies = async () => {
    try {
      const data = await api.listPolicies()
      setPolicies(data)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load policy rules')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadPolicies()
  }, [])

  // Agent scopes
  const agentScopes = useMemo(() => {
    const list = new Set<string>()
    policies.forEach((p) => {
      if (p.agent_id) list.add(p.agent_id)
    })
    return ['all', ...Array.from(list)]
  }, [policies])

  // Filtered policies
  const filteredPolicies = useMemo(() => {
    if (selectedAgent === 'all') return policies
    return policies.filter((p) => p.agent_id === selectedAgent || !p.agent_id)
  }, [policies, selectedAgent])

  const handleOpenEdit = (policy?: Policy) => {
    if (policy) {
      setEditingPolicy({ ...policy })
    } else {
      setEditingPolicy({
        id: undefined,
        agent_id: 'accounts-agent',
        task_id: null,
        tool: 'payments.send',
        condition_json: JSON.stringify({ amount_paise_gte: 1000000 }, null, 2),
        decision: 'ASK_HUMAN',
        version: 1,
        active: 1,
      })
    }
    setModalOpen(true)
  }

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingPolicy) return

    setSaving(true)
    try {
      await api.updatePolicy(editingPolicy)
      await loadPolicies()
      setModalOpen(false)
      setEditingPolicy(null)
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : 'Failed to save policy rule')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-[22px] sm:text-[24px] font-bold text-ink tracking-tight">
              Deterministic Policies Matrix
            </h1>
            <span className="px-2.5 py-0.5 rounded-full bg-accent/15 border border-accent/30 text-accent text-[11px] font-mono font-semibold">
              Gateway Enforcement
            </span>
          </div>
          <p className="text-[13px] text-ink2 mt-1">
            Rules evaluated outside agent memory. Changes update the deterministic policy engine atomically.
          </p>
        </div>

        <div className="flex items-center gap-3 self-start sm:self-auto">
          <button
            onClick={loadPolicies}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-surface border border-line text-ink2 hover:text-ink text-[12px] font-medium transition-colors"
          >
            <RotateCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => handleOpenEdit()}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-bg hover:bg-accent/90 font-semibold text-[13px] transition-all active:scale-95 shadow-md shadow-accent/10 focus-accent"
          >
            <Plus className="w-4 h-4" />
            <span>Add Rule</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-block/15 border border-block/40 text-block text-xs font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filter by Agent Scope */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <span className="text-[12px] font-mono text-ink2 uppercase mr-1">Scope:</span>
        {agentScopes.map((scope) => (
          <button
            key={scope}
            onClick={() => setSelectedAgent(scope)}
            className={`px-3 py-1.5 rounded-lg text-[12px] font-mono transition-all whitespace-nowrap ${
              selectedAgent === scope
                ? 'bg-accent/20 border border-accent/40 text-accent font-bold'
                : 'bg-surface border border-line text-ink2 hover:text-ink'
            }`}
          >
            {scope === 'all' ? 'All Autonomous Agents' : scope}
          </button>
        ))}
      </div>

      {/* Rules Table / Cards */}
      {loading && policies.length === 0 ? (
        <div className="space-y-3">
          <Skeleton className="h-16 w-full rounded-card" />
          <Skeleton className="h-16 w-full rounded-card" />
          <Skeleton className="h-16 w-full rounded-card" />
        </div>
      ) : filteredPolicies.length === 0 ? (
        <EmptyState
          title="No policy rules configured"
          description="Click 'Add Rule' above to define deterministic interception criteria for autonomous agents."
        />
      ) : (
        <div className="rounded-card border border-line bg-surface overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface2/80 border-b border-line text-[11px] font-mono text-ink2 uppercase tracking-wider">
                  <th className="py-3 px-4">Rule #</th>
                  <th className="py-3 px-3">Agent Scope</th>
                  <th className="py-3 px-4">Tool Target</th>
                  <th className="py-3 px-4">Deterministic Condition</th>
                  <th className="py-3 px-3">Decision</th>
                  <th className="py-3 px-3 text-center">Version</th>
                  <th className="py-3 px-3 text-center">Status</th>
                  <th className="py-3 px-4 text-right">Edit</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/60 font-mono text-[13px]">
                {filteredPolicies.map((p) => {
                  let conditionDisplay = p.condition_json
                  try {
                    const parsed = JSON.parse(p.condition_json)
                    if (parsed.amount_paise_gte) {
                      conditionDisplay = `amount >= ₹${(parsed.amount_paise_gte / 100).toLocaleString('en-IN')}`
                    } else if (parsed.domain_not_in) {
                      conditionDisplay = `domain NOT in [${parsed.domain_not_in.join(', ')}]`
                    } else if (parsed.read_only) {
                      conditionDisplay = `read_only agent disallowed write`
                    }
                  } catch {
                    // keep raw
                  }

                  const decisionLabel =
                    p.decision === 'ASK_HUMAN' ? 'ASK HUMAN' : p.decision

                  const isActive = Boolean(p.active)

                  return (
                    <tr key={p.id} className="h-[52px] hover:bg-surface2/50 transition-colors">
                      <td className="py-2.5 px-4 font-bold text-accent">
                        POL-00{p.id}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="px-1.5 py-0.5 rounded bg-surface2 border border-line text-[11px] text-ink">
                          {p.agent_id || 'Global (All)'}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 font-medium text-ink">
                        {p.tool}
                      </td>
                      <td className="py-2.5 px-4 text-ink2 max-w-sm truncate" title={p.condition_json}>
                        <code className="text-[12px] text-accent/90">{conditionDisplay}</code>
                      </td>
                      <td className="py-2.5 px-3">
                        <DecisionChip decision={decisionLabel as DecisionType} size="sm" />
                      </td>
                      <td className="py-2.5 px-3 text-center text-ink2 text-[12px]">
                        v{p.version}
                      </td>
                      <td className="py-2.5 px-3 text-center">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-pill text-[10px] font-bold uppercase ${
                            isActive
                              ? 'bg-allow/15 text-allow border border-allow/30'
                              : 'bg-surface2 text-ink2 border border-line'
                          }`}
                        >
                          {isActive ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <button
                          onClick={() => handleOpenEdit(p)}
                          className="p-1 rounded hover:bg-surface2 text-ink2 hover:text-accent transition-colors"
                          title="Edit policy rule"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Edit / Add Modal Form */}
      {modalOpen && editingPolicy && (
        <div className="fixed inset-0 z-50 overflow-hidden flex items-center justify-center p-4">
          <div
            onClick={() => setModalOpen(false)}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
          />

          <div className="relative z-10 w-full max-w-lg rounded-card border border-line bg-surface p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <h3 className="text-[18px] font-bold text-ink">
                {editingPolicy.id ? `Edit Policy Rule #POL-00${editingPolicy.id}` : 'Create New Policy Rule'}
              </h3>
              <button
                onClick={() => setModalOpen(false)}
                className="text-ink2 hover:text-ink p-1 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSavePolicy} className="space-y-4">
              <div>
                <label className="block text-[12px] font-mono text-ink2 uppercase mb-1">
                  Target Agent ID (Leave empty for global)
                </label>
                <input
                  type="text"
                  value={editingPolicy.agent_id || ''}
                  onChange={(e) =>
                    setEditingPolicy({ ...editingPolicy, agent_id: e.target.value || null })
                  }
                  placeholder="e.g. accounts-agent"
                  className="w-full h-10 px-3 rounded-lg bg-surface2 border border-line text-ink font-mono text-[13px] focus:outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="block text-[12px] font-mono text-ink2 uppercase mb-1">
                  Tool Target
                </label>
                <select
                  value={editingPolicy.tool || 'payments.send'}
                  onChange={(e) => setEditingPolicy({ ...editingPolicy, tool: e.target.value })}
                  className="w-full h-10 px-3 rounded-lg bg-surface2 border border-line text-ink font-mono text-[13px] focus:outline-none focus:border-accent"
                >
                  <option value="payments.send">payments.send</option>
                  <option value="email.send">email.send</option>
                  <option value="database.run_sql">database.run_sql</option>
                </select>
              </div>

              <div>
                <label className="block text-[12px] font-mono text-ink2 uppercase mb-1">
                  Condition JSON
                </label>
                <textarea
                  rows={4}
                  value={editingPolicy.condition_json || ''}
                  onChange={(e) =>
                    setEditingPolicy({ ...editingPolicy, condition_json: e.target.value })
                  }
                  placeholder='{"amount_paise_gte": 1000000}'
                  className="w-full p-3 rounded-lg bg-surface2 border border-line text-ink font-mono text-[12px] focus:outline-none focus:border-accent"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[12px] font-mono text-ink2 uppercase mb-1">
                    Enforcement Decision
                  </label>
                  <select
                    value={editingPolicy.decision || 'ASK_HUMAN'}
                    onChange={(e) =>
                      setEditingPolicy({ ...editingPolicy, decision: e.target.value as Decision })
                    }
                    className="w-full h-10 px-3 rounded-lg bg-surface2 border border-line text-ink font-mono text-[13px] focus:outline-none focus:border-accent"
                  >
                    <option value="ASK_HUMAN">ASK_HUMAN</option>
                    <option value="BLOCK">BLOCK</option>
                    <option value="ALLOW">ALLOW</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[12px] font-mono text-ink2 uppercase mb-1">
                    Status
                  </label>
                  <select
                    value={editingPolicy.active ? '1' : '0'}
                    onChange={(e) =>
                      setEditingPolicy({ ...editingPolicy, active: e.target.value === '1' ? 1 : 0 })
                    }
                    className="w-full h-10 px-3 rounded-lg bg-surface2 border border-line text-ink font-mono text-[13px] focus:outline-none focus:border-accent"
                  >
                    <option value="1">Active</option>
                    <option value="0">Disabled</option>
                  </select>
                </div>
              </div>

              <div className="pt-3 flex justify-end gap-3 border-t border-line">
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2 rounded-lg border border-line text-ink text-[13px] hover:bg-surface2"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 rounded-lg bg-accent text-bg hover:bg-accent/90 font-semibold text-[13px] flex items-center gap-1.5 focus-accent"
                >
                  <Save className="w-4 h-4" />
                  <span>{saving ? 'Saving...' : 'Save Policy Rule'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
