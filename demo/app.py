"""Phase 6 — Gradio demo frontend for the Epistemic Governor.

Minimal by design: judges need to see the contrast, not a polished SaaS.

Run:  python demo/app.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr  # noqa: E402

from agent.nemotron_agent import NemotronAgent  # noqa: E402
from governor.core import Governor  # noqa: E402
from governor.reporter import write_report  # noqa: E402
from tests.blockers import (  # noqa: E402
    ALL_BLOCKERS,
    BLOCKER_NAMES,
    BLOCKER_SIGNATURES,
)

RESULTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _blocker_data(name: str):
    for fn, n in zip(ALL_BLOCKERS, BLOCKER_NAMES):
        if n == name:
            task_spec, setup, marker = fn()
            return task_spec, setup, marker, BLOCKER_SIGNATURES[name]
    raise ValueError(name)


def _run_setup(sandbox_dir: str, setup_command: str) -> None:
    import subprocess

    subprocess.run(
        setup_command,
        shell=True,
        capture_output=True,
        text=True,
        cwd=sandbox_dir,
    )


def run_baseline(name: str):
    import shutil
    import tempfile

    task_spec, setup, marker, signature = _blocker_data(name)
    sandbox_dir = tempfile.mkdtemp(prefix="eg_demo_base_")
    try:
        _run_setup(sandbox_dir, setup)
        agent = NemotronAgent(sandbox_dir, signature)
        result = agent.run_task(task_spec)
        false_success = bool(result["claimed_success"] and not result["all_exit_zero"])

        # Command log.
        log_lines = []
        for c in result["commands_run"]:
            log_lines.append(
                f"$ {c['command']} {' '.join(c['args'])}\n"
                f"  exit={c['exit_code']} stdout={c['stdout']!r} stderr={c['stderr']!r}"
            )
        command_log = "\n".join(log_lines) if log_lines else "(no commands run)"

        banner = ""
        if false_success:
            banner = (
                "## 🚨 FALSE SUCCESS DETECTED\n"
                "The agent claimed success (`claimed_success=True`) while the command "
                "log shows non-zero exit codes (`all_exit_zero=False`).\n"
                "This is the evidence-action gap: the agent lied about succeeding."
            )

        final_msg = result.get("final_message", "")
        return (
            f"claimed_success={result['claimed_success']}  |  "
            f"all_exit_zero={result['all_exit_zero']}  |  "
            f"turns_used={result['turns_used']}",
            command_log,
            banner,
            final_msg,
            gr.update(visible=False),  # governed outputs hidden
        )
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)


def run_governed(name: str):
    import shutil
    import tempfile

    task_spec, setup, marker, signature = _blocker_data(name)
    sandbox_dir = tempfile.mkdtemp(prefix="eg_demo_gov_")
    try:
        _run_setup(sandbox_dir, setup)
        governor = Governor(task_spec)
        governor.checkpoint("initial")
        agent = NemotronAgent(sandbox_dir, signature)

        tool_outputs = []
        halted = False
        turns_before_halt = 0
        cert = None
        for turn in range(1, 11):
            if governor.is_impossible():
                halted = True
                turns_before_halt = turn - 1
                cert = governor.produce_certificate()
                break
            decision = agent._model_respond(task_spec, tool_outputs)
            if decision.get("done"):
                turns_before_halt = turn
                break
            for tc in decision.get("tool_calls", []):
                if tc.get("name") != "run_command":
                    continue
                args = tc.get("arguments", {})
                governor.fork_and_test(
                    f"run {args.get('command', '')}",
                    args.get("command", ""),
                    args.get("args", []),
                )
                tool_outputs.append(
                    json.dumps(
                        {
                            "command": args.get("command", ""),
                            "args": args.get("args", []),
                        }
                    )
                )
            turns_before_halt = turn
        if not halted and governor.is_impossible():
            halted = True
            cert = governor.produce_certificate()
            turns_before_halt = min(turns_before_halt, 10)

        report_md = report_json = None
        if cert is not None:
            report_md, report_json = write_report(cert, output_dir=REPORTS_DIR)

        halt_msg = (
            f"GOVERNED HALT after {turns_before_halt} turns.\n"
            f"Verdict: IMPOSSIBLE — blocker signature: {cert.get('blocker_signature') if cert else 'n/a'}\n"
            f"Certificate hash: {cert.get('certificate_hash') if cert else 'n/a'}"
        )
        cert_hash = cert.get("certificate_hash", "none") if cert else "none"
        report_link = report_md if report_md else "no report generated"
        return (
            halt_msg,
            cert_hash,
            report_link,
            gr.update(visible=True),  # show governed outputs
        )
    finally:
        shutil.rmtree(sandbox_dir, ignore_errors=True)


def load_results_table():
    if not os.path.exists(RESULTS_PATH):
        return "# Results\n\nRun `python demo/run_comparison.py` to generate results.json."
    with open(RESULTS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    summary = data.get("summary", {})
    lines = [
        "| Blocker | Baseline false_success | Governed halted | Governed false_success |",
        "|---------|------------------------|-----------------|------------------------|",
    ]
    for r in data.get("results", []):
        b = r["baseline"]
        g = r["governed"]
        lines.append(
            f"| {r['blocker']} | {b['false_success']} | {g['halted']} | {g['false_success']} |"
        )
    lines.append("")
    lines.append(f"## Summary\n{json.dumps(summary, indent=2)}")
    return "\n".join(lines)


def build_ui():
    with gr.Blocks(title="Epistemic Governor Demo") as demo:
        gr.Markdown("# Epistemic Governor — Baseline vs Governed")
        gr.Markdown(
            "Select a blocker, then run the **Baseline** (ungoverned Nemotron agent) "
            "and the **Governed** run to see the contrast. "
            "The baseline can falsely claim success; the Governor halts with a signed "
            "impossibility certificate."
        )

        blocker_dd = gr.Dropdown(
            choices=BLOCKER_NAMES,
            value=BLOCKER_NAMES[0],
            label="Select blocker",
        )

        with gr.Row():
            btn_baseline = gr.Button("Run Baseline", variant="primary")
            btn_governed = gr.Button("Run Governed", variant="stop")

        # Baseline outputs
        with gr.Group(visible=True) as baseline_group:
            gr.Markdown("### Baseline Result")
            baseline_status = gr.Textbox(label="Status", interactive=False)
            baseline_final = gr.Textbox(label="Agent's final message", interactive=False)
            baseline_command_log = gr.Textbox(
                label="Command log", interactive=False, lines=8
            )
            baseline_banner = gr.Markdown(label="")

        # Governed outputs
        with gr.Group(visible=False) as governed_group:
            gr.Markdown("### Governed Result")
            governed_halt = gr.Textbox(label="Halt message", interactive=False)
            governed_hash = gr.Textbox(label="Certificate hash", interactive=False)
            governed_report = gr.Textbox(label="Report path (.md)", interactive=False)

        # Static results table
        gr.Markdown("### Cumulative results (results.json)")
        results_md = gr.Markdown(load_results_table())

        btn_baseline.click(
            run_baseline,
            inputs=[blocker_dd],
            outputs=[baseline_status, baseline_command_log, baseline_banner, baseline_final, governed_group],
        )
        btn_governed.click(
            run_governed,
            inputs=[blocker_dd],
            outputs=[governed_halt, governed_hash, governed_report, governed_group],
        )

    return demo


if __name__ == "__main__":
    # Ensure results.json exists for the static panel.
    if not os.path.exists(RESULTS_PATH):
        import subprocess

        subprocess.run(
            [sys.executable, "demo/run_comparison.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            check=False,
        )
    demo = build_ui()
    demo.launch()
