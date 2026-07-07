"""The task contract (ADR 010): compile → emit → fulfill → submit → apply.

- `compiler` builds budgeted prompts from store state (I6).
- `service` owns the lifecycle: emitting Task records and applying validated
  results — the only path by which AI output mutates state (I5).
"""
