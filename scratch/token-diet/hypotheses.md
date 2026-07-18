# Token-diet hypotheses (pre-registered before aggregate analysis)

Metric that decides everything: **output bytes per SUCCESSFUL task**, per
caliber, across the full visible battery. A change that cuts bytes but drops
ok-rate (or judged quality on finalists) is a regression, not a win.

## H-A Whitespace: models pretty-print JSON
- Prediction: json_bytes − json_min_bytes = 10–25% on nested outputs
  (plan/generate/reflect), <10% on flat ones (grade/route).
- Candidate fix: output anchor gains "on one line" / "compact, no
  indentation". Zero information loss.
- Risk to test: weak models may lose bracket tracking without line structure
  → ok-rate drop on 1b models. Also bytes≠tokens (indent runs tokenize
  cheaply); treat savings as an upper bound, verify with a tokenizer proxy.

## H-B Deliberation preamble (thinking-class models)
- Prediction: qwen3:4b pre_bytes median ≥ 2× json_bytes; other calibers ~0.
- PROMPT text is off-limits (reasoning-neutrality ruling). Candidate fix is
  DRIVER-side documentation: recommend think-off flags for fulfiller configs
  IF AND ONLY IF ok-rate (and spot-judged quality) holds without thinking.
  Deliverable: docs/benchmark guidance, zero prompt change.

## H-C Cap-anchoring: word caps act as targets, not ceilings
- Prediction: free-text fields cluster in the top quartile of their cap even
  on trivially simple scenarios (e.g. single-fact plans, recall answers).
- Candidate fix: dual phrasing "aim ≤ K words; hard cap {{ cap }}" or
  lowered caps where pedagogy allows. DANGER: quality-relevant content
  (answers anchor grading; missions anchor planning). Any cap cut must
  survive judged spot-checks on multiple categories + calibers.

## H-D Null/default echo: skeletons teach models to emit every key
- Fact (verified): every non-semantic field already has a schema default —
  omission is legal today for grade/route/reflect/generate.
- Prediction: nulls/false/[] are 25–40% of route/grade json bytes, 10–20%
  of reflect on quiet days.
- Candidate fix: skeleton note "omit any field you would set to null/false/
  []" (numbers stay: required fields listed). Risk: weak models omit
  REQUIRED fields more often → rejection retries eat the savings. Measure
  ok-rate delta per caliber.

## H-E Rejections are a hidden multiplier
- Prediction: 1b-class single-shot rejection rate ≥ 40%; each rejection in
  production costs ~1 full output re-emission (max_submissions=3).
- Fix path A (template): whatever the top error taxonomy says is unstated
  or understated.
- Fix path B (system, owner-gated): display-only fields (topic summary,
  focus) could CLIP instead of reject — ledger as proposal with measured
  retry-cost evidence; do not implement unilaterally.

## H-F Reflect adjudication verbosity
- Prediction: models emit no-op "update" entries echoing unchanged insight
  text (rule 1 says adjudicate EVERY insight; it never says "emit only
  changes").
- Candidate fix: one rule-1 clause: "an unchanged verdict emits NOTHING".
- Risk: models might under-report resolutions; watch resolve-op rate.

## H-G SKILL.md input diet
- Content-preserving compression only; every directive survives. Static
  needle tests + budget gate; behavioral evals don't exist yet (QUESTIONS
  6c) so no semantic rewrites.

## Decision rule (anti-reward-hack)
A candidate ships only if, across ≥3 calibers and the full battery:
1. output bytes/successful-task drop ≥ 5% where the hypothesis targets, AND
2. ok-rate does not drop beyond noise (±1 scenario), AND
3. for content-affecting changes: judged spot-set (≥8 scenarios spanning
   categories, cheap-codex judge) shows no quality drop, AND
4. the win holds on at least two calibers, not one.

## H-J Skeleton syntax is weak-model-hostile (post-first-trace, pre-aggregate)
- Observed (gemma3:1b): `rubric` emitted as array (skeleton "- ..." + comment
  reads as a list); `skill` omitted; the enum string
  "recall|explain|..." pasted INTO rubric content. The `//` comments and
  a|b|c notation are copied as content by 1B-class models.
- Candidate fixes to A/B:
  (a) skeleton with REALISTIC literal values (one-line example) and
      constraints moved to RULES — risk: content bleed from example values;
  (b) explicit type note beside rubric ("one string, newline-separated
      bullets");
  (c) schema tolerance: coerce list-of-strings rubric → joined string
      (validation-floor loosening, meaning-preserving; cuts retries).
- Metric: shape-rejection rate per caliber; content-bleed check on (a) by
  domain-distinct scenarios.

## H-K Grade evidence field misread as "your reasoning" (gemma3:1b: 11/11)
- 100% of 1B grade rejections = evidence > 10 words; emitted text is grader
  ANALYSIS (often containing the correct verbatim quote inside quotes, and
  the correct band!). The word "evidence" invites justification prose.
- Candidate fixes:
  (a) template: rename intent in words the model can't misread — skeleton
      value "copy 3-10 words verbatim from ANSWER"; rule 3 phrasing
      "copy, don't describe";
  (b) system (gate-worthy, prototype + measure only): tolerant extraction —
      if evidence fails cap/substring but contains a quoted span that IS a
      verbatim answer substring, accept that span (hallucination check
      intact: only true substrings pass). Massive weak-model rescue.
- Note: shape floors, not capability, are ~100% of the 1B failure story so
  far. Fixing rejections IS the token diet at this caliber (every retry
  re-emits the whole output).

## OWNER CONSTRAINTS (2026-07-17, binding)
- No tiny gains — CLARIFIED (owner, 2026-07-18): a prioritization rule, not a
  ban. Main-work focus goes to MATERIAL levers (retry elimination,
  thinking-class waste, ≥~10% body cuts); do NOT spend tokens investigating
  or optimizing marginal candidates mid-campaign. BUT logically-sound,
  clearly-correct marginal wins are DEFERRED, not discarded: accumulate them
  in a cheap batch after the main work ships (e.g. ArmA compact-JSON /
  ArmD omit-nulls style items), still subject to the same-or-better floor.
- Performance floor is ABSOLUTE: same or better on every kind, every caliber,
  every category. Any regression anywhere kills the candidate.
- H-C (cap tightening) DROPPED: it is the only lever that trades quality for
  tokens.

## CORRECTION (owner challenge, 2026-07-17): whole-trace metric is primary
- Arms are judged on RAW total bytes per successful task (pre_json thinking
  + json + implied retries), never json alone. qwen3:4b is the designated
  rumination detector: numeric focal points induce deliberation loops.
- ArmJ grade skeleton had an INVENTED "3-10 words" lower bound — removed.
  No new numeric constraints anywhere; existing caps stay stated (drift
  gate) but are never made focal in skeleton values.
- Audit question for every arm line: "could a thinking model ruminate on
  this?" — formatting/counting focal points are the triggers.

## ArmS — semantic-only validation (owner latitude 2026-07-17: conventions
## are challengeable when something is genuinely better)
Principle: reject ONLY semantic wrongness; coerce formatting variance; clip
display-only overflow. Every rejection avoided saves a whole re-generation
AND fixes the retry-teaching signal (today the evidence word-cap fires
before the substring check, telling a model that wrote analysis to
"shorten" instead of to "quote").
Concrete candidates:
- grade.evidence: DROP the word-cap rejection; keep the verbatim-substring
  invariant hard; clip stored evidence mechanically. (Also remove from
  TEMPLATE_CAPS + template statement, coherently.)
- generate.rubric: accept list-of-strings, coerce to newline-joined string
  (semantically identical shapes).
- display-only fields (topic summary, phase focus): clip at cap, never
  reject.
Hard floors untouched: enum membership, id existence, verbatim-ness, item
counts, phase/topic structure.
Metric: rejection-rate drop × re-generation cost, ok-rate strictly up,
stored artifacts still bounded.
