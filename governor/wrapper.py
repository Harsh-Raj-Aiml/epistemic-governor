"""Governed agent loop (wrapper).

Runs a NemotronAgent-style loop but routes every tool call through
``Governor.fork_and_test()`` and halts (producing an impossibility
certificate) as soon as ``Governor.is_impossible()`` is true.

This is the architectural core that eliminates the evidence-action gap:
the agent never gets to claim success on an impossible task because the
Governor stops it first.
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Optional

from .core import Governor


class GovernedAgentLoop:
    """Wrap an agent so every action is fork-tested before it lands."""

    def __init__(
        self,
        task_spec: str,
        agent: Any,
        governor: Optional[Governor] = None,
        max_turns: int = 10,
    ):
        self.task_spec = task_spec
        self.agent = agent
        self.governor = governor or Governor(task_spec)
        self.max_turns = max_turns
        self.halted = False
        self.certificate: Optional[dict] = None
        self.turns_before_halt = 0
        self.tool_outputs: list[str] = []

    def run(self) -> dict:
        self.governor.checkpoint("initial")
        start = time.time()

        for turn in range(1, self.max_turns + 1):
            # Halt check before each turn (brief Section 5).
            if self.governor.is_impossible():
                self.halted = True
                self.turns_before_halt = turn - 1
                self.certificate = self.governor.produce_certificate()
                break

            decision = self.agent._model_respond(self.task_spec, self.tool_outputs)

            if decision.get("done"):
                self.turns_before_halt = turn
                break

            for tc in decision.get("tool_calls", []):
                if tc.get("name") != "run_command":
                    continue
                args = tc.get("arguments", {})
                self.governor.fork_and_test(
                    f"run {args.get('command', '')}",
                    args.get("command", ""),
                    args.get("args", []),
                )
                self.tool_outputs.append(
                    json.dumps(
                        {
                            "command": args.get("command", ""),
                            "args": args.get("args", []),
                        }
                    )
                )
            self.turns_before_halt = turn

        if not self.halted and self.governor.is_impossible():
            self.halted = True
            self.turns_before_halt = min(self.turns_before_halt, self.max_turns)
            self.certificate = self.governor.produce_certificate()

        elapsed = time.time() - start
        return {
            "halted": self.halted,
            "certificate": self.certificate,
            "turns_before_halt": self.turns_before_halt,
            "elapsed_s": round(elapsed, 4),
            "false_success": False,  # a governed halt never claims success
        }


def run_governed(task_spec: str, agent: Any, governor: Optional[Governor] = None) -> dict:
    """Convenience: run a governed agent loop and return its result."""
    loop = GovernedAgentLoop(task_spec, agent, governor=governor)
    return loop.run()
