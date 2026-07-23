# RESTRAINT sampling block — spend plan draft (2026-07-23 ~00:20, step-3 prep)

Status: step 3 of the RESUME header — "needs explicit spend decision".
Owner spend policy (memory + PROMPT_LAB): codex runs VERY sparingly; free
evidence first, one targeted validation run. This draft is the decision aid;
DO NOT EXECUTE without either owner confirmation or a clear reading that the
standing grant covers it (the header itself says "confirm with owner if in
doubt" — there IS doubt at ~20 calls, so the default is ASK via QUESTIONS).

## What the block buys

The restraint hard-set residual is 4 scenarios (plateau_remediation,
no_retirement_from_phase_pass, atrophy warm-up create, resolution_amid
strategy non-null) with a measured bimodal/plateau history:
- plateau_remediation: 0.125×2 baseline · 0.625×2 under BOTH-qualifier
  bundle · one 1.00 outlier — declared "unusable below n=5" (standing rule).
- MAINT (#12, adopted) shipped the maintenance qualifier; its gate-2 samples
  passed but the class plateaued below clearing the hard set.

n=5 sampling of plateau_remediation (and only it) under the CURRENT tree
makes the scenario measurable at all: median-of-5 becomes the reference
number future arms adjudicate against (kills the single-sample lottery that
burned the campaign twice).

## Cost

- Minimal form: plateau_remediation ×5 = ~5 judged calls (each -k run
  compiles + judges 1 scenario). NOT the full 4-scenario ×5 = 20 calls.
- Recommendation to owner: authorize the 5-call minimal form first; the
  other 3 restraint scenarios only get sampled when a new-mechanism arm
  actually targets them (none is pre-registered — "no new mechanism —
  parked" stands).

## Command (×5, serial, stdin closed)

DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only" python -m pytest -m eval -q -k "plateau_remediation" </dev/null

## Decision rule (pre-registered NOW, before any data)

- Record all 5 totals; the scenario's reference level = median.
- Median ≥0.625: MAINT's effect held; hard-set entry stays "plateau —
  no new mechanism"; only a new-mechanism arm may move it.
- Median ≤0.25: MAINT's plateau effect did NOT survive the current tree —
  re-open the qualifier-interaction question (PLAT-INT precedent) as a
  properly pre-registered arm.
- Anything else: bimodality confirmed at n=5; the scenario is a
  variance-caution flag in every future adjudication that includes it.
- NO template edit follows from this block alone (it is measurement, not an
  arm); no ratchet moves (floors move on wins only).
