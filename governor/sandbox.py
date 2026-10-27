"""Local (credential-free) sandbox used by the Governor.

Replaces the ConTree sandbox for offline/hackathon use. Each checkpoint is a
temporary directory snapshot of a base sandbox. Forking copies a checkpoint
directory and runs a command inside it, capturing stdout/stderr/exit code.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int


class LocalSandbox:
    """A local sandbox whose state lives in temp directories.

    checkpoints: dict[str, path] mapping checkpoint id -> directory path.
    """

    def __init__(self, base_commands: Optional[list[list[str]]] = None):
        self._base_dir = tempfile.mkdtemp(prefix="eg_base_")
        self.checkpoints: dict[str, str] = {}
        self._latest_checkpoint_id: Optional[str] = None
        if base_commands:
            for cmd in base_commands:
                self.run(cmd[0], cmd[1:])

    def run(self, command: str, args: list[str]) -> CommandResult:
        """Run a command directly in the base sandbox (no fork)."""
        completed = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            cwd=self._base_dir,
        )
        return CommandResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
        )

    def checkpoint(self, label: str) -> str:
        """Snapshot the current base state into a new checkpoint dir."""
        checkpoint_id = str(uuid.uuid4())
        checkpoint_dir = tempfile.mkdtemp(prefix=f"eg_ckpt_{checkpoint_id[:8]}_")
        # Copy current base state into the checkpoint directory.
        if os.path.exists(self._base_dir):
            for item in os.listdir(self._base_dir):
                src = os.path.join(self._base_dir, item)
                dst = os.path.join(checkpoint_dir, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
        self.checkpoints[checkpoint_id] = checkpoint_dir
        self._latest_checkpoint_id = checkpoint_id
        return checkpoint_id

    def latest_checkpoint_id(self) -> Optional[str]:
        return self._latest_checkpoint_id

    def fork_and_test(
        self, hypothesis: str, command: str, args: list[str]
    ) -> dict:
        """Fork from the latest checkpoint and run the command in isolation."""
        base_checkpoint = self._latest_checkpoint_id
        if base_checkpoint is None:
            base_checkpoint = self.checkpoint("initial")
        fork_dir = tempfile.mkdtemp(prefix=f"eg_fork_{uuid.uuid4().hex[:8]}_")
        # Copy checkpoint contents into the fork.
        src = self.checkpoints[base_checkpoint]
        if os.path.exists(src):
            for item in os.listdir(src):
                s = os.path.join(src, item)
                d = os.path.join(fork_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d)
                else:
                    shutil.copy2(s, d)
        fork_id = str(uuid.uuid4())
        try:
            completed = subprocess.run(
                [command, *args],
                capture_output=True,
                text=True,
                cwd=fork_dir,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            exit_code = completed.returncode
        except FileNotFoundError as exc:
            stdout = ""
            # Emit a POSIX-style message so the Governor's blocker signature
            # detector ("No such file or directory") fires on every platform,
            # including Windows where the native message differs.
            stderr = f"FileNotFoundError: [Errno 2] No such file or directory: {command}"
            exit_code = 127
        except Exception as exc:  # pragma: no cover - defensive
            stdout = ""
            stderr = f"{type(exc).__name__}: {exc}"
            exit_code = 1
        finally:
            shutil.rmtree(fork_dir, ignore_errors=True)

        return {
            "hypothesis": hypothesis,
            "command": command,
            "args": list(args),
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "fork_id": fork_id,
            "base_checkpoint": base_checkpoint,
        }

    def cleanup(self) -> None:
        shutil.rmtree(self._base_dir, ignore_errors=True)
        for d in list(self.checkpoints.values()):
            shutil.rmtree(d, ignore_errors=True)
        self.checkpoints.clear()
