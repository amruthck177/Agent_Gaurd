<div align="center">

# 🛡️ AgentGuard 2.0

### Deterministic Security Gateway for Autonomous AI Agents

**Every Action. Every Agent. Every Time.**

[![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue?logo=typescript)](https://www.typescriptlang.org/)
[![Tests](https://img.shields.io/badge/Tests-110%20passed-brightgreen)](#-testing)
[![Defense Rate](https://img.shields.io/badge/Defense%20Rate-100%25-brightgreen)](#-benchmark-results)
[![False Blocks](https://img.shields.io/badge/False%20Blocks-0.0%25-brightgreen)](#-benchmark-results)

> DevHack 2026 · Team LogicLords · Yenepoya Institute of Technology · PS 2.1 — AI Agent Safety and Control

</div>

---

## 📋 Table of Contents

- [The Problem](#-the-problem)
- [The Solution](#-the-solution)
- [Methodology & Security Model](#-methodology--security-model)
- [Live Demo Scenario](#-live-demo-scenario)
- [System Architecture](#-system-architecture)
- [Enforcement Pipeline](#-enforcement-pipeline)
- [Security Guarantees & Features](#-security-guarantees--features)
- [API Reference](#-api-reference)
- [Tech Stack](#-tech-stack)
- [Quick Start Guide](#-quick-start-guide)
- [Project Structure](#-project-structure)
- [Testing](#-testing)
- [Benchmark Results](#-benchmark-results)
- [Commit History & Changelog](#-commit-history--changelog)
- [Known Limitations & Scope Boundaries](#-known-limitations--scope-boundaries)
- [Team](#-team)
- [License](#-license)

---

## ❗ The Problem

Autonomous AI agents are increasingly entrusted with sensitive operations: executing bank transfers, emailing external vendors, and modifying production databases. While human-in-the-loop approval workflows exist, they suffer from a fundamental architectural vulnerability:

| Vulnerability | Attack / Failure Mode | Real-World Consequence |
|---|---|---|
| **Approval of Description, Not Parameters** | Human approves *"Pay Supplier A ₹5,000"*, but the agent submits `recipient: "Supplier B"` | Unauthorized capital drain; fund diversion |
| **Time-of-Check vs. Time-of-Use (TOCTOU)** | Between human approval and tool execution, parameters are altered in-memory | Silent invoice tampering; inflated payment amounts |
| **Prompt Injection & Model Drift** | A poisoned invoice or confused reasoning alters the downstream tool parameters | An approved task executes a completely unintended payload |
| **Replay & Stale Token Reuse** | A single approval token is reused across multiple execution cycles | Double-spending or repeated unauthorized database edits |
| **Over-Privileged Roles** | Read-only reporting agents invoke mutating tools or issue destructive queries | Accidental or malicious database loss (`DROP TABLE`, `TRUNCATE`) |
| **Malleable Audit Logs** | Application logs are stored in standard mutable files or database tables | Inability to prove non-repudiation or detect insider tampering |

**The Core Threat:** Humans approve what an agent *claims* it will do, but traditional architectures have no deterministic mechanism ensuring the agent does *only and exactly that*.

---

## ✅ The Solution

**AgentGuard 2.0** is an out-of-process, deterministic security gateway. Every sensitive agent tool call is intercepted and validated against strict cryptographic invariants before any tool execution occurs.

> *"The model cannot talk its way past the gateway."*

### Key Operating Principles:
1. **Deterministic Enforcement Outside the LLM:** Security rules run in verified backend code, completely insulated from prompt injection, jailbreaks, or model hallucinations.
2. **Exact Parameter Cryptographic Binding:** Approvals are cryptographically tied to a canonical hash of tool parameters. If even one character or paise differs, execution is blocked immediately.
3. **Execution-Time Re-validation:** Expiry, revocation, and permission scopes are evaluated at the exact millisecond of execution, eliminating TOCTOU windows.
4. **Atomic Single-Use State Transitions:** Approvals transition from `approved` to `used` via atomic database operations, preventing concurrent and sequential replay attacks.
5. **Fail-Closed Default:** Any unexpected exception, timeout, or network partition causes the gateway to halt and return `BLOCK`. The system never defaults to open.
6. **Cryptographic Tamper-Evident Audit Chain:** All gateway decisions are appended to an immutable SHA-256 Merkle chain, providing instant mathematical verification of log integrity.

---

## 🔬 Methodology & Security Model

AgentGuard enforces a multi-tier defense-in-depth model across the entire tool invocation lifecycle:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            METHODOLOGY LIFECYCLE                                 │
│                                                                                  │
│   [Agent Intent]  ──►  [Pre-Execution Policy]  ──►  [Human Enclave Escalation]   │
│                                                            │                     │
│                                                            ▼                     │
│   [Tool Execution] ◄── [Atomic State Lock] ◄── [Canonical Hash Verification]     │
│          │                                                                       │
│          ▼                                                                       │
│   [SHA-256 Merkle Audit Append] ──► [Real-Time WebSocket / SSE Broadcast]       │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 1. Zero-Trust Gateway Interception
Agents are never provisioned with direct tool credentials (database passwords, banking API keys, SMTP credentials). The gateway is the sole orchestrator holding tool access. An agent proposes an execution request via `POST /v1/execute`:
```json
{
  "agent_id": "accounts-agent",
  "task_id": "task-accounts-1",
  "tool": "payments.send",
  "params": {
    "recipient": "Supplier A",
    "amount": 5000.0,
    "currency": "INR"
  },
  "approval_id": "optional-uuid"
}
```

### 2. Canonical Parameter Normalization (RFC 8785)
To eliminate semantic mismatches (e.g., whitespace variations, floating-point inaccuracies, or unordered JSON keys), the gateway normalizes sensitive parameters into a canonical representation:
- **String Fields:** Whitespace trimmed and case-normalized.
- **Monetary Amounts:** Converted to integer minor units (paise) to eradicate IEEE 754 floating-point ambiguity.
- **JSON Serialization:** Sorted lexicographical keys without extraneous whitespace.
- **Approved Hash:** `SHA-256(canonical_json(sensitive_params))`

### 3. Policy & Escalation Matrix
Requests are classified by a deterministic policy engine into three unambiguous states:

| Decision | State Representation | Gateway Action |
|---|---|---|
| `ALLOW` | 🟢 Passes all constraints | Executes tool immediately; logs execution proof |
| `ASK_HUMAN` | 🟡 Exceeds threshold / unlisted domain | Creates pending approval; halts execution |
| `BLOCK` | 🔴 Violates policy / tampering detected | Aborts immediately; zero tool execution; audit logged |

### 4. Concurrency & TOCTOU Defense
To guarantee that approvals cannot be replayed or raced across concurrent worker threads, state transitions use atomic conditional SQL updates:
```sql
UPDATE approvals
SET status = 'used', used_at = :now
WHERE id = :approval_id
  AND status = 'approved'
  AND revoked_at IS NULL
  AND expires_at > :now;
```
If two identical requests arrive simultaneously, the SQLite row-level lock ensures exactly one query updates a row (`rowcount == 1`). The competing request receives `rowcount == 0` and is immediately `BLOCKED` as a replay attempt.

### 5. SHA-256 Merkle Hash Chain Audit
Every decision (allowed, escalated, or blocked) produces an immutable audit record chained cryptographically to the prior block:
```python
# Genesis record uses 64 zeros as the previous hash
hash_0 = SHA256("0" * 64 + canonical_json(record_0))
hash_n = SHA256(hash_{n-1} + canonical_json(record_n))
```
- **Secret Redaction:** Passwords, API tokens, and sensitive account details are masked *before* hashing.
- **Tamper Detection:** `GET /v1/audit/verify` recalculates the entire chain from block 0. If a single byte in the database is modified by an attacker, verification fails and flags the exact record ID.

---

## 🎬 Live Demo Scenario

The canonical demonstration scenario showcases complete protection against in-flight parameter alteration:

1. **Escalation:** The agent requests a payment of ₹5,000 to `Supplier A`. The human supervisor approves the request in the console.
2. **Tampering Attempt:** A confused or compromised agent attempts to reuse the approval token, submitting `recipient: "Supplier B"`.
3. **Gateway Interception:** AgentGuard recomputes the canonical parameter hash:
   - Approved hash: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
   - Attempted hash: `a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e`
4. **Immediate Block:** Returns `BLOCK: "Recipient changed after approval"`.
5. **Verified Containment:** The payment tool execution counter remains **`0`**.
6. **Audit Proof:** The tampering attempt is permanently recorded in the hash chain with full diagnostic diffs.
7. **Legitimate Execution:** The unchanged payment to `Supplier A` is resubmitted and successfully executes (`ALLOW`).

---

## 🏗️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                              AI Agent                                  │
│             (Generates tool calls; holds zero credentials)             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │  POST /v1/execute
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         AgentGuard Gateway                             │
│                                                                        │
│   ┌────────────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│   │ Agent Registry │    │  Policy Engine  │    │  Approval Store  │    │
│   │ • Identity     │    │ • Permissions   │    │ • Exact Binding  │    │
│   │ • Role Checks  │    │ • SQL Sanitizer │    │ • Expiry / TTL   │    │
│   │ • Task Scope   │    │ • Thresholds    │    │ • Atomic Lock    │    │
│   └────────────────┘    └─────────────────┘    └──────────────────┘    │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                 Tamper-Evident SHA-256 Chain                   │   │
│   │     record_n.hash = SHA256(prev_hash + canonical_json(n))      │   │
│   └────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │  ALLOW only
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Simulated Tool Layer                            │
│           payments.send  │  email.send  │  database.run_sql            │
│         (Importable only by gateway.py — zero external bypass)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         Frontend Dashboard                             │
│       React 18 · TypeScript · Vite · SSE Real-Time Event Stream        │
│    Live Feed │ Approvals Enclave │ Policy Console │ Audit Inspector    │
└────────────────────────────────────────────────────────────────────────┘
```

### Module Responsibilities

| Subsystem | File Location | Responsibility |
|---|---|---|
| **Enforcement Gateway** | `backend/app/gateway.py` | Central pipeline orchestrator; executes validation steps in strict sequence |
| **Policy Engine** | `backend/app/policy.py` | Evaluates RBAC permissions, financial thresholds, destructive SQL, and email allowlists |
| **Approval Lifecycle** | `backend/app/approvals.py` | Manages state machine (`pending` → `approved` → `used`/`revoked`/`expired`) and canonical hashing |
| **Cryptographic Audit** | `backend/app/audit.py` | Merkle chain hashing, secret scrubbing, and full integrity re-verification |
| **Database Layer** | `backend/app/db.py` | SQLite connection manager with WAL mode, schema migrations, and test fixture seeding |
| **API Endpoints** | `backend/app/main.py` | FastAPI application, REST endpoints, SSE stream, and CORS configuration |
| **Type Schemas** | `backend/app/schemas.py` | Pydantic data models, parameter canonicalization, and serialization logic |
| **Sandboxed Tools** | `backend/app/tools/` | Mock implementations of payment, email, and SQL execution engines |

---

## ⚙️ Enforcement Pipeline

Every request arriving at `POST /v1/execute` traverses an unbroken sequence of validation gates. If any gate fails, the pipeline aborts immediately with `BLOCK`:

```
Incoming Request
       │
       ▼
 1. Agent Verification ────────────── BLOCK "Unknown agent: <id>"
       │
       ▼
 2. Tool Registry Check ───────────── BLOCK "Unknown tool: <name>"
       │
       ▼
 3. Policy Engine Evaluation
    ├─ Role-Based Access ──────────── BLOCK "Agent lacks write permission"
    ├─ Destructive SQL Check ──────── BLOCK "Destructive database operation prohibited"
    ├─ Financial Limit (> ₹10,000) ── ASK_HUMAN "Payment exceeds ₹10,000 limit"
    └─ Email Domain Validation ────── ASK_HUMAN "Sending email to unknown external domain"
       │
       ▼
 4. Human Approval Gate
    ├─ [No approval token supplied] ─ Create pending approval → Return ASK_HUMAN
    └─ [Approval token supplied]
       ├─ Token Existence Check ───── BLOCK "Approval does not match request"
       ├─ Agent / Task / Tool Match ─ BLOCK "Approval does not match request"
       ├─ Canonical Parameter Hash ── BLOCK "<Field> changed after approval"
       ├─ Expiry Check ────────────── BLOCK "Approval expired"
       ├─ Revocation Check ────────── BLOCK "Approval revoked"
       └─ Atomic Lock Acquisition ─── BLOCK "Approval already used (replay)"
       │
       ▼
 5. Tool Invocation ───────────────── ALLOW (Tool runs here and ONLY here)
       │
       ▼
 6. Cryptographic Audit Append ────── Always executed in finally block
       │
 Any uncaught runtime exception ───── BLOCK "Gateway error: failed closed"
```

---

## 🔐 Security Guarantees & Features

### 1. Invariant Defense Against TOCTOU
Approvals store both a human-readable snapshot and a canonical SHA-256 hash. When an agent invokes the gateway with an approval ID, the gateway reconstructs the canonical hash of the inbound parameters and verifies strict equality. Any modification—such as appending spaces, altering currency codes, or shifting cents—causes instant termination.

### 2. Destructive SQL Classification
The SQL policy gate analyzes incoming SQL statements using regex and syntax pattern matching:
- **Prohibited:** Any query containing `DROP`, `TRUNCATE`, or `DELETE` without an explicit `WHERE` clause.
- **Allowed:** Standard parameterized `SELECT`, `INSERT`, and constrained `UPDATE` queries.

### 3. Masked Audit Trail
All payloads sent to the audit logger are sanitized before hashing and persistence:
- Credit card / Account numbers: Masked except for the last 4 digits (`****1234`).
- Bearer tokens & API keys: Completely redacted (`[REDACTED]`).

### 4. Human Approval Enclave
High-risk actions generate human-readable approval tickets:
- Accessible via desktop dashboard or mobile enclave view (`/approvals`).
- Fully localized with multi-lingual UI support (**English**, **Hindi**, **Kannada**).
- Includes instant QR-code mobile pairing.

---

## 📡 API Reference

### Core Gateway Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/health` | System health check (`{"status": "ok"}`) |
| `POST` | `/v1/execute` | Main gateway entrypoint for agent tool invocation |
| `GET` | `/v1/approvals` | List pending, approved, or expired approval tokens |
| `POST` | `/v1/approvals/{id}/approve` | Human supervisor authorizes a pending request |
| `POST` | `/v1/approvals/{id}/reject` | Human supervisor rejects a pending request |
| `POST` | `/v1/approvals/{id}/revoke` | Revokes an existing valid approval token |
| `GET` | `/v1/audit` | Paginated query of the Merkle audit chain |
| `GET` | `/v1/audit/verify` | Recomputes entire SHA-256 chain; reports integrity status |
| `GET` | `/v1/audit/export/csv` | Exports complete audit trail in standard CSV format |
| `GET` | `/v1/live-feed` | Server-Sent Events (SSE) live feed of real-time decisions |
| `GET` | `/v1/policies` | Retrieve all active gateway security policies |
| `GET` | `/v1/agents` | List registered agent identities and permissions |

### Demo / Benchmark Endpoints (`DEMO_MODE=1`)

| Method | Route | Description |
|---|---|---|
| `POST` | `/v1/demo/reset` | Resets the SQLite database to clean seeded state |
| `POST` | `/v1/demo/run/{scenario_id}` | Triggers a pre-canned attack or legitimate scenario |
| `POST` | `/v1/demo/tamper/{record_id}` | Mutates a historical audit record in SQLite to demonstrate tamper detection |
| `GET` | `/v1/tests/results` | Serves official benchmark execution output |

---

## 🛠️ Tech Stack

### Backend
- **Python 3.11+** — High-performance asynchronous backend runtime
- **FastAPI 0.111.1** — OpenAPI-compliant web framework with Server-Sent Events support
- **Uvicorn 0.30.1** — Production-grade ASGI server
- **Pydantic v2 (2.7.4)** — High-speed deterministic data validation
- **SQLite 3 (WAL Mode)** — Embedded ACID storage with write-ahead logging and zero external setup
- **pytest 8.2.2** — Automated testing framework

### Frontend
- **React 18** — Reactive component architecture
- **TypeScript 5** — End-to-end static type safety
- **Vite 5** — Ultra-fast build pipeline with automated local reverse-proxy
- **Tailwind CSS 3** — Modern design system with responsive layouts
- **Lucide Icons** — Consistent visual iconography

---

## 🚀 Quick Start Guide

Run AgentGuard locally on any machine in under 3 minutes. Zero external dependencies (no Docker, no Redis, no external SQL server required).

### Prerequisites
- **Python 3.11+** installed
- **Node.js 18+** & **npm** installed

```bash
# Terminal 1 — Backend Setup & Launch
# 1. Clone the project repository from GitHub
git clone https://github.com/amruthck177/Agent_Gaurd.git

# 2. Navigate to the project root directory
cd Agent_Gaurd

# 3. Create an isolated Python virtual environment
python -m venv venv

# 4. Activate the virtual environment
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 5. Install all backend dependencies (FastAPI, Uvicorn, Pydantic, pytest)
pip install -r requirements.txt

# 6. Copy the environment configuration template (safe local defaults)
cp .env.example .env

# 7. Start the FastAPI gateway server on localhost:8000 with auto-reload
uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000

# Terminal 2 — Frontend Setup & Launch
# 1. Navigate to the frontend directory
cd frontend

# 2. Install all Node.js dependencies
npm install

# 3. Start the Vite development server (proxies API requests to port 8000)
npm run dev

# 4. Access the web security console in your browser
# → Open http://localhost:5173
```

> **Note:** The frontend automatically proxies all `/v1` and `/health` requests to the backend at `http://127.0.0.1:8000`.

---

## 📁 Project Structure

```
Agent_Gaurd/
├── .env.example                 # Environment variable template with safe defaults
├── .gitignore                   # Git exclusion rules (no cache, DB, or media)
├── README.md                    # Comprehensive system documentation
├── requirements.txt             # Pinned Python dependencies
├── results.txt                  # Automated benchmark output values
│
├── backend/                     # Core Gateway Engine
│   ├── app/
│   │   ├── main.py              # FastAPI app, API routers, SSE event emitter
│   │   ├── gateway.py           # ⭐ Enforcement pipeline (sole tool invoker)
│   │   ├── approvals.py         # Approval state machine & canonical hashing
│   │   ├── policy.py            # RBAC, SQL classification, financial policies
│   │   ├── audit.py             # SHA-256 Merkle chain, verify, tamper detection
│   │   ├── db.py                # SQLite WAL connection, migrations, seeding
│   │   ├── schemas.py           # Pydantic schemas, normalization logic
│   │   └── tools/               # Isolated tool adapters
│   │       ├── payments.py      # Simulated payment execution
│   │       ├── email.py         # Simulated email gateway
│   │       └── database.py      # Simulated SQL execution
│   ├── tests/                   # Comprehensive 110-test suite
│   │   ├── test_security.py     # 8 core security invariants
│   │   ├── test_gateway_toctou.py # TOCTOU & parameter tampering tests
│   │   ├── test_approvals.py    # Approval lifecycle & replay tests
│   │   ├── test_audit.py        # Merkle chain & cryptographic tamper tests
│   │   ├── test_agent.py        # Role & permission enforcement tests
│   │   ├── test_api.py          # HTTP contract & response tests
│   │   ├── test_policy_and_tools.py # Policy rule logic tests
│   │   ├── test_schemas_and_db.py # Canonical serialization tests
│   │   ├── test_story_http.py   # Full end-to-end attack scenario tests
│   │   ├── test_sql_bypass.py   # SQL injection & bypass defense tests
│   │   ├── test_secrets_leak.py # Secret redaction tests
│   │   └── test_health.py       # Health check tests
│   └── pytest.ini               # Pytest configuration
│
├── frontend/                    # Modern Security Console
│   ├── src/
│   │   ├── App.tsx              # Application layout & page routing
│   │   ├── main.tsx             # Entrypoint
│   │   ├── index.css            # Custom CSS & Tailwind styles
│   │   ├── pages/
│   │   │   ├── LiveFeed.tsx     # Real-time SSE event activity monitor
│   │   │   ├── Approvals.tsx    # Human escalation console & QR enclave
│   │   │   ├── AuditLog.tsx     # SHA-256 Merkle log & tamper simulation
│   │   │   ├── Policies.tsx     # Security policy management console
│   │   │   ├── TestResults.tsx  # Interactive test & benchmark dashboard
│   │   │   ├── DemoPanel.tsx    # 10-scenario interactive attack demo
│   │   │   ├── MobileApproval.tsx # Responsive mobile approval interface
│   │   │   └── Styleguide.tsx   # Component design system reference
│   │   ├── components/          # Reusable UI components
│   │   │   ├── common/          # DecisionChip, StatCard, ParamCompare, etc.
│   │   │   └── layout/          # AppShell, Sidebar, Topbar, Drawer, etc.
│   │   ├── lib/
│   │   │   ├── api.ts           # Typed API client
│   │   │   └── useEvents.ts     # Real-time Server-Sent Events hook
│   │   └── i18n/                # Multi-language translations (en, hi, kn)
│   ├── package.json             # NPM dependencies
│   ├── tailwind.config.js       # Design tokens & color palette
│   └── vite.config.ts           # Dev server config & reverse proxy
│
├── agent/                       # Agent SDK & Demo Harness
│   ├── scripted_agent.py        # Autonomous agent test runner
│   └── sdk_wrapper.py           # Client-side agent gateway wrapper
│
├── benchmarks/                  # Verification & Benchmark Suite
│   ├── cases.json               # 34 attack and legitimate test cases
│   ├── run_benchmarks.py        # Benchmark execution script
│   ├── results.json             # Structured benchmark metrics output
│   └── README.md                # Benchmark methodology documentation
│
└── docs/                        # Architecture & Design Specifications
    ├── api-contract.md          # Formal API contract
    ├── design.md                # Frontend design guidelines & tokens
    ├── openapi.json             # OpenAPI 3.0 specification
    └── plan.md                  # Comprehensive engineering design document
```

---

## 🧪 Testing

The codebase features an exhaustive, fully-automated test suite covering 110 unit, integration, and security test cases.

### Running the Test Suite
Ensure your virtual environment is active, then execute:

```bash
pytest backend/tests/ -v
```

### Test Coverage Highlights

| Test Module | Test Focus |
|---|---|
| `test_security.py` | Validates all 8 core security invariants (parameter change, amount change, expiry, revocation, RBAC, replay, thresholds, fail-closed) |
| `test_gateway_toctou.py` | Time-of-check vs. time-of-use attack scenarios and whitespace/character obfuscation |
| `test_approvals.py` | Complete state machine transitions, invalid status transitions, and race condition defenses |
| `test_audit.py` | Cryptographic Merkle chain computation, back-pointer integrity, and automated tamper detection |
| `test_agent.py` | Agent authentication, permission scoping, and cross-task approval hijacking defense |
| `test_api.py` | Complete validation of all HTTP REST routes, input validation, and HTTP error codes |
| `test_policy_and_tools.py` | Policy threshold validation, destructive SQL filtering, and email allowlisting |
| `test_sql_bypass.py` | Advanced SQL injection patterns, multi-statement injection, and obfuscated keywords |
| `test_secrets_leak.py` | Scans database and logs to ensure credentials and account numbers are strictly scrubbed |
| `test_story_http.py` | End-to-end simulation of the primary pitch demo via live HTTP calls |

---

## 📊 Benchmark Results

AgentGuard incorporates an automated benchmark runner (`benchmarks/run_benchmarks.py`) executing **34 comprehensive test cases** (12 legitimate operations + 22 active attack vectors):

```
======================================================================
                     AGENTGUARD BENCHMARK REPORT
======================================================================
  Total Test Cases Executed : 34
  Legitimate Operations     : 12 (100% Correctly Allowed)
  Attack / Violation Scenarios: 22 (100% Correctly Blocked / Escalated)
  Unauthorized Tool Calls   : 0 (Zero Unauthorized Executions)
  Mismatch Detection Rate   : 100.0%
  False Block Rate          : 0.0%
  Mean Gateway Latency      : 198 ms
  P95 Gateway Latency       : 221 ms
  Audit Chain Verification  : PASS (Valid Cryptographic Linkage)
  Tamper Detection Check    : PASS (Mutation accurately detected at record #2)
======================================================================
```

### Verification of Core Security Invariants

| Invariant # | Security Guarantee | Result | Verification Proof |
|---|---|---|---|
| **INV-1** | Altered recipient blocked | ✅ **PASS** | Hash mismatch triggers immediate `BLOCK`; zero tool execution |
| **INV-2** | Altered amount blocked | ✅ **PASS** | Even a 1-paise inflation triggers immediate `BLOCK` |
| **INV-3** | Expired approval blocked | ✅ **PASS** | Requests post-TTL rejected at execution time |
| **INV-4** | Revoked approval blocked | ✅ **PASS** | Supervisor-revoked tokens rejected at execution time |
| **INV-5** | Read-only agent write blocked | ✅ **PASS** | Unprivileged agents prevented from invoking mutating tools |
| **INV-6** | Replay / duplicate blocked | ✅ **PASS** | Atomic SQL update ensures single-use token lifecycle |
| **INV-7** | High-value actions escalated | ✅ **PASS** | Transactions > ₹10,000 automatically routed to human approval |
| **INV-8** | Fail-closed on system error | ✅ **PASS** | Gateway exceptions immediately resolve to `BLOCK` |

---

## 📜 Commit History & Changelog

| Commit Hash | Type | Commit Message | Scope & Purpose |
|---|---|---|---|
| `33c565a` | `docs` | `docs: streamline Quick Start guide with concise two-terminal setup commands` | Updated README Quick Start section with ready-to-run two-terminal guide |
| `a1aba87` | `docs` | `docs: expand README with detailed methodology, zero-trust model, and benchmarks` | Comprehensive architecture, zero-trust lifecycle, threat model, and benchmarks |
| `77e1612` | `docs` | `docs: comprehensive README with architecture, enforcement pipeline, API reference, benchmarks` | Initial comprehensive system documentation and test suite breakdown |
| `8a969fb` | `docs` | `docs: update README with complete clone-and-run setup instructions` | Added clone-and-run instructions and dependency checklists |
| `205fa1b` | `feat` | `feat: add React frontend, fix DecisionChip types, update .gitignore for clean repo` | Integrated React 18 console, fixed TypeScript types, and cleaned repo exclusions |
| `7faa337` | `freeze` | `backend-frozen: API contract, OpenAPI spec, B7 HTTP story test, B6 CORS/demo checks` | Finalized core backend contract, OpenAPI spec, and end-to-end HTTP tests |
| `720d93e` | `chore` | `chore: update benchmark results artifact` | Updated automated benchmark metrics report and results artifact |
| `5a5faaf` | `docs` | `docs: document Known Limitations and production roadmap (R1)` | Documented architectural boundaries, SQLite scope, and production roadmap |
| `5b7074d` | `fix` | `fix(security): R3 re-read approval on atomic update failure to prevent TOCTOU reason mismatch` | Fixed race condition state re-read on atomic update failures |
| `8aab323` | `fix` | `fix(security): R2+R4 scrub secrets from 500 responses and logs` | Sanitized credentials, tokens, and account numbers from logs and error payloads |
| `452ce2b` | `fix` | `fix(security): R5 mitigate SQL CTE and comment/stacked statement bypass` | Enhanced SQL classification against stacked injection, comments, and CTE bypasses |
| `155693a` | `feat` | `feat: checkpoint baseline before security audit fixes` | Baseline checkpoint of gateway, policy engine, and approvals store |
| `80f1ab0` | `chore` | `chore: workspace setup` | Initial repository scaffolding and project directory setup |

---

## ⚠️ Known Limitations & Scope Boundaries

AgentGuard is a focused hackathon reference implementation designed for PS 2.1. The following boundaries are documented design choices:

1. **Embedded SQLite:** Employs SQLite with Write-Ahead Logging (WAL) for zero-setup execution. Production deployments require PostgreSQL with distributed row locking.
2. **Workload Identity:** Agent identity is passed as structured request metadata (`agent_id`). Production deployments should integrate mTLS or SPIFFE workload identities.
3. **Simulated Tool Execution:** Included tools (`payments.send`, `email.send`, `database.run_sql`) are simulated mock adapters to ensure safe local reproducibility without risking real capital or credentials.
4. **Local Merkle Chain:** The audit chain is hosted locally in SQLite. Production systems would publish periodic Merkle roots to public append-only ledgers (e.g., Sigstore Rekor).

---

## 👥 Team

**Team LogicLords** · Yenepoya Institute of Technology, Thodar, Moodbidri  
*DevHack 2026 · Problem Statement 2.1 — AI Agent Safety and Control*

| Team Member | Role | Core Contributions |
|---|---|---|
| **Amruth CK** *(Leader)* | Lead Systems & Security Architect | Gateway pipeline, exact parameter binding, TOCTOU defense, atomic state transitions |
| **Mustafa Fazil** | Security & Cryptography Engineer | SHA-256 Merkle audit chain, tamper detection engine, test suite & benchmark suite |
| **Rajesh Gouda** | Frontend Architect | React 18 console, SSE real-time stream integration, responsive UI, localization |
| **Adbuth Joshva D P** | Agent & Tool Integrations | Demo agent simulation, policy engine, sandboxed mock tools, technical documentation |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<div align="center">

**AgentGuard 2.0** · DevHack 2026 · Team LogicLords  
*Built to answer one question: How do you trust an AI agent with your money?*

</div>
