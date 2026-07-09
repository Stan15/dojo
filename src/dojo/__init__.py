"""Dojo: a local-first, source-to-practice learning app.

You capture what you want to learn; dojo turns it into scheduled practice.
The architecture has two halves (ADR 010/012):

- A **deterministic core** — FSRS spaced-repetition scheduling
  (`scheduling`, `outcomes`), daily packet building (`packet`), validation
  (`schemas`, `limits`), and storage as git-versioned markdown (`store`).
- **AI as validated tasks** — anything needing judgment (generating
  exercises, grading, reflection, planning, routing captures) is compiled
  into a byte-budgeted prompt (`tasks.compiler`), emitted as a pending task,
  and fulfilled by ANY model through one validated door
  (`tasks.service.submit`). The system never blocks on AI.

Entry points: `cli` (the `dojo` command — JSON envelopes for agents,
interactive flows for humans via `interactive`), `api.DojoAPI` (the Python
façade both use), and `evals` (the model benchmark harness).
"""
