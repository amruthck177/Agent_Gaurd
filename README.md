# AgentGuard 2.0

AI-agent safety gateway — DevHack 2026 · Team LogicLords · PS 2.1

AgentGuard enforces that every sensitive AI-agent action (payments, email, database writes)
passes through a gateway before it runs. Approvals are bound to exact parameters, expire,
can be revoked, and work only once. Every decision is logged in a SHA-256 hash-chained
audit log. All tools are **simulated** (no real payments or email).

---

## Quick Start (Clone & Run)

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm 9+

---

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/AgentGaurd.git
cd AgentGaurd
```

---

### 2. Backend setup

```bash
# Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Copy the environment file (defaults work out of the box)
cp .env.example .env

# Start the backend API server (from repo root)
uvicorn app.main:app --reload --app-dir backend --host 127.0.0.1 --port 8000

# Verify it's running
curl http://localhost:8000/health
# → {"status":"ok"}
```

---

### 3. Frontend setup

```bash
# In a new terminal, from the repo root
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

> The frontend automatically proxies API calls to `http://localhost:8000`.

---

### 4. Run the tests (optional)

```bash
# From repo root, with venv active
pytest backend/tests/ -v
# → 110 passed
```

---

### 5. Run benchmarks (optional)

```bash
python benchmarks/run_benchmarks.py
# Results saved to benchmarks/results.json
```

---

## Repository Layout

```
AgentGaurd/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, router registration
│   │   ├── gateway.py       # Enforcement pipeline
│   │   ├── approvals.py     # Approval CRUD and state machine
│   │   ├── policy.py        # Rule engine
│   │   ├── audit.py         # SHA-256 hash-chain audit log
│   │   ├── db.py            # SQLite connection + schema
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── tools/           # Simulated tools (payments, email, database)
│   └── tests/               # 110 pytest tests
├── frontend/
│   ├── src/
│   │   ├── pages/           # Live Feed, Approvals, Audit Log, Demo Panel, etc.
│   │   ├── components/      # Reusable UI components
│   │   └── lib/             # API client, WebSocket hooks
│   ├── package.json
│   └── vite.config.ts       # Proxy: /api → localhost:8000
├── agent/
│   ├── scripted_agent.py    # Offline scripted demo agent
│   └── sdk_wrapper.py       # Agent-side fail-closed wrapper
├── benchmarks/
│   ├── cases.json           # 34 attack + legitimate test cases
│   ├── run_benchmarks.py    # Benchmark runner
│   └── results.json         # Latest results (100% defense rate)
├── docs/
│   ├── plan.md              # System design & logic
│   ├── design.md            # UI design spec
│   └── openapi.json         # Full OpenAPI spec
├── design-export/           # UI design screenshots & HTML exports
├── .env.example             # Environment variable template
├── requirements.txt         # Python dependencies
└── README.md
```

---

## How It Works

Every agent tool call goes through this pipeline:

```
Agent → SDK Wrapper → AgentGuard Gateway → [Policy Check] → [Approval Check] → Tool
                                ↓
                         Audit Log (SHA-256 Merkle chain)
```

### Decision Statuses

| Status | Meaning |
|--------|---------|
| `ALLOW` | All checks passed — tool executed |
| `ASK_HUMAN` | Human approval required — tool did not run |
| `BLOCK` | Rule or approval violation — tool did not run |

---

## Key Security Features

| Feature | Description |
|---------|-------------|
| **Exact parameter binding** | Approvals are locked to exact recipient, amount, currency |
| **TTL enforcement** | Tokens expire after configurable time-to-live |
| **Revocation** | Approvals can be revoked instantly, even mid-flight |
| **Single-use tokens** | Replay attacks blocked — each token consumed on use |
| **Read-only enforcement** | Agents with read-only roles cannot execute writes |
| **SQL policy** | Destructive operations (DROP TABLE) blocked by policy |
| **Fail-closed** | Gateway failure blocks all actions — never defaults to open |
| **Merkle audit chain** | Every decision hashed — tampering detected immediately |
| **Human-in-the-loop** | Large payments routed to human approver via enclave |

---

## Known Limitations

1. **SQLite** — reference implementation uses SQLite. Production needs PostgreSQL + Redis.
2. **No mTLS** — `agent_id` passed as metadata. Production requires signed JWT/SPIFFE.
3. **Single node** — concurrency via SQLite WAL. Multi-node needs distributed locking.
4. **Hash-chain only** — production roadmap adds Ed25519 signing + Sigstore/Rekor notary.

---

## Team

| Person | Area |
|--------|------|
| Amruth CK (leader) | Gateway pipeline, approval binding, replay protection |
| Mustafa Fazil | Audit chain, tests, benchmark script |
| Rajesh Gouda | Frontend, WebSocket feed |
| Adbuth Joshva D P | Demo agent, mock tools, policies, video, README |
