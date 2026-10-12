# AgentGuard 2.0 — API Contract

> **Status:** Frozen (`backend-frozen` commit). Do not change endpoint shapes, field names, enum values, or reason strings without updating this document and `openapi.json`.

## Base URL

| Environment | URL |
|-------------|-----|
| Local development | `http://localhost:8000` |
| Frontend origin (CORS allowed) | `http://localhost:5173` |

## CORS

Strict. `Access-Control-Allow-Origin` is **only** set to `http://localhost:5173`. Any other origin receives no CORS headers.

## Authentication

None in the demo / development build. In production this layer must be added before any internet-facing deployment (see [docs/plan.md](plan.md) roadmap).

## Decisions Enum

All gateway and audit records use exactly **three** decision values:

| Value | Meaning |
|-------|---------|
| `"ALLOW"` | Tool executed; action completed |
| `"ASK_HUMAN"` | Sensitive action; approval created and awaiting human review |
| `"BLOCK"` | Execution denied; tool did **not** run |

## Reason Strings

The `reason` field is deterministic. Frontend code **may** display it verbatim.

| Reason | When |
|--------|------|
| `"Request approved and executed successfully"` | ALLOW |
| `"Unknown agent: <id>"` | Agent not in DB |
| `"Unknown tool: <name>"` | Tool not registered |
| `"Payment over threshold: requires approval"` | ASK_HUMAN — amount ≥ threshold |
| `"Sensitive payment: requires approval"` | ASK_HUMAN — policy match |
| `"Email requires approval"` | ASK_HUMAN — email tool |
| `"Read-only agent attempted write SQL"` | BLOCK — policy |
| `"SQL statement blocked by policy: <type>"` | BLOCK — hard SQL policy |
| `"Destructive SQL blocked"` | BLOCK — DROP/DELETE/TRUNCATE/ALTER |
| `"Approval does not match request"` | BLOCK — agent/task/tool mismatch |
| `"Recipient changed after approval"` | BLOCK — exact-param mismatch |
| `"Amount changed after approval"` | BLOCK — exact-param mismatch |
| `"Currency changed after approval"` | BLOCK — exact-param mismatch |
| `"Email recipient changed after approval"` | BLOCK — exact-param mismatch |
| `"Approval expired"` | BLOCK — TTL exceeded |
| `"Approval revoked"` | BLOCK — human revoked |
| `"Approval already used (replay)"` | BLOCK — duplicate submission |
| `"Gateway error: failed closed"` | BLOCK — any unhandled error |

---

## Endpoints

### `GET /health`

Liveness probe.

**Response 200**
```json
{ "status": "ok" }
```

---

### `POST /v1/gateway/execute`

Submit an agent tool-call through the enforcement gateway.

**Request body**
```json
{
  "agent_id":   "accounts-agent",
  "task_id":    "task-accounts-1",
  "tool":       "payments.send",
  "params":     { "recipient": "Supplier A", "amount": 5000.00, "currency": "INR" },
  "approval_id": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | string | ✓ | Registered agent identifier |
| `task_id` | string | ✓ | Active task identifier |
| `tool` | string | ✓ | Tool name (`payments.send`, `email.send`, `database.run_sql`) |
| `params` | object | ✓ | Tool parameters (arbitrary key→value) |
| `approval_id` | string\|null | — | Pre-obtained approval UUID |

**Response 200** — always 200 even for BLOCK (decision is in the body)
```json
{
  "decision":    "BLOCK",
  "reason":      "Recipient changed after approval",
  "executed":    false,
  "audit_id":    42,
  "approval_id": "a1b2c3d4-..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `decision` | `"ALLOW"\|"ASK_HUMAN"\|"BLOCK"` | Enforcement decision |
| `reason` | string | Human-readable deterministic reason |
| `executed` | boolean | `true` iff tool actually ran |
| `audit_id` | integer\|null | Audit log row ID |
| `approval_id` | string\|null | Created or validated approval UUID |

**Response 422** — Pydantic validation failure (missing required field, wrong type)
```json
{ "detail": [ { "loc": ["body", "agent_id"], "msg": "Field required", "type": "missing" } ] }
```

**Response 500** — Unhandled server error (fail closed)
```json
{
  "decision": "BLOCK",
  "reason":   "Gateway error: failed closed",
  "error_id": "550e8400-e29b-41d4-a716-446655440000"
}
```
> No stack trace or exception text is ever included in 500 responses.

---

### `POST /v1/approvals`

Create a new pending approval bound to exact canonical parameters.

**Request body**
```json
{
  "agent_id": "accounts-agent",
  "task_id":  "task-accounts-1",
  "tool":     "payments.send",
  "params":   { "recipient": "Supplier A", "amount": 5000.00, "currency": "INR" }
}
```

**Response 201**
```json
{
  "id":                   "a1b2c3d4-0000-0000-0000-000000000001",
  "agent_id":             "accounts-agent",
  "task_id":              "task-accounts-1",
  "tool":                 "payments.send",
  "approved_params_json": "{\"amount\":5000,\"currency\":\"INR\",\"recipient\":\"supplier a\"}",
  "approved_hash":        "sha256hex...",
  "status":               "pending",
  "created_at":           "2026-10-12T15:00:00+00:00",
  "approved_at":          null,
  "expires_at":           "2026-10-12T15:10:00+00:00",
  "revoked_at":           null,
  "used_at":              null
}
```

**Approval status lifecycle:**
```
pending → approved | rejected
approved → used (atomic, one-shot) | revoked | expired
```

---

### `POST /v1/approvals/{id}/approve`

Human approves a pending approval.

**Response 200** — full approval object with `"status": "approved"`  
**Response 404** — approval not found or not in `pending` status

---

### `POST /v1/approvals/{id}/reject`

Human rejects a pending approval.

**Response 200** — full approval object with `"status": "rejected"`  
**Response 404** — approval not found or not in `pending` status

---

### `POST /v1/approvals/{id}/revoke`

Human revokes an approved (but not yet used) approval.

**Response 200** — full approval object with `"status": "revoked"`  
**Response 404** — approval not found

---

### `GET /v1/approvals`

List approval records.

**Query parameters**

| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status: `pending`, `approved`, `rejected`, `used`, `revoked`, `expired` |

**Response 200** — array of approval objects

---

### `GET /v1/policies`

List all active policies.

**Response 200**
```json
[
  {
    "id":             1,
    "agent_id":       null,
    "task_id":        null,
    "tool":           "payments.send",
    "condition_json": "{\"amount_paise_gte\": 500000}",
    "decision":       "ASK_HUMAN",
    "version":        1,
    "active":         1
  }
]
```

---

### `PUT /v1/policies`

Create or update a policy.

**Request body**
```json
{
  "id":             null,
  "agent_id":       "accounts-agent",
  "task_id":        null,
  "tool":           "payments.send",
  "condition_json": "{\"amount_paise_gte\": 500000}",
  "decision":       "ASK_HUMAN",
  "version":        1,
  "active":         true
}
```

If `id` is null, a new policy is inserted. If `id` is set, the existing row is updated and `version` is incremented.

**Response 200** — full policy object with assigned `id`

---

### `GET /v1/audit`

Query the append-only audit log.

**Query parameters**

| Param | Type | Description |
|-------|------|-------------|
| `agent_id` | string | Filter by agent |
| `task_id` | string | Filter by task |
| `tool` | string | Filter by tool |
| `decision` | string | `ALLOW`, `ASK_HUMAN`, or `BLOCK` |
| `executed` | boolean | `true` / `false` |
| `approval_id` | string | Filter by approval |
| `since` | ISO-8601 string | Inclusive start timestamp |
| `until` | ISO-8601 string | Inclusive end timestamp |
| `search` | string | Full-text filter on `reason` / `params_masked` |
| `limit` | integer | Max rows (default 100) |
| `offset` | integer | Pagination offset (default 0) |
| `format` | `"csv"` | Returns `text/csv` download instead of JSON |

**Response 200 (JSON)** — array of audit records
```json
[
  {
    "id":            42,
    "ts":            "2026-10-12T15:01:00+00:00",
    "agent_id":      "accounts-agent",
    "task_id":       "task-accounts-1",
    "tool":          "payments.send",
    "params_masked": "{\"amount_paise\": 500000, \"currency\": \"INR\", \"recipient\": \"supplier a\"}",
    "decision":      "BLOCK",
    "reason":        "Recipient changed after approval",
    "approval_id":   "a1b2c3d4-...",
    "executed":      0,
    "prev_hash":     "abc123...",
    "hash":          "def456..."
  }
]
```

> `params_masked` — secrets (API keys, tokens, passwords) are scrubbed before storage; they never appear in audit rows.

---

### `GET /v1/audit/verify`

Recompute the SHA-256 hash chain from genesis and verify integrity.

**Response 200**
```json
{ "ok": true,  "checked": 42, "broken_at": null }
{ "ok": false, "checked": 12, "broken_at": 13 }
```

| Field | Type | Description |
|-------|------|-------------|
| `ok` | boolean | `true` if chain is intact |
| `checked` | integer | Number of records verified |
| `broken_at` | integer\|null | First record ID where chain breaks (null if ok) |

---

### `GET /v1/tool_calls`  ·  `GET /v1/tool-calls`

Proof-of-execution log — records only created when a tool **actually ran**.

**Query parameters**

| Param | Type | Description |
|-------|------|-------------|
| `tool` | string | Filter by tool name |
| `audit_id` | integer | Filter by associated audit record |

**Response 200**
```json
{
  "count": 1,
  "tool_calls": [
    {
      "id":          1,
      "tool":        "payments.send",
      "params_json": "{\"amount_paise\": 500000, \"currency\": \"INR\", \"recipient\": \"supplier a\"}",
      "executed_at": "2026-10-12T15:02:00+00:00",
      "audit_id":    43
    }
  ]
}
```

---

### `POST /v1/demo/reset`  *(DEMO_MODE=1 required)*

Drops and re-creates the demo database with seeded agents, tasks, and policies.

**Response 200**
```json
{ "status": "ok", "message": "Demo database reset and seeded successfully" }
```

**Response 403** — when `DEMO_MODE` env var is not `"1"`
```json
{ "detail": "Demo endpoint disabled (DEMO_MODE != 1)" }
```

---

### `POST /v1/demo/tamper`  *(DEMO_MODE=1 required)*

Directly alters an audit record's decision without updating hashes (for demo purposes).

**Request body** (optional)
```json
{ "record_id": 5 }
```
If omitted, the latest audit row is tampered.

**Response 200**
```json
{ "status": "tampered", "record_id": 5 }
```

**Response 403** — DEMO_MODE guard  
**Response 404** — record not found

---

### `GET /v1/tests/results`

Serves the pre-computed benchmark results.

**Response 200** (file found)
```json
{
  "available": true,
  "test_cases_run": 30,
  "legitimate_cases": 12,
  "violation_cases": 18,
  "unauthorized_executions": 0,
  "mismatch_detection_rate": 1.0,
  "false_block_rate": 0.0,
  "latency_mean_ms": 1.2,
  "latency_p95_ms": 3.1
}
```

**Response 200** (file not yet generated)
```json
{ "available": false }
```

---

## WebSocket  `WS /ws/events`

Real-time event feed for the dashboard. The server broadcasts JSON messages on every significant state change.

### Client → Server

Send the literal string `"ping"` to receive `"pong"` as a keep-alive.

### Server → Client (event shapes)

#### `gateway.decision`
```json
{
  "type": "gateway.decision",
  "data": {
    "agent_id":    "accounts-agent",
    "task_id":     "task-accounts-1",
    "tool":        "payments.send",
    "decision":    "BLOCK",
    "reason":      "Recipient changed after approval",
    "executed":    false,
    "audit_id":    42,
    "approval_id": "a1b2c3d4-..."
  }
}
```

#### `approval.created`
```json
{
  "type": "approval.created",
  "data": { /* full Approval object */ }
}
```

#### `approval.updated`
```json
{
  "type":   "approval.updated",
  "action": "approved",
  "data":   { /* full Approval object */ }
}
```
`action` values: `"approved"`, `"rejected"`, `"revoked"`

#### `policy.updated`
```json
{
  "type": "policy.updated",
  "data": { /* full Policy object */ }
}
```

#### `demo.reset`
```json
{ "type": "demo.reset", "status": "ok" }
```

#### `demo.tamper`
```json
{ "type": "demo.tamper", "record_id": 5 }
```

---

## Error Handling

| HTTP Status | When | Body |
|-------------|------|------|
| 200 | All gateway/approval/policy calls — decision in body | varies |
| 201 | Approval created | approval object |
| 403 | Demo endpoint with `DEMO_MODE != 1` | `{ "detail": "..." }` |
| 404 | Resource not found | `{ "detail": "..." }` |
| 422 | Pydantic validation failure | `{ "detail": [...] }` |
| 500 | Unhandled server error | `{ "decision": "BLOCK", "reason": "Gateway error: failed closed", "error_id": "uuid" }` |

> **Fail-closed guarantee:** Any error at any point in the gateway pipeline returns `"decision": "BLOCK"`. The tool is **never** executed on error.
