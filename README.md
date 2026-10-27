# Epistemic Governor

**A deterministic governance layer that proves when a coding task is impossible instead of letting the agent hallucinate success.**

## The Problem

Coding agents do not just fail — they lie about succeeding. A 2026 study formally named this the **evidence-action gap**: across **19,371 trajectories** and eight frontier models, agents over-persist, attempt workarounds, and claim success the record does not support.

Existing escalation tools detect this after the fact. The Epistemic Governor removes the failure mode architecturally: it sits between the agent and the sandbox, forks state, tests each proposed action in isolation, and **halts** the agent when the same root-cause blocker appears across multiple distinct hypotheses — emitting a signed **impossibility certificate** that proves the task cannot be completed under current constraints.

The demo is binary: baseline agent lies → governed agent halts with proof.

## How It Works

```
Agent proposes action
        |
        v
+---------------------+
|  Epistemic Governor |
|                     |
|  fork sandbox state |
|  test action alone  |
|  same blocker x3?   |
|  YES -> HALT        |
|       emit certificate (signed, sha256) |
|  NO  -> continue    |
+---------------------+
        |
        v
Sandbox (forked, isolated)
```

1. **Fork** — before each agent action, the Governor checkpoints and forks the sandbox state.
2. **Test** — the action runs in the isolated fork; stdout/stderr/exit code are captured.
3. **Halt** — if ≥3 distinct hypotheses all share the same blocker signature, the Governor halts.
4. **Certify** — a signed, sha256-hashed impossibility certificate is produced, plus a human-readable escalation report.

## Results

_Table produced by `python demo/run_comparison.py` (see Reproducibility)._

| Metric | Value |
|--------|-------|
| Baseline false-successes | 12 / 12 |
| Governed halted | 12 / 12 |
| Governed false-successes | 0 / 12 |

Per-blocker baseline false-success is `True` on all 12 blockers; governed false-success is `False` on all 12 blockers (the Governor halts with an impossibility certificate in every case).

**The winning metric: governed false-success = 0 / 12.** Baseline false-success is non-zero across all blockers.

## Reproducibility

```bash
# Install
pip install -r requirements.txt

# Run unit tests (credential-free, uses mocks)
pytest tests/ -v

# Run the 12-blocker comparison (baseline vs governed)
python demo/run_comparison.py

# Launch the Gradio demo
python demo/app.py
```

## Setup

Required environment variables (for live Nebius/Nemotron mode; optional — the project runs credential-free with mocks otherwise):

- `NEBIUS_API_KEY` — Token Factory inference key
- `NEBIUS_PROJECT_ID` — Nebius project ID for Sandboxes

Install:

```bash
pip install contree-sdk openai pytest python-dotenv gradio
```

Copy `.env.example` to `.env` and fill in values when using live credentials. No credentials are committed to this repository.

## Feedback on Nebius and NVIDIA Tools

**How did the Contree Sandbox fork latency affect the Governor's design?**
Fork latency is the Governor's critical path: every agent action requires a sandbox fork, test, and teardown. To keep the loop responsive, the Governor forks from the latest checkpoint rather than cloning from the base image each time, and it reuses checkpoints across turns. High fork latency directly increases time-to-halt, so checkpoint reuse and parallel fork testing are the primary levers for production deployment.

**How did the Nemotron Super / Nano tiering affect cost and quality?**
The hackathon requires `nvidia/nemotron-3-super-120b-a12b` (Super tier) for the primary agent. Super-tier quality is needed for the agent to generate diverse, testable hypotheses; a Nano-tier model would produce too few distinct blockers to trigger the 3-hypothesis halt rule, increasing false negatives. Cost scales with turns; the Governor reduces cost by halting early instead of letting the agent burn tokens on workarounds.

**What friction did you encounter integrating OpenCode with Token Factory?**
Token Factory exposes an OpenAI-compatible endpoint, so the OpenAI Python client integrates with minimal changes. The main friction is credential management: the base URL (`https://api.tokenfactory.nebius.com/v1/`) and API key must be injected via environment variables, and sandbox orchestration (ConTree) is a separate control plane from inference, so the agent loop must coordinate two clients. Keeping credentials out of source control (`.env` + `.env.example`) is essential.

## License

MIT License. Copyright (c) 2026 Epistemic Governor Team.