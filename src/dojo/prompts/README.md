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
