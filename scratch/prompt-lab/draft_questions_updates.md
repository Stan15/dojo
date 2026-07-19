# Draft QUESTIONS.md edits (apply at session end)

## Progress board changes
- Flip "[ ] Fresh session (prompt authority...)" to [x]:
  - [x] Drop-diagnosis iteration (fresh session): 5 stable drops + 3 unmoved
        floors + present_before_probing diagnosed from the two runs' traces;
        root fixes at template/compiler/judge level, never scenario-specific.
        Judge multi-quote fix 3c3041f; template+compiler commit <SHA2>;
        route-bleed scenario <SHA3>. Battery re-measured (iterW), output
        budgets rebuilt same commit.
  - Weak-model README demo item: update with result (<RESULT>).

## New open question (codex bootstrap)
0b. **Post-iteration codex validation + floor bootstraps (2026-07-19).**
   The drop-diagnosis fixes are template-level and verified by the free
   gates + local 4B batteries; the codex-tier floors that DROPPED
   (mixed_signals, probe, mastery, plan_extend, loop_chain) and the new
   routing scenario's floor need one authorized run to confirm/bootstrap:
   `-m eval` full visible run (~90 calls) — ratchets update same commit.
   After the drops are confirmed recovered, you re-trigger the holdout
   release gate yourself (I never run it).
   **Default: awaiting your green light; no spend until then.**
