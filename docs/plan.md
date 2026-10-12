# AgentGuard 2.0: Complete Project Plan

**Team LogicLords:** Rajesh Gouda · Mustafa Fazil · Adbuth Joshva D P · Amruth CK (leader)
**College:** Yenepoya Institute of Technology, Thodar, Moodbidri
**Event:** DevHack 2026, Sahyadri, Mangaluru (DEVHOST) · **Problem statement:** PS 2.1 AI Agent Safety and Control
**Companion file:** `design.md` (visual design). This file is the full idea, scope, build plan, tests and delivery plan.

---

## Part A. The idea

### A1. Elevator pitch
> AI agents can now pay suppliers, email customers and edit databases. Humans can approve what an agent *says* it will do, but nothing guarantees the agent then does *exactly that*. **AgentGuard is a gateway that every sensitive agent action must pass through. Approvals are bound to the exact approved parameters, expire, can be revoked, and work only once. Anything that differs is blocked before the tool runs, and every decision goes into a tamper-evident log.**

### A2. The one demo that sells it
1. A human approves **"pay Supplier A ₹5,000"**.
2. The agent (compromised or confused) tries to pay **Supplier B ₹5,000** using that approval.
3. AgentGuard returns **BLOCK: "Recipient changed after approval"**.
4. The payment tool's execution counter is still **0**.
5. The audit log shows the record, reason and hashes.
6. The unchanged approved payment to Supplier A **succeeds**.

If a judge remembers only one thing, it is this.

### A3. Problem
| Problem | What goes wrong today |
|---|---|
| Approval of a description, not of parameters | Between approval and execution the payee or amount can change (time-of-check vs time-of-use) |
| Prompt injection and drift | A malicious invoice email or a confused agent changes the action |
| Stale or reused approvals | Expired, withdrawn or replayed approvals still work |
| Over-broad permissions | A read-only agent can write, or an agent exceeds its task |
| Untrustworthy logs | After an incident, logs can be edited, so nothing is provable |

**Who feels it:** small businesses and small finance or operations teams adopting agents without a security team (example: a Mangaluru seafood exporter whose accounts agent pays ice and packaging suppliers).

### A4. Solution principles
1. **Enforcement in code, outside the LLM.** The model cannot talk its way past the gateway.
2. **Every sensitive call goes through the gateway.** There is no direct path from agent to tool.
3. **Exact-parameter binding.** Approval = a specific tool, agent, task and parameter set.
4. **Checks happen at execution time**, not just when approval was granted.
5. **Fail closed.** Error, timeout or gateway outage means BLOCK.
6. **Evidence.** Every decision is logged in a hash chain you can verify.
7. **Honesty.** Mock tools are labelled simulated. Metrics come from a script, not from typing.

### A5. Decisions (the only three statuses, everywhere)
| Decision | Meaning |
|---|---|
| `ALLOW` | Passes all checks; the tool runs |
| `ASK_HUMAN` (shown "ASK HUMAN") | Needs a human approval first; the tool does not run |
| `BLOCK` | Violates a rule or approval; the tool does not run |

---

## Part B. Scope (be exact in the deck and video)

| Capability | Status |
|---|---|
| Enforcement gateway; all sensitive calls routed through it | **Implemented** |
| Approval bound to exact parameters | **Implemented** |
| Expiry, revocation, one-time use (replay/duplicate protection) | **Implemented** |
| Per-agent and per-task permissions (read-only vs write) | **Implemented** |
| Policy rules (payment > ₹10,000 → ASK HUMAN; `DROP TABLE` → BLOCK; unknown external email domain → ASK HUMAN) | **Implemented** |
| SHA-256 hash-chained audit log, verify endpoint, tamper detection | **Implemented** |
| Live dashboard: feed, approvals, policies, audit, demo panel, test results | **Implemented** |
| 30+ case test suite with measured metrics | **Implemented** |
| Email, database, payment tools | **Simulated** (mock functions, no real money or mail) |
| Phone-style approval page in English, Hindi, Kannada | **Simulated** (static strings; build only after the core works, else move to Roadmap) |
| Intent-drift LLM check, plain-English policy compiler, risk score 0 to 100 | **Optional**; call Roadmap unless built |
| Real WhatsApp/SMS approvals, MCP connectors, multi-tenant SaaS, compliance reports | **Roadmap** |

**Non-goals:** real payment APIs, model training, production-certification claims, claims against competitors we did not benchmark.

---

## Part C. How it works

### C1. Architecture

```
AI Agent  (proposes tool calls; holds no tool credentials)
   │  POST /v1/gateway/execute  {agent_id, task_id, tool, params, approval_id?}
   ▼
Enforcement Gateway (FastAPI)  ── any error/timeout → BLOCK (fail closed)
   ├─ Permission + Policy engine
   ├─ Approval Store (SQLite): exact params, expiry, revocation, used flag
   ├─ Audit Log (SHA-256 hash chain)
   ▼
Simulated Tools: email · database · payments   (importable only by the gateway)
   ▼
Dashboard (React + WebSocket): live feed, approvals, policies, audit, demo, tests
```

### C2. Decision pipeline (order matters)

```
execute(req):
  try:
    agent = agents.get(req.agent_id)           else BLOCK "Unknown agent"
    tool  = registry.get(req.tool)             else BLOCK "Unknown tool"
    if not permitted(agent, req.task_id, tool): BLOCK "Agent lacks write permission"
    if policy.hard_block(req):                  BLOCK (e.g. "Destructive database operation prohibited")
    if policy.requires_approval(req):
        if not req.approval_id:                 create pending approval; ASK_HUMAN
        ap = approvals.get(req.approval_id)
        if ap is None or (ap.agent_id, ap.task_id, ap.tool) != (req.agent_id, req.task_id, req.tool):
                                                BLOCK "Approval does not match request"
        if hash(canonical(sensitive(req))) != ap.approved_hash:
                                                BLOCK "<field> changed after approval"
        if now >= ap.expires_at:                BLOCK "Approval expired"
        if ap.revoked_at:                       BLOCK "Approval revoked"
        # atomic one-time use
        n = UPDATE approvals SET status='used', used_at=now
            WHERE id=? AND status='approved' AND revoked_at IS NULL AND expires_at > now
        if n != 1:                              BLOCK "Approval already used (replay)"
    out = tools.run(req); record in tool_calls   ALLOW
  except Exception / timeout:                   BLOCK "Gateway error: failed closed"
  finally: audit.append(decision, reason, executed)
```

Why each rule exists:
- **Canonical hash:** sorted-key JSON, amount stored as integer paise, recipient normalised to a stable id (trimmed, case-folded). Prevents "Supplier A " vs "supplier a" confusion and float errors. Store the readable JSON too, so the UI can show *which field* changed.
- **Atomic `UPDATE ... WHERE status='approved'`:** two simultaneous requests cannot both win; exactly one gets `n = 1`. This is the replay and duplicate-execution defence.
- **Re-validation at execution time:** expiry, revocation and permissions are checked immediately before the tool runs.
- **No bypass:** only `gateway.py` imports the tool module. A test asserts the agent package has no reference to tool functions.
- **Fail closed:** the agent-side wrapper treats a timeout or no response as BLOCK and never calls a tool itself.

### C3. Audit hash chain
Record: `id, ts, agent_id, task_id, tool, params_masked, decision, reason, approval_id, executed, prev_hash, hash`.
`hash = SHA256(prev_hash + canonical_json(record_without_hash))`. Genesis `prev_hash = "0"*64`.
`GET /v1/audit/verify` recomputes the chain and returns `{ok, checked, broken_at}`.
**Secrets:** mask API keys, tokens and full account numbers *before* hashing and storing. A test plants fake secrets and greps the database and log files.

### C4. Data model (SQLite)
```
agents(id, name, role, permissions_json)
tasks(id, agent_id, description, scope_json)
policies(id, agent_id?, task_id?, tool, condition_json, decision, version, active)
approvals(id, agent_id, task_id, tool, approved_params_json, approved_hash,
          status[pending|approved|rejected|used|revoked|expired],
          created_at, approved_at, expires_at, revoked_at, used_at)
audit(id, ts, agent_id, task_id, tool, params_masked, decision, reason,
      approval_id, executed, prev_hash, hash)
tool_calls(id, tool, params_json, executed_at, audit_id)   -- proof of what actually ran
```
`tool_calls` is the evidence for "payment tool never executed": every BLOCK test asserts zero rows for that request.

### C5. API
| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/gateway/execute` | Agent submits a tool call; returns `{decision, reason, executed, audit_id}` |
| POST | `/v1/approvals` | Create approval for exact params |
| POST | `/v1/approvals/{id}/approve` · `/reject` · `/revoke` | Human actions |
| GET | `/v1/approvals?status=` | Queue |
| GET · PUT | `/v1/policies` | Read and edit rules |
| GET | `/v1/audit` · `/v1/audit/verify` | Log and integrity |
| POST | `/v1/demo/reset` · `/v1/demo/tamper` | Demo only (guarded by `DEMO_MODE=1`) |
| GET | `/v1/tests/results` | Serves `benchmarks/results.json` |
| WS | `/ws/events` | Live feed |

### C6. Policies (defaults)
| Rule | Decision |
|---|---|
| `payments.send` amount > ₹10,000 | ASK_HUMAN |
| `payments.send` with an approval: any sensitive field differs | BLOCK |
| Agent role `reader` calling a write tool | BLOCK |
| `database.run_sql` containing `DROP`/`TRUNCATE`/`DELETE` without `WHERE` | BLOCK |
| `email.send` to an unknown external domain | ASK_HUMAN |
| Approval default lifetime | 10 minutes |

---

## Part D. Demo scenarios and proof

| # | Scenario | Expected | Reason shown |
|---|---|---|---|
| 1 | Valid exact approved payment, Supplier A ₹5,000 | ALLOW | Matches approval |
| 2 | Recipient changed to Supplier B after approval | BLOCK | Recipient changed after approval |
| 3 | Amount changed after approval | BLOCK | Amount changed after approval |
| 4 | Approval expired | BLOCK | Approval expired |
| 5 | Approval revoked | BLOCK | Approval revoked |
| 6 | Read-only agent attempts a write | BLOCK | Agent lacks write permission |
| 7 | `DROP TABLE customers` | BLOCK | Destructive database operation prohibited |
| 8 | Payment above ₹10,000 | ASK HUMAN, then ALLOW after approval | Payment exceeds ₹10,000 limit |

**Proof package for scenario 2 (must be visible in video and live demo):** approval record → attempted Supplier B call → BLOCK response → `tool_calls` count 0 → audit record with hashes → separate unchanged call succeeds with count 1.

---

## Part E. Testing and metrics

### E1. Required security tests (each asserts decision, reason and tool-executed count)
1. Changed recipient
2. Changed amount
3. Expired approval
4. Revoked approval
5. Read-only agent attempts write
6. Replay / duplicate execution (sequential, and two concurrent requests where exactly one succeeds)
7. Payment above configured threshold without approval
8. Gateway failure (inject exception or stop the service; no tool runs, agent receives BLOCK)

Plus: audit tamper detection, secrets not in logs, no direct tool bypass, approval for a different agent or task rejected.

### E2. Suite design
30+ cases in `benchmarks/cases.json`: about 12 legitimate cases (must be ALLOW or correct ASK HUMAN flow) and 18+ violations, including variants (tiny amount change, whitespace or case change in recipient, currency change, wrong agent, wrong task, expired by one second, revoked just before execution).

### E3. Metric definitions (also write them in `benchmarks/README.md`)
| Metric | Definition |
|---|---|
| Test cases run | Rows executed by `run_benchmarks.py` |
| Unauthorized executions | Cases where a tool ran though expected decision was BLOCK or unresolved ASK HUMAN. Report actual count |
| Mismatch detection rate | Tampered executions blocked ÷ all tampered executions |
| False-block rate | Legitimate actions blocked ÷ all legitimate actions |
| Added latency | Mean and p95 of (gateway call time − direct mock-tool time) over 100 runs; state machine used |
| Audit integrity | Clean chain verifies; after editing one stored record, verify fails and names that record |

Rules: results are written to `benchmarks/results.json` by the script and read by the deck and dashboard. If any rate is below 100%, report it and explain. Say clearly that the suite is our own.

### E4. The four deck results and where the values are stored

Slide 6 of the deck has four result boxes. Their values are stored in **`results.txt`** (also copy it to `benchmarks/results.txt` in the repo). `run_benchmarks.py` must print these values and write them to `benchmarks/results.json`; copy them into `results.txt` and then into the deck. Never type a number that the script did not output.

| Deck box | Key in `results.txt` | How it is produced | Value |
|---|---|---|---|
| Unauthorized executions | `unauthorized_executions` | Count of cases where a tool ran but the expected decision was BLOCK or unresolved ASK HUMAN (check `tool_calls`) | `[ADD RESULT]` |
| Mismatch detection rate | `mismatch_detection_rate` | Tampered executions blocked ÷ all tampered executions | `[ADD RESULT]` |
| False-block rate | `false_block_rate` | Legitimate actions blocked ÷ all legitimate actions | `[ADD RESULT]` |
| Added latency | `added_latency_ms` | Mean (and p95) of gateway time minus direct tool time over 100 runs | `[ADD RESULT]` |

Supporting values stored in the same file: test cases run, legitimate and violation counts, p95 latency, audit verify and tamper-detection result, machine and Python version, commit hash, the eight required security tests with PASS/FAIL, and notes on any case that did not pass.

Workflow: run script → `results.json` → fill `results.txt` → paste the four values into slide 6 → commit both files to the repo so judges can reproduce them.

---

## Part F. Tech stack and repository

Backend: Python 3.11, FastAPI, Pydantic, SQLite, pytest, hashlib.
Frontend: React 18, Vite, Tailwind, Recharts, Lucide, WebSocket.
Agent: scripted mode (default, fully offline) and optional LLM mode.
Run path (required in README): `pip install -r requirements.txt` → `uvicorn app.main:app` → `npm run dev`. Docker optional. No runtime calls to external services; bundle fonts locally.

```
agentguard/
  backend/app/{main.py, gateway.py, approvals.py, policy.py, audit.py, db.py, schemas.py, tools/}
  backend/tests/                  # pytest: required tests + extras
  benchmarks/{cases.json, run_benchmarks.py, results.json, README.md}
  agent/{scripted_agent.py, sdk_wrapper.py}
  frontend/src/{pages, components, lib}
  docs/{plan.md, design.md, architecture.png}
  README.md  .env.example  LICENSE
```

---

## Part G. Team and schedule

| Person | Owns |
|---|---|
| Amruth CK | Gateway pipeline, approval binding, replay protection, integration |
| Mustafa Fazil | Audit chain, verify/tamper, tests, benchmark script |
| Rajesh Gouda | Frontend (from Stitch design), WebSocket feed |
| Adbuth Joshva D P | Demo agent, mock tools, policies page, video, README and deck polish |

Roles are a suggestion; keep one owner per area.

| Date (2026) | Goal | Exit check |
|---|---|---|
| Sun 11 Oct | Repo, schema, gateway skeleton, approvals create/approve | Valid payment ALLOW |
| Mon 12 | Exact match, expiry, revoke, one-time use, permissions, policies | Scenarios 1 to 6 pass |
| Tue 13 | Audit chain, verify, tamper; frontend feed and approvals | Chain verifies; feed is live |
| Wed 14 | 30+ tests, benchmark script, fail-closed test, results page | `results.json` generated |
| Thu 15 | Demo panel, scripted agent, record video and fallback recording | Offline run end to end |
| Fri 16 | Fill deck metrics and links; README; proofread | Deck checklist complete |
| Sat 17 | Final checks, push repo, upload video, submit on Unstop | Confirmation received |
| 18 to 19 | Buffer only, no new features | |
| 20 Oct | Hard deadline | |

**Cut order (from the bottom up):** Hindi/Kannada approval page, intent-drift, policy compiler, light theme, Docker, deployment link.
**Never cut:** exact-parameter block, replay protection, audit chain, tests with real metrics.

---

## Part H. Delivery

### H1. Demo video (heavily weighted, 2 to 3 minutes)
| Time | Content |
|---|---|
| 0:00 | Problem in one sentence |
| 0:20 | Valid approved payment → ALLOW |
| 0:50 | Approve Supplier A ₹5,000; agent tries Supplier B → BLOCK; parameter comparison; `Payment tool executions: 0` |
| 1:30 | Audit record, Verify (green), Simulate tamper, Verify (red, record named) |
| 2:00 | Test results page with real numbers |
| 2:30 | What is simulated and what is roadmap; close |
Captions on, large cursor, no external services needed. Record a second full take as the fallback.

### H2. Live pitch (if selected for the final)
Run the same sequence from the Demo Panel with the scripted agent. Keep a local SQLite snapshot and a Reset button; keep the fallback recording on the laptop and on Drive.

### H3. Submission package (Unstop, by 17 Oct)
- PPT in the official template (rename file to the team name as the template asks)
- GitHub repository link (README, run steps, tests, benchmark script)
- Google Drive demo video link (anyone with the link can view)
- Deployment link (optional; omit if none)
- Check links open in a private window; team of 4 from the same institute

### H4. Status of the deck right now
Filled: team name and members, leader email (amruthck123@gmail.com), phone (9686201029), college.
Pending: GitHub link, Drive link, deployment link (omit if none), four `[ADD RESULT]` metric boxes (fill only from `results.json`).

---

## Part I. Differentiation, risks, checklist

### I1. How to position
Existing agent gateways and guardrails mostly decide by policy and log events. AgentGuard's focus is narrower and testable: **approval bound to exact parameters, expiring and one-time, verified at execution time, with a verifiable audit chain, usable by non-technical owners.** Say "our focus is"; do not say "nobody else does this". Back every claim with a test result.

### I2. Risks
| Risk | Mitigation |
|---|---|
| Crowded space | Win on a deterministic, demonstrable core and real data |
| Six days of build time | Cut order above; core first |
| Self-written metrics look weak | Publish `cases.json` and the script; label as our own suite |
| Deck claims the build cannot support | Tag Implemented / Simulated / Roadmap; delete unbuilt claims by 16 Oct |
| Demo failure | Scripted agent, offline, reset button, fallback recording |
| Deck renders differently in PowerPoint | Open the final file in PowerPoint on a real machine |

### I3. Master checklist (yours, mapped to this plan)
- [ ] **1 Submission:** leader email ✔, phone ✔, college ✔; GitHub link, Drive link, deployment link (or omit)
- [ ] **2 Core proof:** Part D proof package, all six steps
- [ ] **3 Security tests:** Part E1, all eight, plus extras
- [ ] **4 Benchmarks:** Part E3 numbers in the deck from `results.json`; test setup documented
- [ ] **5 Hardening:** all calls via gateway; exact match; execution-time rechecks; atomic one-time use; chain tamper test; no secrets in logs
- [ ] **6 Presentation:** template and order kept; readable diagrams; ALLOW / ASK HUMAN / BLOCK used consistently; Implemented vs Simulated vs Roadmap tags; unsupported claims and repeats removed; proofread
- [ ] **7 Live demo:** valid-action run; modified-recipient attack; audit log and outcome; fallback recording; works offline
- [ ] **8 Security Hardening:** R1-R5 resolved with CTE protection, secret masking, and TOCTOU atomic state re-validation

### I4. Production Hardening Roadmap & Known Limitations
Documented infrastructure items for production evolution beyond the reference build:
1. **Physical Process & Tool Isolation (R1)**: Move tools to separate microservices/workers with gRPC/IPC isolation so tools cannot be imported into application or agent runtimes.
2. **Cryptographic Identity Attestation**: Replace payload `agent_id` with mTLS client certificates or SPIFFE/OIDC verifiable tokens.
3. **Multi-Tenant Physical Partitioning**: Schema-per-tenant or dedicated DB instances for strict enterprise tenancy.
4. **Asymmetric Audit Notarization**: Append-only log signing using Ed25519 HSM/KMS keys and public notary anchoring (Rekor).
5. **High-Throughput Distributed State**: PostgreSQL with Redis distributed locking for multi-region gateway clusters.
