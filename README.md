<div align="center">

# 🛡️ AgentGuard 2.0

### Deterministic Security Gateway for Autonomous AI Agents

**Every Action. Every Agent. Every Time.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![Tests](https://img.shields.io/badge/Tests-110%20passed-brightgreen)](#testing)
[![Defense Rate](https://img.shields.io/badge/Defense%20Rate-100%25-brightgreen)](#benchmark-results)
[![False Blocks](https://img.shields.io/badge/False%20Blocks-0.0%25-brightgreen)](#benchmark-results)

> DevHack 2026 · Team LogicLords · Yenepoya Institute of Technology · PS 2.1 — AI Agent Safety and Control

</div>

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [The Solution](#-the-solution)
- [Live Demo](#-live-demo)
- [Architecture](#-architecture)
- [Enforcement Pipeline](#-enforcement-pipeline)
- [Security Features](#-security-features)
- [API Reference](#-api-reference)
- [Tech Stack](#-tech-stack)
- [Quick Start](#-quick-start)
- [Project Structure](#-project-structure)
- [Testing](#-testing)
- [Benchmark Results](#-benchmark-results)
- [Known Limitations](#-known-limitations)
- [Team](#-team)

---

## ❗ The Problem

AI agents can now pay suppliers, send emails, and edit databases — autonomously. But there is a critical gap:

| Problem | What Goes Wrong Today |
|---------|----------------------|
| **Approval of description, not parameters** | Human approves *"pay Supplier A ₹5,000"* — agent executes *"pay Supplier B ₹50,000"* |
| **Time-of-check vs time-of-use (TOCTOU)** | Between approval and execution, the payee or amount silently changes |
| **Prompt injection & agent drift** | A malicious invoice email or confused model changes the approved action |
| **Stale or replayed approvals** | Expired, withdrawn, or previously-used tokens are re-submitted |
| **Over-broad permissions** | A read-only agent writes to the database; an agent exceeds its task scope |
| **Untrustworthy logs** | After an incident, logs can be edited — nothing is provable in court |

**The core threat:** Humans approve what an agent *says* it will do, but nothing enforces that the agent then does *exactly that*.

---

## ✅ The Solution

**AgentGuard is a deterministic enforcement gateway.** Every sensitive AI agent action — payments, emails, database writes — must pass through it before the tool runs.

> *"The model cannot talk its way past the gateway."*

**Key guarantees:**
1. Approvals are cryptographically bound to **exact parameters** (recipient, amount, currency)
2. Every check happens **at execution time** — not just when approval was granted
3. Tokens **expire**, can be **revoked**, and are **single-use** (no replay)
4. Gateway failure → **fail closed** (always BLOCK, never default open)
5. Every decision is logged in a **tamper-evident SHA-256 Merkle chain**

---

## 🎬 Live Demo

The canonical demo that explains everything in 30 seconds:

1. Human approves **"pay Supplier A ₹5,000"**
2. Agent (compromised or confused) tries to pay **Supplier B ₹5,000** with that approval
3. AgentGuard returns → **`BLOCK: "Recipient changed after approval"`**
4. Payment tool execution counter → **still 0**
5. Audit log → records the attempt with hash proof
6. The original, unchanged payment to Supplier A → **ALLOW** ✅

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AI Agent                                 │
│            (proposes tool calls; holds no credentials)          │
└───────────────────────┬─────────────────────────────────────────┘
                        │  POST /v1/execute
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AgentGuard Gateway                            │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Agent        │  │ Policy       │  │ Approval             │  │
│  │ Registry     │  │ Engine       │  │ State Machine        │  │
│  │              │  │              │  │                      │  │
│  │ • Known?     │  │ • Permitted? │  │ • Hash match?        │  │
│  │ • Role?      │  │ • Threshold? │  │ • Not expired?       │  │
│  │ • Task?      │  │ • Allowlist? │  │ • Not revoked?       │  │
│  │              │  │ • SQL safe?  │  │ • Not used? (atomic) │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Audit Log (SHA-256 Merkle Chain)           │    │
│  │  record_n.hash = SHA256(prev_hash + canonical_json(n)) │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────┬─────────────────────────────────────────┘
                        │  ALLOW only
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Simulated Tool Layer                            │
│         payments.send │ email.send │ database.run_sql           │
│         (Only gateway.py may import these — enforced by arch)  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| **Gateway** | `backend/app/gateway.py` | Enforcement pipeline — orchestrates all checks in strict order |
| **Policy Engine** | `backend/app/policy.py` | Rule evaluation: permissions, thresholds, SQL classification, email allowlists |
| **Approvals** | `backend/app/approvals.py` | State machine: pending → approved → used/revoked/expired |
| **Audit Chain** | `backend/app/audit.py` | SHA-256 hash-chained immutable log, tamper detection |
| **Database** | `backend/app/db.py` | SQLite with WAL mode, schema init, atomic row-locks |
| **API** | `backend/app/main.py` | FastAPI routes, SSE live feed, CORS, lifespan |
| **Schemas** | `backend/app/schemas.py` | Pydantic models, canonical hashing, parameter normalization |

---

## ⚙️ Enforcement Pipeline

The gateway executes these checks **in exact order** — any failure immediately returns BLOCK:

```
POST /v1/execute
       │
       ▼
  1. Agent lookup ──────────────── BLOCK "Unknown agent: <id>"
       │
       ▼
  2. Tool registry check ────────── BLOCK "Unknown tool: <name>"
       │
       ▼
  3. Policy check
     ├─ Permission (role) ─────────── BLOCK "Agent lacks write permission"
     ├─ Destructive SQL ───────────── BLOCK "Destructive database operation prohibited"
     ├─ Payment threshold ─────────── ASK_HUMAN "Payment exceeds ₹10,000 limit"
     └─ Email domain allowlist ────── ASK_HUMAN "Sending email to unknown external domain"
       │
       ▼
  4. [If ASK_HUMAN and no approval_id] ── Create pending approval → return ASK_HUMAN
       │
       ▼
  5. [If approval_id supplied]
     ├─ a. Fetch approval row
     ├─ b. Match (agent_id, task_id, tool) ─── BLOCK "Approval does not match request"
     ├─ c. Canonical hash of sensitive params ─ BLOCK "<Field> changed after approval"
     ├─ d. Expiry check ─────────────────────── BLOCK "Approval expired"
     ├─ e. Revocation check ─────────────────── BLOCK "Approval revoked"
     └─ f. Atomic UPDATE status='used' ─────── BLOCK "Approval already used (replay)"
       │
       ▼
  6. Execute tool ─────────────────────────── ALLOW (tool runs here and ONLY here)
       │
       ▼
  7. [finally] Append to audit chain ─── always, even on error
       │
  Any exception at any point ──────────── BLOCK "Gateway error: failed closed"
```

### Decision Statuses (exactly three, everywhere in the system)

| Status | Display | Meaning |
|--------|---------|---------|
| `ALLOW` | ✅ ALLOW | All checks passed — tool executed |
| `ASK_HUMAN` | 🟡 ASK HUMAN | Human approval required — tool did NOT run |
| `BLOCK` | 🔴 BLOCK | Rule or approval violation — tool did NOT run |

---

## 🔐 Security Features

### 1. Exact Parameter Binding
Approvals are bound to a **canonical SHA-256 hash** of sensitive parameters at approval time.

```
payments.send  → hash(recipient_normalized, amount_paise, currency)
email.send     → hash(to_domain, has_attachment)
database.run_sql → hash(statement_type, table)
```

At execution time, the hash is recomputed from the actual parameters. Any change — even a single character like `"Supplier A"` → `"Supplier  A"` (double space) — produces a different hash and triggers BLOCK.

### 2. Approval State Machine

```
           create()
 pending ──────────────► approved
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
           revoked      expired    used (atomic)
```

- **Revocation** is checked at execution time (not just at approval time)
- **Expiry** uses configurable TTL (default: 10 minutes via `APPROVAL_TTL_SECONDS`)
- **Single-use**: atomic SQL `UPDATE SET status='used' WHERE status='approved' AND revoked_at IS NULL AND expires_at > now` — `rowcount != 1` → BLOCK replay

### 3. SHA-256 Merkle Audit Chain

```
hash_0 = SHA256("0"*64 + canonical_json(record_0))
hash_1 = SHA256(hash_0  + canonical_json(record_1))
hash_2 = SHA256(hash_1  + canonical_json(record_2))
...
```

- Secrets are **masked before hashing** (API keys, bearer tokens, account numbers → last-4 only)
- Appends are **serialized** via threading lock + SQLite `BEGIN IMMEDIATE`
- `GET /v1/audit/verify` recomputes the entire chain and reports the exact record where tampering occurred
- **Direct database modification** is detected immediately — even changing a single byte breaks the chain

### 4. Policy Engine

| Policy Rule | Trigger | Decision |
|-------------|---------|----------|
| Unknown agent | `agent_id` not in registry | BLOCK |
| Unknown tool | `tool` not in `{payments.send, email.send, database.run_sql}` | BLOCK |
| Read-only role | Agent with `can_write=false` calls a write tool | BLOCK |
| Destructive SQL | `DROP`, `TRUNCATE`, unbounded `DELETE` | BLOCK |
| Payment threshold | Amount > ₹10,000 without prior approval | ASK_HUMAN |
| Email allowlist | Domain not in `{internal.corp, company.com, example.com}` | ASK_HUMAN |

### 5. Fail-Closed Design
Any exception — including a gateway crash, DB timeout, or import error — results in `BLOCK "Gateway error: failed closed"`. The system **never defaults to open**.

### 6. Human-in-the-Loop Approvals
Large payments (> ₹10,000) are routed to the Human Approvals Console:
- Cryptographic single-use tokens
- Mobile-friendly approval page (English, Hindi, Kannada)
- QR code for mobile enclave access
- Supervisor can approve or reject with audit trail

---

## 📡 API Reference

### Core Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check → `{"status": "ok"}` |
| `POST` | `/v1/execute` | Main gateway enforcement |
| `GET` | `/v1/approvals` | List pending approvals |
| `POST` | `/v1/approvals/{id}/approve` | Human approves a pending request |
| `POST` | `/v1/approvals/{id}/reject` | Human rejects a pending request |
| `POST` | `/v1/approvals/{id}/revoke` | Revoke an approved token |
| `GET` | `/v1/audit` | Paginated audit log with filters |
| `GET` | `/v1/audit/verify` | Verify Merkle chain integrity |
| `GET` | `/v1/audit/export/csv` | Export audit log as CSV |
| `GET` | `/v1/live-feed` | SSE stream of real-time decisions |
| `GET` | `/v1/policies` | List all active policies |
| `GET` | `/v1/agents` | List registered agents |

### Demo Endpoints (DEMO_MODE=1 only)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/demo/reset` | Reset DB to clean state |
| `POST` | `/v1/demo/run/{scenario_id}` | Run a specific demo scenario |
| `POST` | `/v1/demo/tamper/{record_id}` | Simulate direct DB tamper (for audit demo) |

### Execute Request Format

```json
POST /v1/execute
{
  "agent_id": "accounts-agent",
  "task_id": "task-accounts-1",
  "tool": "payments.send",
  "params": {
    "recipient": "Supplier A",
    "amount": 5000.00,
    "currency": "INR"
  },
  "approval_id": "optional-uuid-if-approved"
}
```

### Execute Response Format

```json
{
  "decision": "ALLOW",
  "reason": "Request approved and executed successfully",
  "executed": true,
  "approval_id": null,
  "audit_id": 42
}
```

---

## 🛠️ Tech Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Core language |
| FastAPI | 0.111.1 | REST API + SSE live feed |
| Uvicorn | 0.30.1 | ASGI server |
| Pydantic v2 | 2.7.4 | Request/response validation |
| SQLite | Built-in | Storage (WAL mode, row-locks) |
| pytest | 8.2.2 | 110-test suite |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| React | 18 | UI framework |
| TypeScript | 5 | Type-safe components |
| Vite | 5 | Build tool + dev proxy |
| Tailwind CSS | 3 | Styling |
| React Router | 6 | Client-side routing |

### Design
- 9 desktop screens + 8 mobile screens (exported via Stitch)
- Responsive: sidebar navigation on desktop, bottom tab bar on mobile

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1. Clone

```bash
git clone https://github.com/amruthck177/Agent_Gaurd.git
cd Agent_Gaurd
```

### 2. Backend

```bash
# Create and activate virtualenv
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt

# Copy env (defaults work out of the box)
cp .env.example .env

# Start backend on port 8000
uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000

# Verify
curl http://localhost:8000/health
# → {"status":"ok"}
```

### 3. Frontend

```bash
# New terminal, from repo root
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

> The frontend proxy is pre-configured to forward all API calls to `http://127.0.0.1:8000`.

---

## 📁 Project Structure

```
Agent_Gaurd/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app, all routes, SSE live feed, CORS
│   │   ├── gateway.py       # ⭐ Enforcement pipeline (only file that may call tools)
│   │   ├── approvals.py     # Approval CRUD, state machine, canonical hashing
│   │   ├── policy.py        # Rule engine: permissions, SQL classification, thresholds
│   │   ├── audit.py         # SHA-256 Merkle chain log, verify, tamper detection
│   │   ├── db.py            # SQLite connection, WAL mode, schema init, seeding
│   │   ├── schemas.py       # Pydantic models, canonical JSON, param normalization
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── payments.py  # Simulated payment tool (no real money)
│   │       ├── email.py     # Simulated email tool (no real mail)
│   │       └── database.py  # Simulated database tool (no real DB writes)
│   ├── tests/
│   │   ├── test_security.py       # 8 core security invariants
│   │   ├── test_gateway_toctou.py # Time-of-check vs time-of-use tests
│   │   ├── test_approvals.py      # Approval state machine tests
│   │   ├── test_audit.py          # Merkle chain & tamper detection tests
│   │   ├── test_agent.py          # Agent permission tests
│   │   ├── test_api.py            # HTTP endpoint tests
│   │   ├── test_policy_and_tools.py # Policy rule tests
│   │   ├── test_schemas_and_db.py  # Schema & DB tests
│   │   ├── test_story_http.py     # End-to-end scenario tests
│   │   ├── test_sql_bypass.py     # SQL injection & bypass tests
│   │   ├── test_secrets_leak.py   # Secret masking in audit log tests
│   │   └── test_health.py         # Health check tests
│   └── pytest.ini
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx               # Router, layout
│   │   ├── main.tsx              # Entry point
│   │   ├── index.css             # Global styles + Tailwind
│   │   ├── pages/
│   │   │   ├── LiveFeed.tsx      # Real-time SSE agent activity stream
│   │   │   ├── Approvals.tsx     # Human approval console + QR code
│   │   │   ├── AuditLog.tsx      # Merkle chain viewer + tamper simulation
│   │   │   ├── Policies.tsx      # Policy viewer
│   │   │   ├── TestResults.tsx   # Benchmark results dashboard
│   │   │   ├── DemoPanel.tsx     # Interactive 10-scenario demo
│   │   │   ├── MobileApproval.tsx # Mobile enclave approval page
│   │   │   └── Styleguide.tsx    # Design system reference
│   │   ├── components/
│   │   │   ├── common/           # DecisionChip, StatCard, ParamCompare, etc.
│   │   │   └── layout/           # AppShell, Sidebar, Topbar, Drawer, etc.
│   │   ├── lib/
│   │   │   ├── api.ts            # Typed API client (all endpoints)
│   │   │   └── useEvents.ts      # SSE WebSocket hook for live feed
│   │   └── i18n/
│   │       ├── en.json           # English strings
│   │       ├── hi.json           # Hindi strings
│   │       └── kn.json           # Kannada strings
│   ├── vite.config.ts            # Dev server + proxy to :8000
│   ├── package.json
│   └── tailwind.config.js
│
├── agent/
│   ├── scripted_agent.py    # Offline scripted demo agent (runs scenarios without browser)
│   └── sdk_wrapper.py       # Agent-side SDK: fail-closed on timeout, retry logic
│
├── benchmarks/
│   ├── cases.json           # 34 test case definitions (12 legitimate + 22 violations)
│   ├── run_benchmarks.py    # Automated benchmark runner → produces results.json
│   ├── results.json         # Latest benchmark output (never edited by hand)
│   └── README.md            # Benchmark methodology
│
├── docs/
│   ├── plan.md              # Full system design, scope, methodology, test plan
│   ├── design.md            # UI design spec, colour tokens, component behaviour
│   └── openapi.json         # Complete OpenAPI 3.0 specification
│
├── design-export/           # UI screenshots (9 desktop, 8 mobile) + Stitch HTML exports
│
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies (pinned versions)
└── README.md
```

---

## 🧪 Testing

### Run all tests

```bash
# From repo root, with venv active
pytest backend/tests/ -v
```

### Test categories (110 tests total)

| Test File | Coverage |
|-----------|----------|
| `test_security.py` | 8 core security invariants (recipient change, amount change, expiry, revocation, read-only, replay, threshold, fail-closed) |
| `test_gateway_toctou.py` | Time-of-check vs time-of-use race conditions |
| `test_approvals.py` | State machine: all valid and invalid transitions |
| `test_audit.py` | Merkle chain construction, verification, tamper detection |
| `test_agent.py` | Agent registry, role permissions, task scoping |
| `test_api.py` | All HTTP endpoints, status codes, response schemas |
| `test_policy_and_tools.py` | All policy rules, SQL classifier, email allowlist |
| `test_schemas_and_db.py` | Canonical hashing, parameter normalization, DB operations |
| `test_story_http.py` | End-to-end HTTP scenarios (the full demo flow) |
| `test_sql_bypass.py` | SQL injection, obfuscated destructive commands |
| `test_secrets_leak.py` | API keys, bearer tokens, account numbers masked in audit |
| `test_health.py` | Health endpoint, CORS headers |

### Run benchmarks

```bash
python benchmarks/run_benchmarks.py
# Results saved to benchmarks/results.json
```

---

## 📊 Benchmark Results

Automated benchmark over **34 test cases** (12 legitimate + 22 attack scenarios):

| Metric | Result |
|--------|--------|
| **Test cases run** | 34 |
| **Legitimate cases** | 12 — all correctly ALLOWED |
| **Attack scenarios** | 22 — all correctly BLOCKED or ASK_HUMAN |
| **Unauthorized tool executions** | **0** |
| **Mismatch detection rate** | **100.0%** |
| **False block rate** | **0.0%** |
| **Mean added latency** | 198 ms |
| **P95 added latency** | 221 ms |
| **Audit chain verify** | ✅ PASS |
| **Tamper detection** | ✅ PASS (detected at record #2) |

### All 8 Security Invariants — PASS

| # | Invariant | Result |
|---|-----------|--------|
| 1 | Changed recipient blocked | ✅ PASS |
| 2 | Changed amount blocked (even +1 paise) | ✅ PASS |
| 3 | Expired approval blocked | ✅ PASS |
| 4 | Revoked approval blocked | ✅ PASS |
| 5 | Read-only agent write blocked | ✅ PASS |
| 6 | Replay attack blocked | ✅ PASS |
| 7 | Over-threshold routed to human | ✅ PASS |
| 8 | Gateway failure → fail closed | ✅ PASS |

### Attack Scenarios Tested

| Category | Examples |
|----------|---------|
| **Recipient substitution** | Supplier A → Supplier B, whitespace injection, suffix spoofing ("Supplier A Ltd") |
| **Amount manipulation** | +1 paise inflation, 10× inflation, reduction |
| **Currency swap** | INR → USD |
| **Token attacks** | Expired, revoked, replayed, wrong agent, wrong task, wrong tool |
| **Permission bypass** | Read-only agent write, cross-task approval hijacking |
| **SQL injection** | DROP TABLE, TRUNCATE, unbounded DELETE, obfuscated commands |
| **Email exfiltration** | Unknown external domain routing |
| **Rogue agent** | Unregistered agent_id, unknown tool name |

---

## ⚠️ Known Limitations

These are documented scope boundaries — not bugs:

1. **SQLite only** — Reference implementation uses SQLite with WAL mode. Production requires PostgreSQL + distributed locking (Redis/Redlock) for multi-node deployments.

2. **No mTLS / workload identity** — `agent_id` is passed as structured request metadata. Production requires signed JWT, mTLS, or SPIFFE workload identity.

3. **Hash-chain only (no external notary)** — Audit integrity uses SHA-256 chaining. Production roadmap adds asymmetric Ed25519 signing + external append-only notaries (Sigstore/Rekor).

4. **Single-tenant** — Reference uses logical agent/task boundaries in one SQLite file. Production requires physical schema separation or tenant-isolated instances.

5. **Simulated tools** — All tools (payments, email, database) are mock functions. No real money moves, no real email is sent, no real database is written.

6. **No rate limiting** — No per-agent request rate limiting. Production needs API gateway-level rate limits.

---

## 👥 Team

**Team LogicLords** — Yenepoya Institute of Technology, Thodar, Moodbidri

| Person | Role |
|--------|------|
| **Amruth CK** *(Leader)* | Gateway enforcement pipeline, approval binding, TOCTOU protection, replay defence |
| **Mustafa Fazil** | SHA-256 Merkle audit chain, test suite, benchmark script |
| **Rajesh Gouda** | React frontend, WebSocket/SSE live feed, responsive design |
| **Adbuth Joshva D P** | Demo agent, mock tools, policies, demo video, documentation |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**AgentGuard 2.0** · DevHack 2026 · Team LogicLords

*Built to answer one question: how do you trust an AI agent with your money?*

</div>
