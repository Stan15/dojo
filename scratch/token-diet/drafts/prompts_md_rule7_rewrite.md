# DRAFT: docs/design/prompts.md changes for the winner commit

## Rule 7 replacement (current text PRESCRIBES the measured-hostile style)

7. **Example skeleton, not JSON Schema — with realistic literal values.**
   The output contract is a literal JSON skeleton — cheaper than a
   `model_json_schema()` dump and more reliably followed. Skeletons obey the
   measured token-shape rules (src/dojo/prompts/README.md, lint-enforced):
   every skeleton value is a REALISTIC literal (never `"a|b|c"` option
   strings, never `// comments`, never `"..."` — ≤4B models copy skeleton
   text as content and omit fields that comments crowd); option lists and
   per-variant field requirements live in a prose "Field rules" block after
   the skeleton; when items repeat, show TWO complete examples (a single
   example teaches first-item-only field patterns); rule statements must
   match the schema exactly — a rule that names some required fields teaches
   models to omit the rest. Skeletons anchor with "your final output is
   exactly this JSON (anything before it is ignored)" — format-anchored but
   REASONING-NEUTRAL (owner ruling 2026-07-11): never invite deliberation,
   never suppress it; extraction consumes the last JSON object either way.

## §1c addition (new): Token-shape rules are tested

Every rule above that names a skeleton pattern is enforced mechanically:
shape-lints in tests/test_prompts.py reject enum-pipe strings, `//`
comments, and `"..."` placeholder values in any template's OUTPUT block
(patterns measured to cause rejection-retries — the dominant weak-model
token cost; evidence: token-diet campaign, dev/token-diet
scratch/token-diet/). The output-byte ratchet
(evals/baselines/output-budget.json + tests/test_output_budget.py) gates
regressions in output bytes per successful task the way
token-footprint.json gates prompt-side growth. Prompt-quality work and
token work are mutually non-regressing (STATE standing directive
2026-07-17): whichever side you touch, run the other side's gates.
