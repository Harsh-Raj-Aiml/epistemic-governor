"""Escalation report generator.

Writes a human-readable Markdown report and a JSON copy of the certificate.
This is the artifact the evidence-action gap paper says existing escalation
tools omit: agent progress + verification status together.
"""

from __future__ import annotations

import json
import os
from typing import Any


def write_report(certificate: dict, output_dir: str = "reports") -> tuple[str, str]:
    """Write {hash[:12]}.md and {hash[:12]}.json. Return both paths."""
    cert_hash = certificate.get("certificate_hash", "unknown")
    short = cert_hash[:12]
    os.makedirs(output_dir, exist_ok=True)

    md_path = os.path.join(output_dir, f"{short}.md")
    json_path = os.path.join(output_dir, f"{short}.json")

    md = _render_markdown(certificate)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(certificate, f, indent=2)

    return md_path, json_path


def _render_markdown(certificate: dict) -> str:
    lines: list[str] = []
    lines.append("# Escalation Report — Impossibility Certificate")
    lines.append("")
    lines.append("## Task Specification")
    lines.append("")
    lines.append(certificate.get("task_spec", ""))
    lines.append("")
    lines.append("## Verdict: IMPOSSIBLE")
    lines.append("")
    lines.append("## Root Cause")
    lines.append("")
    lines.append(certificate.get("blocker_signature", ""))
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    lines.append("| hypothesis | command | exit_code | stderr snippet |")
    lines.append("|------------|---------|-----------|----------------|")
    for fork in certificate.get("impossibility_forks", []):
        hypothesis = fork.get("hypothesis", "")
        command = fork.get("command", "")
        args = " ".join(fork.get("args", []))
        full_command = f"{command} {args}".strip()
        exit_code = fork.get("exit_code", "")
        stderr = (fork.get("stderr") or "").replace("\n", " ")
        snippet = stderr[:120]
        lines.append(f"| {hypothesis} | {full_command} | {exit_code} | {snippet} |")
    lines.append("")
    lines.append("## Search Space Exhausted")
    lines.append("")
    for cid in certificate.get("checkpoints", []):
        lines.append(f"- {cid}")
    lines.append("")
    lines.append("## Certificate Hash")
    lines.append("")
    lines.append(certificate.get("certificate_hash", ""))
    lines.append("")
    lines.append("## Human Action Required")
    lines.append("")
    lines.append(
        "The agent could not complete the task because of the root cause above. "
        "A human should verify the blocker (e.g., install the missing dependency, "
        "restore network access, fix permissions, or correct the endpoint) before "
        "unblocking the agent. The certificate hash above can be re-verified with "
        "`governor.certificate.verify(certificate)`."
    )
    lines.append("")
    return "\n".join(lines)
