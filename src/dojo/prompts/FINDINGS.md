# PER-TEMPLATE FINDINGS REGISTER — read WITH README.md before editing

_README.md carries the cross-cutting failure modes (1-11) and measured
dead ends; THIS file is the per-template ledger: what each template has
WON (preserve it — the mechanism tells you which edits would break it)
and what was TRIED AND FAILED (don't re-till without new evidence).
Every entry cites its battery data (scratch/token-diet/baselines/) or
test. A template edit that contradicts a WIN here needs a pre-registered
arm proving the win survives. Drift gate: tests/test_prompts.py asserts
every template has a section here._

## campaign_reflect.md

WINS TO PRESERVE
- Example values in the ops fragments are DOMAIN-ORTHOGONAL (calligraphy)
  — plausible values bled verbatim into 59%/33% of gemma/qwen outputs as
  silent insight-store pollution (EX-BLEED, iterEXB_*). Never swap in
  plausible-domain examples; check the corpus before picking a new domain.
- The create example is SUPPRESSED when real insights exist (EXB2,
  compiler-side, test-enforced: test_reflect_with_insights_shows_update_
  example_only). 12/14 surviving bleed copies were the create op.
- W1's verbosity guard (codex judged 3 SUBSTANTIVE / 1 PADDED on the
  overshoot tail) is a SINGLE-SAMPLE judged read → PROVISIONAL under the
  2026-07-20 replication rule. It was a harm-guard, never the adoption
  basis (that was shape ok-rates across 4 replicated cells), so W1 stands;
  re-sample the guard at the next authorized codex spend.
- Word caps in rules 1/6 are ANCHORS (models cluster at the stated number;
  4 overshoot fields in ~70 accepted outputs); the validator wall is
  ceil(cap×1.5). Raising a stated cap moves the whole distribution.
- The output anchor line is reasoning-neutral (owner ruling 2026-07-11).
- Ops example shows one op per TYPE, update first (mode 10; armJ5 count
  anchoring).

- The raise-difficulty case is MAINTENANCE-GUARDED (MAINT, adopted on
  owner ruling 2026-07-20): "accuracy above 0.85 on ACTIVE practice (not
  maintenance reviews of a passed phase) → raise difficulty". Adopted on
  shape evidence — qwen 18/30 (campaign-best reflect; baseline 10-16),
  gemma 25/30 in-band with dial-fails 0 — the same evidence class as
  every other adopted arm. Its judged target (plateau 0.125→0.625
  replicated under the two-qualifier bundle) is UNMEASURED-NOT-FAILED:
  plateau_remediation is bimodal below n=5 (see entry below); re-sample
  at a future ≥5-sample codex spend before citing judged numbers.
- Per-op field-rule GEOMETRY is a PROFILE (DOPS 2026-07-20,
  fulfiller.reflect_field_rules): parallel per-op lines gave gemma its
  best reflect ever (29/30, op-composition fails 0); qwen got WORSE twice
  (op-fails 10-12 vs 6-8) on the same edit. Default = legacy run-on form,
  byte-identical (test-pinned); "dops" = parallel lines, opt-in. Editing
  either fragment must keep both measurements valid.

- **plateau_remediation is UNUSABLE as single- or double-sample judged
  evidence** (2026-07-20, 8 samples across arms: 0.125/0.125 stable at
  baseline, then 1.00/0.625/0.625/0.125/0.5/1.0 under qualifier arms).
  Any claim citing it needs ≥5 samples. It is the reason the judged
  replication rule exists.

CLOSED NEGATIVES
- Reflect DECOMPOSITION (owner-approved pilot, 2026-07-20): splitting into
  ops+voice calls ELIMINATED journal-omission at all three models (the
  campaign's most persistent class) but did NOT clear the acceptance bar —
  per-op field composition moved into call 1 unchanged (qwen 15/30 vs a
  >=18 bar; gemma 28/30; lfm-instruct 2/30 from 0). Cost +30% (inside the
  +45% bar). Infra parked opt-in (campaign_reflect_ops/voice templates,
  ReflectOpsResult/ReflectVoiceResult). The residual is per-op field
  composition, NOT job-count dilution — target that, not the split.
- Section ORDER: moving rules 6-7 adjacent to OUTPUT left journal-omission
  EXACTLY at baseline (SORD, sord_*_reflect.jsonl). Omission is
  compositional load; the only open lever is the owner-gated reflect
  decomposition (QUESTIONS −3).
- Wording variants for journal/op obligations: null across 6 template
  generations (P4a/P4b/P8/P9b/W1/W2 ledger).

## campaign_plan.md

WINS TO PRESERVE
- Words-only path rule (P1): abstract letter-path skeletons ("a.b.c"
  beyond the single skeleton literal) caused letter-path bleed into real
  plans; zero letter-paths is checked at every plan adjudication.
- Phase criteria stated IN FULL incl. min_accuracy 0 for calibration
  (mode 7 crash of 2026-07-17; test_plan_template_states_full_calibration_
  criteria pins it).
- Refinement-question cap is an anchor (W1): gemma's historical rejections
  were ALL 16-22 words vs the 15 stated — the 1.5× wall converted the
  class (gemma plan 9/11→13/13, iterW1cap_*).
- "kind" field-rule states the enum; skeleton shows one realistic literal
  (mode 1).

CLOSED NEGATIVES
- Enum-form rephrase of "kind is one word": no measured effect at any
  caliber (W4 family); don't spend a battery on it alone.

## attempt_grade.md

WINS TO PRESERVE
- Evidence wording says copy-don't-describe and NEVER uses the word
  "quote" (modes 3/4: "quote" wording made models add literal quotation
  marks — breaking the verbatim check AND leaking escapes that corrupted
  whole payloads, 7/8 of qwen's no-JSON fails).
- NO evidence word-cap exists (ArmS: the cap fired before the verbatim
  check and taught models to shorten analysis instead of quoting; 14/14
  gemma3:1b rejections. test_evidence_words_not_a_template_cap_anymore
  pins it). Validator-side wins riding on this template: W3 strips
  decoration (wrapping quotes/ellipsis) before the verbatim check.
- Score band stated as explicit enum ("one of 1.0/0.7/0.3/0.0") — the
  safe enum form other templates copy.
- Verbatim check STAYS STRICT (owner-aligned 2026-07-19): 79% of
  rejections are genuinely ungrounded; 4% catch answer-KEY quoting
  (grading the wrong text). Soft enforcement rejected while mechanical
  rescues exist.

CLOSED NEGATIVES
- Evidence-core fuzzy rescue: 3 mangled converts beyond live W3 —
  NOT implemented (W5).
- JSON quote-repair for no-JSON fails: 7/333 (W6). The no-JSON mass is a
  capability signature (derailment), not syntax.

## exercise_generate.md

WINS TO PRESERVE
- The fewer-items escape hatch is stated, TYPED, CAPPED, and
  DEVIATION-FRAMED ('"note" stays null unless you deviated (then ≤ N
  words)') — the proven form that diagnostic now mirrors (mode 11).
- Example items: one per distinct skill TYPE, never repeated types
  (mode 10: two creates made even codex emit exactly two).
- Rubric accepts list-of-strings via validator coercion (ArmS) — template
  keeps showing the dash-bullet string form.

CLOSED NEGATIVES
- qwen's residual generate fails are output-corruption capability
  signatures (escape chaos + invented intervention shapes) — no
  template lever found (2026-07-20 sweep).

## exercise_diagnostic.md

WINS TO PRESERVE
- The fewer+note rule is stated in generate's EXACT deviation-framed form
  with note_words cap (DSTATE-2, dstate2_*: gemma 7/7 best-ever, qwen
  6/7). The two failed intermediate forms are the reasons: bare statement
  → qwen emitted "note": true (type unstated); permission framing
  ("or fewer + note") → gemma under-filled and wrote 40-word essays
  (3/3→2/7). Do not reword away from the null-default framing.
- note_words is declared in TEMPLATE_CAPS (the shared GenerateResult cap
  is trippable from diagnostic submissions).

## capture_route.md

WINS TO PRESERVE
- The OUTPUT skeleton is COMPILER-SELECTED (never hardcode a literal):
  the three-sided trap is fully measured — null literals teach field
  omission (qwen 1/8), corpus-absent literals teach INVENTING registry
  names (gemma 7→5, rfix_gemma), real literals invite copying (gemma 7→5
  again, rfix2_gemma). Profiles hold each caliber's measured best:
  default nulls (gemma 6/6-era), fulfiller.route_skeleton="live"
  (qwen 12/13; lfm2.5-instruct 13/13 PERFECT, rfix3_lfmi). Edit the
  route_skeleton_* fragments, keep both profiles' measurements.
- topic_path is CHARSET-VALIDATED like plan paths (ROUTE-CHARSET
  2026-07-22, adopted): spaces were accepted here while PlanTopic
  rejected them — same regex, same taught message now; rule 2 states
  the leaf format. Judged: route_new_leaf 0.60→0.80/0.80 stable with
  the snake_case criterion clean both samples (rchar_* jsonls,
  gate-1 minis above baseline both models).
- Rule 2's new_topic case states BOTH the leaf format AND that the
  reason names the coverage gap (ROUTE-REASON 2026-07-22, adopted):
  the judge expected justification the template never asked for
  (mode-7 at the judged tier). route_new_leaf: 0.60 → 0.80/0.80
  (charset arm) → 1.00/1.00 (reason arm) — both samples perfect,
  scenario left the hard set. Two single-variable arms, each fixing
  its own criterion; rreason_*/rchar_* jsonls.
- Rule blocks are fragments too (route_soft/_field × default/lean);
  default compiles byte-identical to legacy (pinned hashes in
  test_route_default_profile_keeps_legacy_rule_text).
- Rule 3 (caps) and the Check line stay IN the template file (statement
  gate pins cap placeholders to template text).

CLOSED NEGATIVES
- Lean rule-block at lfm-think: 0/13, class unchanged (RSIMP) — rule
  density wasn't the constraint. (Bonus: gemma runs lean 6/6.)
- Enum-form "action" phrasing alone: 0/13 at lfm-think (W4) — rumination
  migrates to the next informal descriptor. lfm-think route is a
  CERTIFIED CAPABILITY FLOOR (0/13 under three different surgeries).

## goal_route.md

Same regime as capture_route.md (shared fragments family, same trap, same
profiles, same negatives). Differences to preserve: no stay_inbox in the
action set (rule 5 guards it — kept even in the lean fragment because
single-shot has no retry to teach it); 3-line skeleton wrap.

## campaign_reflect_ops.md / campaign_reflect_voice.md (PILOT, opt-in)

Split-reflect pilot templates (owner-approved 2026-07-20), NOT on any
production path — no compiler function renders them by default; the probe
(scratch/prompt-lab/decomp_probe.py) drives them. Findings: the split
ELIMINATED journal-omission at all three measured models (gemma 28/30,
qwen 15/30, lfm-instruct 2/30 from 0) but missed its acceptance bar
because per-op field composition moved into the ops call. Preserve if
editing: the voice call must stay TINY (~1.2KB: digest + rules 1-3 +
skeleton) — its attention isolation is the mechanism that worked; the ops
call carries ALL evidence sections and inherits campaign_reflect's wins
(orthogonal examples, create-suppression, cap anchors). Do not wire to
production without a fresh owner decision + a new measurement.

## fragments/ (cross-cutting)

- reflect_ops_default.md / reflect_ops_no_insights.md: orthogonal-domain
  values (EX-BLEED); default has UPDATE example only (EXB2);
  no_insights keeps its create example — create is the only valid op
  there, and its residual bleed is measured and accepted (6/27 gemma).
- route_skeleton_* / route_soft_* / route_field_*: see route sections.
  default variants are byte-verbatim legacy extractions — regenerating
  them from the templates' git history is the recovery path.
- anchor_deliberate.md (6i): CALIBER-DIVERGENT — raised qwen
  trap-avoidance 44%→75%, made gemma slightly worse; opt-in profile
  only, default stays byte-identical neutral. Thinking-class models
  need no invitation (they deliberate anyway; their cost is latency).
