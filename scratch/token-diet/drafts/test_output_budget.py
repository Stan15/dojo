"""DRAFT (lands as tests/test_output_budget.py in the winner commit).

Output-side twin of test_token_footprint.py (owner directive 2026-07-17:
prompt work and token work are mutually non-regressing, BOTH tested).

The committed baseline (evals/baselines/output-budget.json) records, per
measurement driver, per task kind: single-shot ok-rate and median raw output
bytes per SUCCESSFUL task, measured over the visible quality corpus by
scratch-descended tooling (one driven step per scenario, whole-trace bytes).

Two gates:
  1. Coherence (default gate, free): the baseline file exists, covers every
     task kind, and its recorded template-set hash matches the current
     src/dojo/prompts content — a template edit without a re-measure + baseline
     update in the same commit fails loudly.
  2. Ratchet (opt-in, real models): with DOJO_TOKEN_DRIVER set, re-measures
     the corpus and asserts per kind: ok-rate not down more than noise
     (±1 scenario), bytes/success not up more than tolerance (+5%).
     Improvements auto-ratchet by updating the baseline in the same commit.

Driver labels are explicit (e.g. "api-chat/qwen3.5:4b/--no-think") — a
baseline is only comparable to runs with its own driver (measurement ruling
2026-07-18: the driver is part of measurement config).
"""
# Implementation lands with the winner commit; shape:
#   measure_corpus(driver) -> {kind: {"n": int, "ok": int, "bytes_ok_median": int}}
#   test_output_budget_baseline_coherent()          # default gate
#   @pytest.mark.eval_tokens
#   test_output_budget_ratchet()                    # opt-in real-model gate
