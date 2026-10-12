"""
benchmarks/run_benchmarks.py

AgentGuard 2.0 Benchmark & Evaluation Suite (plan.md Part E).
Runs 30+ test cases from cases.json against a real, seeded database and real gateway pipeline (no mocks).
Measures and outputs:
  - test_cases_run, legitimate_cases, violation_cases
  - unauthorized_executions (must be 0)
  - mismatch_detection_rate (100.0%)
  - false_block_rate (0.0%)
  - added_latency mean and p95 (over 100 runs: direct tool vs gateway call)
  - audit clean verify and audit tamper detection (broken record id)
  - PASS/FAIL for the 8 required security tests

Outputs written to:
  - benchmarks/results.json
  - benchmarks/results.txt
  - results.txt (workspace root)
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Path setup: Add backend and workspace root to sys.path
BENCHMARKS_DIR = Path(__file__).resolve().parent
ROOT_DIR = BENCHMARKS_DIR.parent
BACKEND_DIR = ROOT_DIR / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import get_connection, init_db, reset_db, seed_demo
from app import approvals, audit, gateway, policy
from app.gateway import _run_tool
from app.schemas import Decision

logger = logging.getLogger("run_benchmarks")


def get_git_commit() -> str:
    """Retrieves current git commit hash, or 'unknown'."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ---------------------------------------------------------------------------
# 1. Benchmark Cases Runner
# ---------------------------------------------------------------------------
def run_cases_suite(cases: List[Dict[str, Any]], tmp_dir: str) -> Dict[str, Any]:
    """Runs all test cases from cases.json through the real gateway."""
    total_cases = len(cases)
    legitimate_cases = 0
    violation_cases = 0
    unauthorized_executions = 0
    tampered_total = 0
    tampered_blocked = 0
    legit_total = 0
    legit_blocked = 0

    case_results: List[Dict[str, Any]] = []

    for case in cases:
        case_id = case["id"]
        category = case["category"]
        expected_decision = case["expected_decision"]
        expected_tool_executed = case["expected_tool_executed"]
        setup = case.get("setup")
        req = case["request"]

        # Prepare dedicated isolated fresh database
        db_path = os.path.join(tmp_dir, f"bench_{case_id}.db")
        reset_db(db_path)
        seed_demo(db_path)

        approval_id: Optional[str] = req.get("approval_id")

        # Execute setup actions if requested
        if setup:
            create_appr = setup.get("create_approval")
            if create_appr:
                setup_agent = create_appr.get("agent_id", "accounts-agent")
                setup_task = create_appr.get("task_id", "task-accounts-1")
                ap = approvals.create(
                    agent_id=setup_agent,
                    task_id=setup_task,
                    tool=create_appr["tool"],
                    params=create_appr["params"],
                    db_path=db_path,
                )
                approval_id = ap.id

                if setup.get("approve"):
                    approvals.approve(approval_id, db_path=db_path)

                if setup.get("expire_backdate"):
                    conn = sqlite3.connect(db_path)
                    conn.execute(
                        "UPDATE approvals SET expires_at = '2020-01-01T00:00:00Z' WHERE id = ?",
                        (approval_id,),
                    )
                    conn.commit()
                    conn.close()

                if setup.get("revoke"):
                    approvals.revoke(approval_id, db_path=db_path)

                if setup.get("execute_first"):
                    # First legitimate execution to consume the approval
                    gateway.execute(
                        db_path,
                        agent_id=req["agent_id"],
                        task_id=req["task_id"],
                        tool=create_appr["tool"],
                        params=create_appr["params"],
                        approval_id=approval_id,
                    )

        # Count tool_calls before execution
        conn = get_connection(db_path)
        count_before = conn.execute("SELECT count(*) FROM tool_calls").fetchone()[0]
        conn.close()

        # Gateway execution
        resp = gateway.execute(
            db_path,
            agent_id=req["agent_id"],
            task_id=req["task_id"],
            tool=req["tool"],
            params=req["params"],
            approval_id=approval_id,
        )

        # Count tool_calls after execution
        conn = get_connection(db_path)
        count_after = conn.execute("SELECT count(*) FROM tool_calls").fetchone()[0]
        conn.close()

        tool_calls_delta = count_after - count_before
        tool_executed = (tool_calls_delta > 0)
        actual_decision = resp.decision.value if hasattr(resp.decision, "value") else str(resp.decision)

        # Check safety invariants
        if category == "legitimate":
            legitimate_cases += 1
            legit_total += 1
            if actual_decision == Decision.BLOCK.value:
                legit_blocked += 1
        else:
            violation_cases += 1
            tampered_total += 1
            if actual_decision in (Decision.BLOCK.value, Decision.ASK_HUMAN.value):
                tampered_blocked += 1

        # Check for unauthorized tool executions
        if expected_decision in ("BLOCK", "ASK_HUMAN") and tool_executed:
            unauthorized_executions += 1

        case_passed = (actual_decision == expected_decision) and (tool_executed == expected_tool_executed)

        case_results.append({
            "id": case_id,
            "description": case["description"],
            "category": category,
            "expected_decision": expected_decision,
            "actual_decision": actual_decision,
            "reason": resp.reason,
            "expected_tool_executed": expected_tool_executed,
            "actual_tool_executed": tool_executed,
            "tool_calls_delta": tool_calls_delta,
            "passed": case_passed,
        })

    mismatch_detection_rate = (tampered_blocked / tampered_total) if tampered_total > 0 else 1.0
    false_block_rate = (legit_blocked / legit_total) if legit_total > 0 else 0.0

    return {
        "test_cases_run": total_cases,
        "legitimate_cases": legitimate_cases,
        "violation_cases": violation_cases,
        "unauthorized_executions": unauthorized_executions,
        "mismatch_detection_rate": mismatch_detection_rate,
        "false_block_rate": false_block_rate,
        "cases": case_results,
    }


# ---------------------------------------------------------------------------
# 2. Added Latency Measurement (100 runs)
# ---------------------------------------------------------------------------
def measure_added_latency(tmp_dir: str, iterations: int = 100) -> Dict[str, float]:
    """
    Measures added latency: (gateway call time - direct mock-tool time)
    over 100 runs.
    """
    lat_db = os.path.join(tmp_dir, "latency_bench.db")
    reset_db(lat_db)
    seed_demo(lat_db)

    sample_params = {
        "recipient": "Supplier A",
        "amount": 5000.0,
        "currency": "INR",
        "reference": "LAT-TEST",
    }

    deltas_ms: List[float] = []

    for i in range(iterations):
        # 1. Time direct mock-tool execution
        t0 = time.perf_counter()
        _run_tool("payments.send", sample_params)
        direct_ms = (time.perf_counter() - t0) * 1000.0

        # 2. Create and approve an approval for gateway execution
        ap = approvals.create(
            agent_id="accounts-agent",
            task_id="task-accounts-1",
            tool="payments.send",
            params=sample_params,
            db_path=lat_db,
        )
        approvals.approve(ap.id, db_path=lat_db)

        # 3. Time gateway execution
        t1 = time.perf_counter()
        gateway.execute(
            lat_db,
            agent_id="accounts-agent",
            task_id="task-accounts-1",
            tool="payments.send",
            params=sample_params,
            approval_id=ap.id,
        )
        gw_ms = (time.perf_counter() - t1) * 1000.0

        # Delta = max(0, gw_ms - direct_ms)
        deltas_ms.append(max(0.0, gw_ms - direct_ms))

    mean_latency = statistics.mean(deltas_ms)
    sorted_deltas = sorted(deltas_ms)
    p95_idx = int(0.95 * len(sorted_deltas))
    p95_latency = sorted_deltas[min(p95_idx, len(sorted_deltas) - 1)]

    return {
        "mean_ms": round(mean_latency, 3),
        "p95_ms": round(p95_latency, 3),
        "iterations": iterations,
    }


# ---------------------------------------------------------------------------
# 3. Audit Integrity & Tamper Detection Benchmark
# ---------------------------------------------------------------------------
def run_audit_benchmarks(tmp_dir: str) -> Dict[str, Any]:
    """Tests clean chain verification and tamper detection."""
    audit_db = os.path.join(tmp_dir, "audit_verify_bench.db")
    reset_db(audit_db)
    seed_demo(audit_db)

    # Populate several audit records
    for i in range(5):
        gateway.execute(
            audit_db,
            agent_id="accounts-agent",
            task_id="task-accounts-1",
            tool="payments.send",
            params={"recipient": "Supplier A", "amount": 1000.0 * (i + 1), "currency": "INR"},
        )

    # 1. Clean verify
    clean_res = audit.verify(audit_db)
    clean_dict = clean_res.model_dump() if hasattr(clean_res, "model_dump") else (clean_res if isinstance(clean_res, dict) else dict(clean_res))
    clean_ok = clean_dict.get("ok") is True
    records_checked = clean_dict.get("checked", 0)

    # 2. Tamper detection on record #2
    tampered_id = 2
    audit.tamper(tampered_id, db_path=audit_db)
    tamper_res = audit.verify(audit_db)
    tamper_dict = tamper_res.model_dump() if hasattr(tamper_res, "model_dump") else (tamper_res if isinstance(tamper_res, dict) else dict(tamper_res))
    tamper_detected = (tamper_dict.get("ok") is False) and (tamper_dict.get("broken_at") == tampered_id)

    return {
        "clean_verify_pass": clean_ok,
        "clean_records_checked": records_checked,
        "tamper_detected_pass": tamper_detected,
        "tampered_record_id": tampered_id,
        "reported_broken_at": tamper_dict.get("broken_at"),
    }


# ---------------------------------------------------------------------------
# 4. The 8 Required Security Tests (plan.md §E1)
# ---------------------------------------------------------------------------
def run_security_tests(tmp_dir: str) -> Dict[str, str]:
    """Executes the 8 required security tests from plan.md §E1 and returns PASS/FAIL."""
    results: Dict[str, str] = {}
    sec_db = os.path.join(tmp_dir, "security_tests.db")

    def fresh_db() -> str:
        reset_db(sec_db)
        seed_demo(sec_db)
        return sec_db

    def dec_str(d: Any) -> str:
        return d.value if hasattr(d, "value") else str(d)

    # Test 1: Changed recipient
    db = fresh_db()
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", {"recipient": "Supplier A", "amount": 5000}, db_path=db)
    approvals.approve(ap.id, db_path=db)
    r = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier B", "amount": 5000}, approval_id=ap.id)
    results["security_test_1_changed_recipient"] = "PASS" if dec_str(r.decision) == "BLOCK" and "Recipient changed" in r.reason and not r.executed else "FAIL"

    # Test 2: Changed amount
    db = fresh_db()
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", {"recipient": "Supplier A", "amount": 5000}, db_path=db)
    approvals.approve(ap.id, db_path=db)
    r = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 6000}, approval_id=ap.id)
    results["security_test_2_changed_amount"] = "PASS" if dec_str(r.decision) == "BLOCK" and "Amount changed" in r.reason and not r.executed else "FAIL"

    # Test 3: Expired approval
    db = fresh_db()
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", {"recipient": "Supplier A", "amount": 5000}, db_path=db)
    approvals.approve(ap.id, db_path=db)
    conn3 = sqlite3.connect(db)
    conn3.execute("UPDATE approvals SET expires_at = '2020-01-01T00:00:00Z' WHERE id = ?", (ap.id,))
    conn3.commit()
    conn3.close()
    r = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 5000}, approval_id=ap.id)
    results["security_test_3_expired_approval"] = "PASS" if dec_str(r.decision) == "BLOCK" and "Approval expired" in r.reason and not r.executed else "FAIL"

    # Test 4: Revoked approval
    db = fresh_db()
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", {"recipient": "Supplier A", "amount": 5000}, db_path=db)
    approvals.approve(ap.id, db_path=db)
    approvals.revoke(ap.id, db_path=db)
    r = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 5000}, approval_id=ap.id)
    results["security_test_4_revoked_approval"] = "PASS" if dec_str(r.decision) == "BLOCK" and "Approval revoked" in r.reason and not r.executed else "FAIL"

    # Test 5: Read-only agent attempts write
    db = fresh_db()
    r = gateway.execute(db, agent_id="reader-agent", task_id="task-reader-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 5000})
    results["security_test_5_read_only_agent_write"] = "PASS" if dec_str(r.decision) == "BLOCK" and "Agent lacks write permission" in r.reason and not r.executed else "FAIL"

    # Test 6: Replay / duplicate execution
    db = fresh_db()
    ap = approvals.create("accounts-agent", "task-accounts-1", "payments.send", {"recipient": "Supplier A", "amount": 5000}, db_path=db)
    approvals.approve(ap.id, db_path=db)
    r1 = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 5000}, approval_id=ap.id)
    r2 = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 5000}, approval_id=ap.id)
    results["security_test_6_replay_protection"] = "PASS" if dec_str(r1.decision) == "ALLOW" and dec_str(r2.decision) == "BLOCK" and "Approval already used (replay)" in r2.reason and not r2.executed else "FAIL"

    # Test 7: Payment above threshold without approval
    db = fresh_db()
    r = gateway.execute(db, agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 15000.00})
    results["security_test_7_over_threshold"] = "PASS" if dec_str(r.decision) == "ASK_HUMAN" and "Payment exceeds" in r.reason and not r.executed else "FAIL"

    # Test 8: Gateway failure fail closed
    r = gateway.execute("/nonexistent/invalid_path.db", agent_id="accounts-agent", task_id="task-accounts-1", tool="payments.send", params={"recipient": "Supplier A", "amount": 5000.00})
    results["security_test_8_gateway_fail_closed"] = "PASS" if dec_str(r.decision) == "BLOCK" and "Gateway error: failed closed" in r.reason and not r.executed else "FAIL"

    return results


# ---------------------------------------------------------------------------
# Main Orchestration & Output Formatter
# ---------------------------------------------------------------------------
def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("=" * 80, flush=True)
    print("AGENTGUARD 2.0 BENCHMARK & EVALUATION RUNNER")
    print("=" * 80)

    cases_file = BENCHMARKS_DIR / "cases.json"
    if not cases_file.is_file():
        print(f"Error: {cases_file} not found!", file=sys.stderr)
        sys.exit(1)

    cases: List[Dict[str, Any]] = json.loads(cases_file.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"[*] Running {len(cases)} benchmark cases against isolated databases...")
        cases_summary = run_cases_suite(cases, tmp_dir)

        print(f"[*] Measuring added latency over 100 iterations...")
        latency_summary = measure_added_latency(tmp_dir, iterations=100)

        print(f"[*] Verifying audit log integrity and tamper detection...")
        audit_summary = run_audit_benchmarks(tmp_dir)

        print(f"[*] Running the 8 required security tests...")
        sec_tests = run_security_tests(tmp_dir)

    git_commit = get_git_commit()
    python_ver = sys.version.split()[0]
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    iso_now = datetime.now(timezone.utc).isoformat()

    mismatch_rate_pct = f"{cases_summary['mismatch_detection_rate'] * 100:.1f}%"
    false_block_rate_pct = f"{cases_summary['false_block_rate'] * 100:.1f}%"

    # Structured JSON data payload
    results_json_data = {
        "timestamp": iso_now,
        "metadata": {
            "python_version": python_ver,
            "platform": os_info,
            "git_commit": git_commit,
        },
        "summary": {
            "test_cases_run": cases_summary["test_cases_run"],
            "legitimate_cases": cases_summary["legitimate_cases"],
            "violation_cases": cases_summary["violation_cases"],
            "unauthorized_executions": cases_summary["unauthorized_executions"],
            "mismatch_detection_rate": cases_summary["mismatch_detection_rate"],
            "mismatch_detection_rate_pct": mismatch_rate_pct,
            "false_block_rate": cases_summary["false_block_rate"],
            "false_block_rate_pct": false_block_rate_pct,
            "added_latency_mean_ms": latency_summary["mean_ms"],
            "added_latency_p95_ms": latency_summary["p95_ms"],
        },
        "audit": {
            "clean_verify_pass": audit_summary["clean_verify_pass"],
            "clean_records_checked": audit_summary["clean_records_checked"],
            "tamper_detected_pass": audit_summary["tamper_detected_pass"],
            "tampered_record_id": audit_summary["tampered_record_id"],
            "reported_broken_at": audit_summary["reported_broken_at"],
        },
        "security_tests": sec_tests,
        "detailed_cases": cases_summary["cases"],
    }

    # Write benchmarks/results.json
    results_json_path = BENCHMARKS_DIR / "results.json"
    results_json_path.write_text(json.dumps(results_json_data, indent=2), encoding="utf-8")
    print(f"[✓] Written benchmarks/results.json ({results_json_path})")

    # Format results.txt key = value text
    results_txt_content = f"""# AgentGuard 2.0 Benchmark & Evaluation Results
# Generated automatically by benchmarks/run_benchmarks.py at {iso_now}

[deck_boxes]
unauthorized_executions = {cases_summary['unauthorized_executions']}
mismatch_detection_rate = {mismatch_rate_pct}
false_block_rate = {false_block_rate_pct}
added_latency_ms = {latency_summary['mean_ms']} ms (p95: {latency_summary['p95_ms']} ms)

[metrics]
test_cases_run = {cases_summary['test_cases_run']}
legitimate_cases = {cases_summary['legitimate_cases']}
violation_cases = {cases_summary['violation_cases']}
unauthorized_executions = {cases_summary['unauthorized_executions']}
mismatch_detection_rate = {mismatch_rate_pct}
false_block_rate = {false_block_rate_pct}
added_latency_mean_ms = {latency_summary['mean_ms']} ms
added_latency_p95_ms = {latency_summary['p95_ms']} ms

[audit]
audit_clean_verify = {'PASS' if audit_summary['clean_verify_pass'] else 'FAIL'}
audit_clean_records_checked = {audit_summary['clean_records_checked']}
audit_tamper_detection = {'PASS' if audit_summary['tamper_detected_pass'] else 'FAIL'}
audit_tamper_record_id = {audit_summary['tampered_record_id']}
audit_tamper_reported_broken_at = {audit_summary['reported_broken_at']}

[security_tests]
security_test_1_changed_recipient = {sec_tests['security_test_1_changed_recipient']}
security_test_2_changed_amount = {sec_tests['security_test_2_changed_amount']}
security_test_3_expired_approval = {sec_tests['security_test_3_expired_approval']}
security_test_4_revoked_approval = {sec_tests['security_test_4_revoked_approval']}
security_test_5_read_only_agent_write = {sec_tests['security_test_5_read_only_agent_write']}
security_test_6_replay_protection = {sec_tests['security_test_6_replay_protection']}
security_test_7_over_threshold = {sec_tests['security_test_7_over_threshold']}
security_test_8_gateway_fail_closed = {sec_tests['security_test_8_gateway_fail_closed']}

[environment]
python_version = {python_ver}
platform = {os_info}
git_commit = {git_commit}
timestamp = {iso_now}
"""

    bench_txt_path = BENCHMARKS_DIR / "results.txt"
    root_txt_path = ROOT_DIR / "results.txt"

    bench_txt_path.write_text(results_txt_content, encoding="utf-8")
    root_txt_path.write_text(results_txt_content, encoding="utf-8")
    print(f"[✓] Written benchmarks/results.txt ({bench_txt_path})")
    print(f"[✓] Written results.txt ({root_txt_path})")

    # Print summary to stdout
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS SUMMARY (Deck Slide 6 Values)")
    print("=" * 80)
    print(f"  Test Cases Run:             {cases_summary['test_cases_run']}")
    print(f"  Legitimate Cases:           {cases_summary['legitimate_cases']}")
    print(f"  Violation Cases:            {cases_summary['violation_cases']}")
    print(f"  Unauthorized Executions:    {cases_summary['unauthorized_executions']}")
    print(f"  Mismatch Detection Rate:    {mismatch_rate_pct}")
    print(f"  False-Block Rate:           {false_block_rate_pct}")
    print(f"  Added Latency (Mean):       {latency_summary['mean_ms']} ms")
    print(f"  Added Latency (P95):        {latency_summary['p95_ms']} ms")
    print(f"  Audit Clean Verify:         {'PASS' if audit_summary['clean_verify_pass'] else 'FAIL'}")
    print(f"  Audit Tamper Detection:     {'PASS' if audit_summary['tamper_detected_pass'] else 'FAIL'} (detected at record #{audit_summary['reported_broken_at']})")
    print("-" * 80)
    print("  Security Tests (8/8):")
    for k, v in sec_tests.items():
        print(f"    - {k}: {v}")
    print("=" * 80)


if __name__ == "__main__":
    main()
