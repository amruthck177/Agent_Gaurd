/**
 * AgentGuard Typed API Client
 * Generated / Typed from OpenAPI specification (docs/openapi.json & docs/api-contract.md)
 */

export type Decision = 'ALLOW' | 'ASK_HUMAN' | 'BLOCK'

export interface ExecuteRequest {
  agent_id: string
  task_id: string
  tool: string
  params: Record<string, unknown>
  approval_id?: string | null
}

export interface ExecuteResponse {
  decision: Decision
  reason: string
  executed: boolean
  audit_id: number | null
  approval_id: string | null
}

export type ApprovalStatus = 'pending' | 'approved' | 'rejected' | 'used' | 'revoked' | 'expired'

export interface Approval {
  id: string
  agent_id: string
  task_id: string
  tool: string
  approved_params_json: string
  approved_hash: string
  status: ApprovalStatus
  created_at: string
  approved_at: string | null
  expires_at: string | null
  revoked_at: string | null
  used_at: string | null
}

export interface ApprovalCreateRequest {
  agent_id: string
  task_id: string
  tool: string
  params: Record<string, unknown>
}

export interface Policy {
  id: number
  agent_id: string | null
  task_id: string | null
  tool: string
  condition_json: string
  decision: Decision
  version: number
  active: number | boolean
}

export interface AuditRecord {
  id: number
  ts: string
  agent_id: string
  task_id: string
  tool: string
  params_masked: string
  decision: Decision
  reason: string
  approval_id: string | null
  executed: number | boolean
  prev_hash: string
  hash: string
}

export interface AuditVerifyResponse {
  ok: boolean
  checked: number
  broken_at: number | null
}

export interface AuditQueryParams {
  agent_id?: string
  task_id?: string
  tool?: string
  decision?: Decision | string
  executed?: boolean
  approval_id?: string
  since?: string
  until?: string
  search?: string
  limit?: number
  offset?: number
}

export interface ToolCallItem {
  id: number
  tool: string
  params_json: string
  executed_at: string
  audit_id: number | null
}

export interface ToolCallResponse {
  count: number
  tool_calls: ToolCallItem[]
}

export interface TestResultsResponse {
  available: boolean
  test_cases_run?: number
  legitimate_cases?: number
  violation_cases?: number
  unauthorized_executions?: number
  mismatch_detection_rate?: number
  false_block_rate?: number
  latency_mean_ms?: number
  latency_p95_ms?: number
}

export interface ScenarioParamRow {
  label: string
  approved: string
  attempted: string
  mismatch: boolean
}

export interface ScenarioResult {
  scenario: string
  decision?: Decision | string
  reason?: string
  executed?: boolean
  audit_id?: number | null
  approval_id?: string | null
  tool?: string
  tool_executions?: number
  params_compare?: ScenarioParamRow[]
}

export class ApiError extends Error {
  status: number
  data?: unknown
  constructor(message: string, status: number, data?: unknown) {
    super(message)
    this.status = status
    this.data = data
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = path.startsWith('http') ? path : path
  const headers = new Headers(options.headers || {})

  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(url, {
    ...options,
    headers,
  })

  if (!response.ok) {
    let errBody: unknown
    try {
      errBody = await response.json()
    } catch {
      errBody = await response.text()
    }
    throw new ApiError(
      `Request to ${path} failed with status ${response.status}`,
      response.status,
      errBody,
    )
  }

  // Handle empty or void responses
  if (response.status === 204) {
    return {} as T
  }

  return response.json()
}

export const api = {
  // Liveness Check
  async health(): Promise<{ status: string }> {
    return request<{ status: string }>('/health')
  },

  // Gateway Execution
  async execute(req: ExecuteRequest): Promise<ExecuteResponse> {
    return request<ExecuteResponse>('/v1/gateway/execute', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  // Approvals
  async listApprovals(status?: ApprovalStatus | string): Promise<Approval[]> {
    const qs = status ? `?status=${encodeURIComponent(status)}` : ''
    return request<Approval[]>(`/v1/approvals${qs}`)
  },

  async createApproval(req: ApprovalCreateRequest): Promise<Approval> {
    return request<Approval>('/v1/approvals', {
      method: 'POST',
      body: JSON.stringify(req),
    })
  },

  async approve(id: string): Promise<Approval> {
    return request<Approval>(`/v1/approvals/${encodeURIComponent(id)}/approve`, {
      method: 'POST',
    })
  },

  async reject(id: string): Promise<Approval> {
    return request<Approval>(`/v1/approvals/${encodeURIComponent(id)}/reject`, {
      method: 'POST',
    })
  },

  async revoke(id: string): Promise<Approval> {
    return request<Approval>(`/v1/approvals/${encodeURIComponent(id)}/revoke`, {
      method: 'POST',
    })
  },

  // Policies
  async listPolicies(): Promise<Policy[]> {
    return request<Policy[]>('/v1/policies')
  },

  async updatePolicy(policy: Partial<Policy>): Promise<Policy> {
    return request<Policy>('/v1/policies', {
      method: 'PUT',
      body: JSON.stringify(policy),
    })
  },

  // Audit
  async listAudit(params: AuditQueryParams = {}): Promise<AuditRecord[]> {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        query.append(k, String(v))
      }
    })
    const qs = query.toString() ? `?${query.toString()}` : ''
    return request<AuditRecord[]>(`/v1/audit${qs}`)
  },

  async verifyAudit(): Promise<AuditVerifyResponse> {
    return request<AuditVerifyResponse>('/v1/audit/verify')
  },

  getAuditCsvUrl(params: AuditQueryParams = {}): string {
    const query = new URLSearchParams({ format: 'csv' })
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        query.append(k, String(v))
      }
    })
    return `/v1/audit?${query.toString()}`
  },

  // Proof of Execution Tool Calls
  async getToolCalls(params: { tool?: string; audit_id?: number } = {}): Promise<ToolCallResponse> {
    const query = new URLSearchParams()
    if (params.tool) query.append('tool', params.tool)
    if (params.audit_id) query.append('audit_id', String(params.audit_id))
    const qs = query.toString() ? `?${query.toString()}` : ''
    return request<ToolCallResponse>(`/v1/tool_calls${qs}`)
  },

  // Test Results
  async getTestResults(): Promise<TestResultsResponse> {
    return request<TestResultsResponse>('/v1/tests/results')
  },

  // Demo Controls
  async resetDemo(): Promise<{ status: string; message: string }> {
    return request<{ status: string; message: string }>('/v1/demo/reset', {
      method: 'POST',
    })
  },

  async tamperDemo(recordId?: number): Promise<{ status: string; record_id: number }> {
    return request<{ status: string; record_id: number }>('/v1/demo/tamper', {
      method: 'POST',
      body: JSON.stringify(recordId ? { record_id: recordId } : {}),
    })
  },

  async runScenario(scenario: string): Promise<ScenarioResult> {
    return request<ScenarioResult>('/v1/demo/scenario', {
      method: 'POST',
      body: JSON.stringify({ scenario }),
    })
  },
}
