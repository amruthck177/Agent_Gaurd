"""
backend/app/main.py

FastAPI application entry point for AgentGuard 2.0 (plan.md §C5).

Endpoints implemented:
  - POST /v1/gateway/execute                     Agent submits tool call; enforce policy & approval
  - POST /v1/approvals                           Create approval for exact parameters
  - POST /v1/approvals/{id}/approve              Human approves
  - POST /v1/approvals/{id}/reject               Human rejects
  - POST /v1/approvals/{id}/revoke               Human revokes
  - GET  /v1/approvals                           List approval queue (?status=)
  - GET  /v1/policies                            List all active policies
  - PUT  /v1/policies                            Create or update policy
  - GET  /v1/audit                               Query audit log (?search=&format=csv)
  - GET  /v1/audit/verify                        Cryptographic hash chain verification
  - GET  /v1/tool_calls & /v1/tool-calls         Proof of executed tool calls
  - POST /v1/demo/reset                          Reset demo DB (DEMO_MODE=1 guarded)
  - POST /v1/demo/tamper                         Direct SQL record tamper (DEMO_MODE=1 guarded)
  - GET  /v1/tests/results                       Serves benchmarks/results.json
  - WS   /ws/events                              WebSocket real-time events feed
  - GET  /health                                 Liveness check

Security & Validation:
  - CORS enabled for http://localhost:5173 only
  - All input validated with Pydantic (422 on invalid input, never a stack trace)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import approvals, audit, gateway, policy
from app.db import DB_PATH, get_connection, init_db, reset_db, seed_demo
from app.schemas import (
    Approval,
    ApprovalCreate,
    AuditVerifyResponse,
    Decision,
    ExecuteRequest,
    ExecuteResponse,
    Policy,
)

logger = logging.getLogger(__name__)

BENCHMARKS_RESULTS_PATH = Path(__file__).resolve().parent.parent.parent / "benchmarks" / "results.json"


def get_db_path() -> str:
    """Returns the database path, allowing dynamic override via AGENTGUARD_DB_PATH."""
    return os.getenv("AGENTGUARD_DB_PATH", DB_PATH)


# ---------------------------------------------------------------------------
# WebSocket Real-Time Event Broadcaster
# ---------------------------------------------------------------------------
class ConnectionManager:
    """Manages active WebSocket connections and broadcasts events as JSON."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.debug("WebSocket client connected. Total clients: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.debug("WebSocket client disconnected. Total clients: %d", len(self.active_connections))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        async with self._lock:
            disconnected: List[WebSocket] = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)

            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Application Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database schema is ready on startup
    db_file = get_db_path()
    init_db(db_file)
    logger.info("AgentGuard 2.0 initialized with DB at %s", db_file)
    yield


# ---------------------------------------------------------------------------
# FastAPI App Setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AgentGuard 2.0",
    description="AI Agent Safety & Exact-Parameter Enforcement Gateway",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS: Enabled strictly for the frontend dashboard at http://localhost:5173
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception Handlers: Never leak stack traces
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Returns 422 with structured validation errors; never leaks stack traces."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches any unhandled exceptions, logs them, and returns clean 500 JSON without stack trace."""
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error": str(exc)},
    )


# ---------------------------------------------------------------------------
# Liveness Check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Liveness check. Returns ok when server is running."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# 1. Gateway Execution (plan.md §C5)
# ---------------------------------------------------------------------------
@app.post("/v1/gateway/execute", response_model=ExecuteResponse, tags=["gateway"])
async def gateway_execute(req: ExecuteRequest) -> ExecuteResponse:
    """
    Submits an agent tool execution request through the security gateway.
    Enforces exact parameter matching, policy evaluation, expiry, and replay protection.
    """
    db_file = get_db_path()
    resp = gateway.execute(
        db_path=db_file,
        agent_id=req.agent_id,
        task_id=req.task_id,
        tool=req.tool,
        params=req.params,
        approval_id=req.approval_id,
    )

    # Broadcast decision event via WebSocket
    await manager.broadcast({
        "type": "gateway.decision",
        "data": {
            "agent_id": req.agent_id,
            "task_id": req.task_id,
            "tool": req.tool,
            "decision": resp.decision.value if hasattr(resp.decision, "value") else str(resp.decision),
            "reason": resp.reason,
            "executed": resp.executed,
            "audit_id": resp.audit_id,
            "approval_id": resp.approval_id,
        },
    })

    return resp


# ---------------------------------------------------------------------------
# 2. Approvals Management (plan.md §C5)
# ---------------------------------------------------------------------------
@app.post("/v1/approvals", response_model=Approval, status_code=status.HTTP_201_CREATED, tags=["approvals"])
async def create_approval_endpoint(body: ApprovalCreate) -> Approval:
    """Creates a new pending approval bound to exact canonical sensitive parameters."""
    db_file = get_db_path()
    ap = approvals.create(
        agent_id=body.agent_id,
        task_id=body.task_id,
        tool=body.tool,
        params=body.params,
        db_path=db_file,
    )

    ap_data = dict(ap)
    await manager.broadcast({
        "type": "approval.created",
        "data": ap_data,
    })
    return ap_data


@app.post("/v1/approvals/{id}/approve", tags=["approvals"])
async def approve_endpoint(id: str) -> Dict[str, Any]:
    """Human action: Approves a pending approval."""
    db_file = get_db_path()
    success = approvals.approve(id, db_path=db_file)
    if not success:
        raise HTTPException(status_code=404, detail=f"Approval {id!r} not found or not in pending status")

    ap = approvals.get(id, db_path=db_file)
    await manager.broadcast({
        "type": "approval.updated",
        "action": "approved",
        "data": ap,
    })
    return ap or {"id": id, "status": "approved"}


@app.post("/v1/approvals/{id}/reject", tags=["approvals"])
async def reject_endpoint(id: str) -> Dict[str, Any]:
    """Human action: Rejects a pending approval."""
    db_file = get_db_path()
    success = approvals.reject(id, db_path=db_file)
    if not success:
        raise HTTPException(status_code=404, detail=f"Approval {id!r} not found or not in pending status")

    ap = approvals.get(id, db_path=db_file)
    await manager.broadcast({
        "type": "approval.updated",
        "action": "rejected",
        "data": ap,
    })
    return ap or {"id": id, "status": "rejected"}


@app.post("/v1/approvals/{id}/revoke", tags=["approvals"])
async def revoke_endpoint(id: str) -> Dict[str, Any]:
    """Human action: Revokes an active or approved approval."""
    db_file = get_db_path()
    success = approvals.revoke(id, db_path=db_file)
    if not success:
        raise HTTPException(status_code=404, detail=f"Approval {id!r} not found")

    ap = approvals.get(id, db_path=db_file)
    await manager.broadcast({
        "type": "approval.updated",
        "action": "revoked",
        "data": ap,
    })
    return ap or {"id": id, "status": "revoked"}


@app.get("/v1/approvals", tags=["approvals"])
async def list_approvals_endpoint(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lists approval records filtered optionally by status."""
    db_file = get_db_path()
    return approvals.list(status=status, db_path=db_file)


# ---------------------------------------------------------------------------
# 3. Policies Management (plan.md §C5)
# ---------------------------------------------------------------------------
@app.get("/v1/policies", tags=["policies"])
async def get_policies_endpoint() -> List[Dict[str, Any]]:
    """Reads all policies stored in the database."""
    db_file = get_db_path()
    conn = get_connection(db_file)
    try:
        rows = conn.execute("SELECT * FROM policies ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.put("/v1/policies", tags=["policies"])
async def update_policies_endpoint(pol: Policy) -> Dict[str, Any]:
    """Creates a new policy or updates an existing policy row."""
    db_file = get_db_path()
    conn = get_connection(db_file)
    try:
        cur = conn.cursor()
        decision_str = pol.decision.value if hasattr(pol.decision, "value") else str(pol.decision)

        if pol.id is not None:
            cur.execute(
                """
                UPDATE policies
                SET agent_id = ?, task_id = ?, tool = ?, condition_json = ?,
                    decision = ?, version = version + 1, active = ?
                WHERE id = ?
                """,
                (
                    pol.agent_id,
                    pol.task_id,
                    pol.tool,
                    pol.condition_json,
                    decision_str,
                    1 if pol.active else 0,
                    pol.id,
                ),
            )
            pol_id = pol.id
        else:
            cur.execute(
                """
                INSERT INTO policies (agent_id, task_id, tool, condition_json, decision, version, active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pol.agent_id,
                    pol.task_id,
                    pol.tool,
                    pol.condition_json,
                    decision_str,
                    pol.version,
                    1 if pol.active else 0,
                ),
            )
            pol_id = cur.lastrowid

        conn.commit()
        row = conn.execute("SELECT * FROM policies WHERE id = ?", (pol_id,)).fetchone()
        result = dict(row)

        # Broadcast policy update event
        await manager.broadcast({
            "type": "policy.updated",
            "data": result,
        })
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 4. Audit Log & Integrity Verification (plan.md §C5)
# ---------------------------------------------------------------------------
@app.get("/v1/audit", tags=["audit"])
async def get_audit_endpoint(
    agent_id: Optional[str] = None,
    task_id: Optional[str] = None,
    tool: Optional[str] = None,
    decision: Optional[str] = None,
    executed: Optional[bool] = None,
    approval_id: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    format: Optional[str] = None,
) -> Any:
    """
    Returns audit log entries with optional filters.
    If format=csv, returns standard CSV download text.
    """
    db_file = get_db_path()
    filters = {
        "agent_id": agent_id,
        "task_id": task_id,
        "tool": tool,
        "decision": decision,
        "executed": executed,
        "approval_id": approval_id,
        "since": since,
        "until": until,
        "search": search,
        "limit": limit,
        "offset": offset,
    }

    if format == "csv":
        csv_text = audit.export_csv(db_path=db_file, filters=filters)
        return Response(content=csv_text, media_type="text/csv")

    return audit.list(filters=filters, db_path=db_file)


@app.get("/v1/audit/verify", response_model=AuditVerifyResponse, tags=["audit"])
async def verify_audit_endpoint() -> AuditVerifyResponse:
    """Recomputes SHA-256 hash chain from genesis to verify log integrity."""
    db_file = get_db_path()
    return audit.verify(db_path=db_file)


# ---------------------------------------------------------------------------
# 5. Tool Calls Evidence (plan.md §C4, §D)
# ---------------------------------------------------------------------------
@app.get("/v1/tool_calls", tags=["evidence"])
@app.get("/v1/tool-calls", tags=["evidence"])
async def get_tool_calls_endpoint(
    tool: Optional[str] = None,
    audit_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Queries actual executed tool calls. Used as verifiable evidence
    that blocked actions never ran.
    """
    db_file = get_db_path()
    conn = get_connection(db_file)
    try:
        clauses = []
        params = []
        if tool:
            clauses.append("tool = ?")
            params.append(tool)
        if audit_id is not None:
            clauses.append("audit_id = ?")
            params.append(audit_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM tool_calls {where_sql} ORDER BY id DESC"
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        return {"count": len(rows), "tool_calls": rows}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 6. Demo Endpoints (Guarded by DEMO_MODE=1) (plan.md §C5)
# ---------------------------------------------------------------------------
@app.post("/v1/demo/reset", tags=["demo"])
async def demo_reset_endpoint() -> Dict[str, Any]:
    """Resets and re-seeds demo database. Disabled when DEMO_MODE != 1."""
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo endpoint disabled (DEMO_MODE != 1)",
        )

    db_file = get_db_path()
    reset_db(db_file)
    seed_demo(db_file)

    await manager.broadcast({
        "type": "demo.reset",
        "status": "ok",
    })
    return {"status": "ok", "message": "Demo database reset and seeded successfully"}


@app.post("/v1/demo/tamper", tags=["demo"])
async def demo_tamper_endpoint(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Directly alters a stored audit decision in SQL without updating hashes.
    Disabled when DEMO_MODE != 1.
    """
    if os.getenv("DEMO_MODE", "1") != "1":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo endpoint disabled (DEMO_MODE != 1)",
        )

    db_file = get_db_path()
    record_id = payload.get("record_id") if payload else None

    if record_id is None:
        # Default to latest row in audit table
        conn = get_connection(db_file)
        row = conn.execute("SELECT id FROM audit ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=400, detail="No audit records available to tamper")
        record_id = row["id"]

    success = audit.tamper(int(record_id), db_path=db_file)
    if not success:
        raise HTTPException(status_code=404, detail=f"Audit record {record_id} not found")

    await manager.broadcast({
        "type": "demo.tamper",
        "record_id": record_id,
    })
    return {"status": "tampered", "record_id": record_id}


# ---------------------------------------------------------------------------
# 7. Benchmark / Test Results (plan.md §C5)
# ---------------------------------------------------------------------------
@app.get("/v1/tests/results", tags=["benchmarks"])
async def get_test_results_endpoint() -> Dict[str, Any]:
    """
    Reads and serves benchmarks/results.json.
    Returns {'available': false} if the file has not yet been generated.
    """
    if not BENCHMARKS_RESULTS_PATH.is_file():
        return {"available": False}

    try:
        data = json.loads(BENCHMARKS_RESULTS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {"available": True, **data}
        return {"available": True, "results": data}
    except Exception as exc:
        logger.warning("Could not read benchmarks/results.json: %s", exc)
        return {"available": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# 8. WebSocket Events Feed (plan.md §C5)
# ---------------------------------------------------------------------------
@app.websocket("/ws/events")
async def websocket_events_endpoint(websocket: WebSocket):
    """
    Live WebSocket feed broadcasting all gateway decisions, approval transitions,
    and demo events to connected dashboard clients.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; handles client pings
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)
