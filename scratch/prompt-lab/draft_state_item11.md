# Draft — STATE item 11 (codex validation numbers still pending)

11. **DONE 2026-07-19 — drop-diagnosis iteration (fresh session, holdout
   blindness intact; STATE 10d queue executed on visible traces only;
   landed as d69ff5c templates+gates, fb9fe04 corpus, 03d466d README).**
   a0. **P1 letter-bleed regression caught by pre-registered mini-
      batteries mid-iteration**: the first depth-rule rewrite embedded
      abstract letter-path literals (a.b.c.d_e / a.b.c.d.e); 4B models
      copied them as content (gemma plan 5/9→2/9, literal fused paths
      like a.pod_b.service_c). Words-only restatement recovered gemma to
      7/9 (ABOVE its 5/9 baseline) and qwen to 4/9 (rep2, pre-reg bar),
      with zero letter-path outputs across all 27 verification rows.
      Forensics note: two earlier qwen verification runs were VOIDED
      honestly (machine resource starvation; then 3-worker GPU
      contention timeouts) — plan-only minis now run workers=1.
   a. All 8 targets diagnosed from the two 2026-07-18 run traces; root
      causes template/harness-side, none scenario-specific:
      - reflect_mixed_signals (1.0→0.56/0.67): floundering rule fired
        globally on single-topic struggle → rule 2 now states dials are
        GLOBAL (topic-confined struggle = insight + scaffolding-with-
        named-topic, difficulty held).
      - inferred_restructure_probe (0.89→0.67/0.67): "plan untouched"
        ended the response; rule 4 now names prerequisite-gap/blocker
        suspicion + collapsing-phase-with-silent-feedback as the ASK case.
      - mastery_resolution (1.0→0.875 both): journal named evidence but
        not the resolution → rule 6 records what CHANGED with evidence;
        skeleton journal example demonstrates op-naming.
      - plan_extend_not_duplicate (validation-failed BOTH runs, 5-level
        paths): depth was a rejecting validator absent from plan's Check
        line (the invisible-floor class) → Check states it; rule 1 shows
        the never-form (a.b.c.d_e, never a.b.c.d.e).
      - present_before_probing (0.0, floorless): present-trigger was
        permission, not duty → compiler-emitted FIRST CONTACT fragment
        (registered topic + zero attempts + no source); no_present guard
        fragment for practiced/grounded; residual neutral.
      - generate_downward_calibration (0.3 unmoved): the 10b model-side
        struggle conditional never fired at any caliber → branch moved
        into the compiler (calibration_struggle fragment; suppressed when
        scaffolding already high — chain_strategy scenario proves dials
        already responded).
      - grade_learner_language (0.67 unmoved): not language — the generic
        0.3 band overrode the rubric's explicit partial-credit grant →
        rule 2 "RUBRIC WINS".
      - diagnostic pair (~0.6): axis_coverage was a JUDGE artifact (honest
        multi-quote pass discarded as unproven — fixed free-tier,
        3c3041f); respects_known_insights re-asked narrowed goals → rule
        2 "narrower/rephrased is still a re-ask".
   b. Empty-INSIGHTS reflect skeleton (INSIGHTS 2026-07-18) shipped:
      compiler branch — create-first ops example + "(create is the only
      valid op)" section line when the store has zero active insights.
   c. learning_loop_chain (0.75→0.625): beginner one-decision-per-item +
      mission-anchoring rules in generate.
   d. Both directions gated: battery re-measure (iterW qwen3.5:4b +
      gemma3:4b) + output-budget rebuild in the template commit;
      footprint updated deliberately (reflect 6509→6995B, +7.5% — priced
      by three weight-3 criteria across two dropped scenarios).
   e. Route URL-bleed visible scenario authored (routing 7→8, total 79→80).
   f. README weak-model demo retry: qwen3.5:4b --no-think landed a
      content-good reflect in 2/2 production budgets (evidence-cited
      insights, coherent journal; in-budget retries absorbed early
      misses). README reflection claim updated with the measured tag
      (03d466d).
   g. Codex validation RUN UNDER THE PROMPT_LAB GRANT (owner-authorized
      2026-07-19): [RESULTS PENDING — fill floors recovered/bootstrapped
      + ratchet commit hash]. Holdout release gate re-trigger remains
      owner-only, untouched.
