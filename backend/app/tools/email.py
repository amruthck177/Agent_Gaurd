"""
backend/app/tools/email.py

[SIMULATED] Simulated email tool — no real email sent.
LABEL: [SIMULATED] — shown in UI.
Appends to an in-memory outbox and returns a fake message id.
Only imported and invoked by gateway.py after all security checks pass.
All tools print nothing sensitive and are clearly labelled SIMULATED in docstrings
and return payloads ({"simulated": true}).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# In-memory outbox storing simulated sent emails
_OUTBOX: List[Dict[str, Any]] = []


def get_outbox() -> List[Dict[str, Any]]:
    """[SIMULATED] Returns a copy of all emails in the simulated outbox."""
    return list(_OUTBOX)


def clear_outbox() -> None:
    """[SIMULATED] Clears the in-memory simulated email outbox."""
    _OUTBOX.clear()


def send(
    to: Any = None,
    subject: str = "",
    body: str = "",
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    [SIMULATED] Executes a simulated email dispatch.
    Appends the message to an in-memory outbox and returns a fake message id.
    Prints nothing sensitive.

    Accepts either positional/keyword arguments (to, subject, body)
    or a params dict as the first argument.
    """
    if isinstance(to, dict) and not subject and not body:
        params = to
        to_addr = params.get("to", params.get("recipient", "unknown"))
        subj = str(params.get("subject", "(no subject)"))
        body_text = str(params.get("body", ""))
        has_attachment = bool(params.get("has_attachment") or params.get("attachments"))
    else:
        to_addr = to if to is not None else kwargs.get("to", kwargs.get("recipient", "unknown"))
        subj = str(subject or kwargs.get("subject", "(no subject)"))
        body_text = str(body or kwargs.get("body", ""))
        has_attachment = bool(kwargs.get("has_attachment") or kwargs.get("attachments"))

    fake_msg_id = f"sim_email_{uuid.uuid4().hex[:12]}"
    now_ts = datetime.now(timezone.utc).isoformat()

    record = {
        "message_id": fake_msg_id,
        "to": to_addr,
        "subject": subj,
        "body": body_text,
        "has_attachment": has_attachment,
        "timestamp": now_ts,
        "simulated": True,
    }
    _OUTBOX.append(record)

    return {
        "simulated": True,
        "status": "simulated_success",
        "message_id": fake_msg_id,
        "to": to_addr,
        "subject": subj,
        "has_attachment": has_attachment,
        "label": "[SIMULATED] No real email sent",
    }


# Backwards compatibility alias
def send_email(params: Dict[str, Any]) -> Dict[str, Any]:
    """[SIMULATED] Alias for send(params)."""
    return send(params)
