# STOP — read this before editing ANY template in this directory

These templates are consumed by models from ~0.8B local up to frontier —
weak-model behavior is measured, not guessed. Every failure mode below was
OBSERVED in controlled batteries (evidence: `scratch/token-diet/baselines/`,
branch dev/token-diet; aggregates via `scratch/token-diet/analyze.py`). A
rejection costs a full re-generation — retries are the DOMINANT weak-model
token cost, so output-shape bugs are token bugs AND quality bugs at once.

Mandatory companions to any edit here:
- `docs/design/prompts.md` — craft rules §1, caps contract §1a, neutrality §1b.
  MUST be open while editing (repo rule; goldens + footprint baselines diff).
- `docs/STATE.md` "Standing owner directives" — prompt work and token work are
  MUTUALLY NON-REGRESSING, both directions tested. You run both sides' gates.
- Numeric caps interpolate from `limits.TEMPLATE_CAPS`; every validator a
  payload can trip MUST be stated in its template, in the same commit
  (statement gate in tests/test_prompts.py).

## Measured failure modes (do not reintroduce)

1. **Enum-echo.** `"op": "create|update|resolve"` skeleton values get copied
   verbatim as the VALUE by ≤4B models (33× gemma3:1b; kills capture.route at
   0% ok even on gemma3:4b). Skeletons show ONE realistic literal; the option
   list lives in a prose "Field rules" line.
2. **`//` comments poison output.** Models omit the fields the comments crowd
   (lfm: 7/7 plan failures = omitted commented fields) or copy the comment
   INTO their JSON, making it unparseable (qwen3.5:0.8b, observed verbatim:
   `"strategy": null,  // Strategy is currently static…`). No `//` comments
   in skeletons, ever.
3. **"Quote" wording → literal quotation marks.** Asked for a "verbatim
   quote", qwen3.5:4b wrapped evidence in `\"…\"` — which (a) fails the
   verbatim-substring check (the added quote chars aren't in the answer) and
   (b) leaks escapes that corrupt the whole JSON (7/8 of its no-JSON
   failures). Say "copy the words exactly — no added quotation marks";
   never rely on the word "quote" alone.
4. **"Evidence" invites analysis.** 14/14 gemma3:1b grade rejections were
   grader REASONING written into `evidence` (often containing the right
   quote). Field-intent wording must say copy-don't-describe.
5. **Multiline-string bait.** Dash-bullet layouts inside a string value
   invite raw newlines inside JSON strings (parse failure) or list-typed
   output (10× gemma3:1b rubric-as-array). Show `\n` escapes inside one
   string literal.
6. **Numeric focal points feed rumination.** Thinking-class models loop on
   numbers made salient in skeleton VALUES (qwen think-on: 121–164s, up to
   17.7KB for a one-field answer). Existing caps stay stated (statement
   gate) but never as the skeleton value's focus; NEVER invent new numeric
   constraints (an invented "3-10 words" bound was caught in review).
7. **Understatement teaches omission.** A rule that names only part of a
   required object (plan criteria naming min_attempts but not min_accuracy)
   makes models omit the rest. Statements must match the schema exactly.
8. **Anchors are reasoning-neutral** (owner ruling 2026-07-11): "your final
   output is exactly this JSON (anything before it is ignored)" — never
   invite deliberation, never suppress it.
9. **Example values anchor LENGTH and FORMAT, not just presence —
   demonstrate, never describe.** A journal value reading "2-4 sentences:
   what this cycle showed" made 4B models write 2-4 sentences into a
   30-WORD-capped field: reflect collapsed 11/20 → 0/20 (armJ2 battery).
   The example IS the instruction: skeleton values must be short, realistic,
   cap-compliant text a model can safely imitate (and where a format is
   validated — dotted keys — one example op must demonstrate it).
   AND: example CONTENT must be domain-ORTHOGONAL to plausible inputs
   (EX-BLEED 2026-07-19: one plausible example insight appeared verbatim
   in 59%/33% of gemma/qwen reflect outputs — silent store pollution;
   calligraphy-domain values halved/cut-78% the bleed with ok-rates UP,
   because copy-pressure is structural and orthogonal copies are at least
   VISIBLE). Current orthogonal domain: calligraphy — check the corpus
   before picking a new one. Where real insights exist the compiler
   suppresses the create example entirely (EXB2, test-enforced).

10. **Example lists anchor COUNT and TYPE.** An ops example showing two
   `create` entries made models at every tier emit exactly two creates
   (codex plateau_remediation "two insights, not one"; qwen3.5:4b README
   demo, 2/2 budgets); the older mixed update+create pair never did.
   Show one example per distinct valid TYPE, never a repeated type. A
   skeleton must also satisfy the template's own Check line as a whole:
   a phases literal referencing a topic absent from the topics literal
   was reproduced verbatim as a stable failure (gemma, two samples).
   For skeletons whose values interact with LIVE DATA (route: registry
   entries) the trap is THREE-sided — null literals teach omission
   (qwen 1/8), absent literals teach inventing names (gemma −2, RFIX),
   real literals invite copying (gemma −2, RFIX2) — and which side bites
   is caliber-specific: the route skeleton is therefore COMPILER-SELECTED
   per fulfiller.route_skeleton profile (default nulls = gemma's best;
   "live" registry interpolation = qwen 12/13, lfm-instruct 13/13). Never
   hardcode a route skeleton literal; edit the fragments and keep both
   profiles' measurements (rfix*_ jsonls).

## Measured dead ends (don't re-till without NEW evidence — full ledger
## in scratch/prompt-lab/WORKBENCH.md negatives + battery jsonls)

- **Stated word caps are ANCHORS, not gates** (W1 2026-07-19): validators
  reject only past ceil(cap × 1.5); models cluster at the STATED number
  (only 4 overshoot fields in ~70 accepted outputs). Raising a stated cap
  moves the whole length distribution — tighten/loosen the anchor and the
  wall as separate decisions.
- **Phrase-level fixes don't move rumination cells** (W4): replacing the
  "is one word" descriptor with enum form left lfm-think route at 0/13 —
  the spiral re-attaches to the next informal descriptor. Thinking-class
  route failure is deliberation-budget exhaustion; lfm-think route is a
  certified capability floor (0/13 across three different surgeries).
- **Section ORDER is measured null for obligation-omission** (SORD):
  moving the journal/language rules adjacent to the OUTPUT skeleton left
  journal-omission exactly at baseline. That class is compositional load;
  the open lever is the owner-gated reflect decomposition.
- **Error-feedback retries lose to blind resampling** at every measured
  caliber (R3 ×4 probes); only a narrow grade-only cell keeps an untested
  pulse.

## Before you commit

- `python -m pytest -q` (statement/caps/golden/footprint gates bind; template
  shape-lints enforce items 1/2/6 mechanically once landed — see
  scratch/token-diet/WORKBENCH.md step 5).
- Footprint baseline (`evals/baselines/token-footprint.json`, ±5%) and
  goldens update in the SAME commit as a deliberate change.
- Content-affecting wording changes need the eval ratchets (and judged
  spot-checks where grading/pedagogy is touched). Same-or-better everywhere
  is the floor — a win on one axis that loses the other is a regression.

This file is excluded from the runtime template snapshot (see
`__init__.py::all_templates`); it costs zero payload bytes.

11. **Escape hatches are stated, typed, capped, and deviation-framed —
   all four.** A conditional obligation (e.g. "fewer items requires a
   note") left unstated is tripped blind (mode-7 kin); stated bare, its
   value gets type-guessed (`"note": true`, qwen) and its condition read
   as PERMISSION (gemma under-filled and wrote 40-word note essays,
   3/3 → 2/7). The proven form frames the default as null, the hatch as
   deviation, with an explicit cap: `"note" stays null unless you
   returned fewer than {{ n_items }} items (then ≤ {{ note_words }}
   words saying why)` (DSTATE-2, 2026-07-19: gemma 7/7, qwen 6/7).
