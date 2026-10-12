"""
backend/app/tools/payments.py

[SIMULATED] Simulated payments tool — no real money moves.
LABEL: [SIMULATED] — shown in UI.
Appends to an in-memory/DB ledger and returns a fake txn id.
Only imported and invoked by gateway.py after all security checks pass.
All tools print nothing sensitive and are clearly labelled SIMULATED in docstrings
and return payloads ({"simulated": true}).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# In-memory ledger storing simulated payment transactions
_LEDGER: List[Dict[str, Any]] = []


def get_ledger() -> List[Dict[str, Any]]:
    """[SIMULATED] Returns a copy of all recorded transactions in the simulated ledger."""
    return list(_LEDGER)


def clear_ledger() -> None:
    """[SIMULATED] Clears the in-memory simulated payments ledger."""
    _LEDGER.clear()


def send(
    recipient: Any = None,
    amount: Any = None,
    currency: str = "INR",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    [SIMULATED] Executes a simulated payment.
    Appends the transaction to an in-memory ledger and returns a fake txn id.
    Prints nothing sensitive.

    Accepts either positional/keyword arguments (recipient, amount, currency)
    or a params dict as the first argument.
    """
    if isinstance(recipient, dict) and amount is None:
        params = recipient
        rec = str(params.get("recipient", params.get("recipient_id", params.get("payee", "unknown"))))
        amt = params.get("amount", params.get("amount_paise", 0))
        curr = str(params.get("currency", "INR"))
        ref = str(params.get("reference", "N/A"))
    else:
        rec = str(recipient if recipient is not None else kwargs.get("recipient", "unknown"))
        amt = amount if amount is not None else kwargs.get("amount", kwargs.get("amount_paise", 0))
        curr = str(currency or kwargs.get("currency", "INR"))
        ref = str(kwargs.get("reference", "N/A"))

    fake_txn_id = f"sim_txn_{uuid.uuid4().hex[:12]}"
    now_ts = datetime.now(timezone.utc).isoformat()

    record = {
        "txn_id": fake_txn_id,
        "recipient": rec,
        "amount": amt,
        "currency": curr,
        "reference": ref,
        "timestamp": now_ts,
        "simulated": True,
    }
    _LEDGER.append(record)

    return {
        "simulated": True,
        "status": "simulated_success",
        "txn_id": fake_txn_id,
        "transaction_id": fake_txn_id,
        "recipient": rec,
        "amount": amt,
        "currency": curr,
        "reference": ref,
        "label": "[SIMULATED] No real money moved",
    }


# Backwards compatibility alias
def send_payment(params: Dict[str, Any]) -> Dict[str, Any]:
    """[SIMULATED] Alias for send(params)."""
    return send(params)
