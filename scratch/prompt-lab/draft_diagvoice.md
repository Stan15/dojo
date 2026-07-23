# DIAGVOICE draft-ahead (prepared 2026-07-23 ~00:15 during vrec qwen battery)

Pre-reg: WORKBENCH "DIAGVOICE (pre-registered 2026-07-20 ~22:20)". Single
variable, compiler-only (craft rule 5), no template change. APPLY ONLY after
VERB-RECALL adjudicates (serial arms, quiet tree until battery bkpiwbtqp done).

## Verified facts (this session)

- Clip site: src/dojo/tasks/compiler.py:599-601 (glimpse 48 → 47+ellipsis).
- Trigger field: Exercise.quality == "diagnostic" (schemas.py:650 docstring
  lists "diagnostic" as a quality value; fixture reflect_diagnostic_voice_revision.yaml
  ex_4 has `quality: diagnostic`).
- att_4 user_answer is 111 chars; clip cuts at "...please drop machi…" — every
  judged token (patches/buttons/field hems) is in the clipped half. 240-char
  limit covers it whole.
- compiler.py:578 already iterates store.exercises.list(campaign.id) to build
  topic_of — extend to also capture quality per exercise id (no extra store call).

## Exact diff (compiler.py)

Edit 1 — line 578:
  OLD: topic_of = {ex.id: ex.topic_path for ex in store.exercises.list(campaign.id)}
  NEW: exercises_by_id = {ex.id: ex for ex in store.exercises.list(campaign.id)}
       topic_of = {ex_id: ex.topic_path for ex_id, ex in exercises_by_id.items()}
  (or keep topic_of and add a quality map — pick the minimal-churn form at
  apply time; goldens/comments unaffected either way)

Edit 2 — lines 599-601:
  OLD:
        glimpse = (a.user_answer or "").strip().replace("\n", " ")
        if len(glimpse) > 48:
            glimpse = glimpse[:47] + "…"
  NEW (mechanism: a diagnostic answer IS the learner's voice — rule 4 promises
  it returns as citable evidence, so it renders whole up to 240):
        glimpse = (a.user_answer or "").strip().replace("\n", " ")
        ex_q = exercises_by_id.get(a.exercise_id)
        limit = 240 if ex_q is not None and ex_q.quality == "diagnostic" else 48
        if len(glimpse) > limit:
            glimpse = glimpse[: limit - 1] + "…"
  (row_budget at line 610 still bounds the section — pre-reg notes this.)

## Gates (pre-registered bars)

Gate 1 (local, free, serial — ONE battery at a time), 30-scenario reflect set
(stems below), workers 2. Baselines = MAINT-era: qwen 18/30, gemma 25/30; flat
= within ±3 both.

  python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py qwen3.5:4b --no-think" scratch/token-diet/baselines/diagvoice_qwen_reflect.jsonl 2 atrophy_reentry chain_reflect_then chain_strategy_change implicit_ease inferred_restructure learning_loop_chain legitimate_restructure mastery_resolution no_retirement overconfident_fast plateau_remediation premature_resolution reflect_ resolution_amid resolution_despite restructure_minimal retire_on_learner too_easy_calibration too_hard_scaffolding
  python scratch/token-diet/measure.py "python scratch/token-diet/api_driver.py gemma3:4b" scratch/token-diet/baselines/diagvoice_gemma_reflect.jsonl 2 <same filters>

  (filter check before launch: the 19 filters above must select EXACTLY the 30
  maint-set scenarios — verify with a dry glob first.)

Gate 2 (judged, ~4 codex calls): ×2 samples
  DOJO_EVAL_DRIVER="codex exec --skip-git-repo-check -s read-only" python -m pytest -m eval -q -k "reflect_diagnostic_voice" </dev/null
  Bars: c1+c3 pass BOTH samples AND total ≥0.75 both. Byte cost recorded
  (~+150B on diagnostic-bearing payloads only).

## Adopt mechanics (same commit)

- output-budget rebuild (payload bytes move on diagnostic-bearing reflect
  payloads) + token-footprint baseline if the ±5% gate trips + any golden
  regen. Full pytest green. Stage files BY NAME (never git add -A; the
  __holdout baseline mod is OWNER-ONLY).
- FINDINGS.md register row + BLOG_MATERIAL.md capture + WORKBENCH adjudication.

## Revert mechanics

git checkout src/dojo/tasks/compiler.py; record negative in WORKBENCH.
