"""Epistemic Governor core.

The Governor sits between a coding agent and its sandbox. Before each agent
action it forks sandbox state, tests the action in isolation, and halts the
agent when the same root-cause blocker appears across multiple distinct
hypotheses — emitting a signed impossibility certificate.
"""

from __future__ import annotations

from typing import Any

from .certificate import build
from .sandbox import LocalSandbox


class Governor:
    """Deterministic governance layer over a sandbox."""

    BLOCKER_SIGNATURES = [
        "ModuleNotFoundError",
        "ImportError",
        "PermissionError",
        "ConnectionRefused",
        "No such file or directory",
        "404",
        "401",
        "403",
        "ENOENT",
    ]

    def __init__(self, task_spec: str):
        self.task_spec = task_spec
        self.sandbox = LocalSandbox()
        self.checkpoints: list[tuple[str, str]] = []  # (id, label)
        self.impossibility_forks: list[dict] = []
        self.proven_impossible = False

    # ------------------------------------------------------------------
    # Checkpoint / fork API
    # ------------------------------------------------------------------
    def checkpoint(self, label: str) -> str:
        checkpoint_id = self.sandbox.checkpoint(label)
        self.checkpoints.append((checkpoint_id, label))
        return checkpoint_id

    def fork_and_test(
        self, hypothesis: str, command: str, args: list[str]
    ) -> dict:
        record = self.sandbox.fork_and_test(hypothesis, command, args)
        if self._indicates_impossibility(record):
            self.impossibility_forks.append(record)
        return record

    # ------------------------------------------------------------------
    # Impossibility detection
    # ------------------------------------------------------------------
    def _indicates_impossibility(self, result: dict) -> bool:
        if result.get("exit_code", 0) == 0:
            return False
        stderr = result.get("stderr", "") or ""
        return any(sig in stderr for sig in self.BLOCKER_SIGNATURES)

    def _blocker_signature(self, record: dict) -> str:
        stderr = record.get("stderr", "") or ""
        for sig in self.BLOCKER_SIGNATURES:
            if sig in stderr:
                return sig
        return "unknown"

    def is_impossible(self) -> bool:
        """True iff >=3 impossibility forks share ONE blocker signature.

        Conservative rule: prevents premature halting. Requires at least 3
        distinct hypotheses all producing the same single blocker signature.
        """
        if len(self.impossibility_forks) < 3:
            return False
        signatures = {self._blocker_signature(r) for r in self.impossibility_forks}
        if len(signatures) != 1:
            return False
        return True

    # ------------------------------------------------------------------
    # Certificate
    # ------------------------------------------------------------------
    def produce_certificate(self) -> dict:
        self.proven_impossible = True
        return build(self)

    # ------------------------------------------------------------------
    # Convenience: run the governed agent loop
    # ------------------------------------------------------------------
    def checkpoint_ids(self) -> list[str]:
        return [cid for cid, _ in self.checkpoints]
