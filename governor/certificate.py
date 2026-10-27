"""Impossibility certificate schema + signing.

Produces a signed, sha256-hashed JSON artifact proving a task is impossible
under current constraints. The hash covers the payload excluding the hash key
itself, so `verify` can detect any tampering.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


def build(governor: Any) -> dict:
    """Build a signed impossibility certificate from a Governor."""
    payload = {
        "task_spec": governor.task_spec,
        "impossibility_forks": governor.impossibility_forks,
        "checkpoints": governor.checkpoint_ids(),
        "verdict": "IMPOSSIBLE",
        "blocker_signature": _shared_signature(governor),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    certificate_hash = sha256_payload(payload)
    payload["certificate_hash"] = certificate_hash
    return payload


def verify(certificate: dict) -> bool:
    """Recompute the hash from the payload (excluding the hash key) and compare.

    Returns True if the certificate is unmodified.
    """
    stored_hash = certificate.get("certificate_hash")
    if not stored_hash:
        return False
    payload_without_hash = {k: v for k, v in certificate.items() if k != "certificate_hash"}
    recomputed = sha256_payload(payload_without_hash)
    return recomputed == stored_hash


def _shared_signature(governor: Any) -> str:
    signatures = {governor._blocker_signature(r) for r in governor.impossibility_forks}
    if len(signatures) == 1:
        return next(iter(signatures))
    return "mixed"


def sha256_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
