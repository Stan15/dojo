# QUESTIONS proposal draft — retry-prompt enrichment (owner-gated)
# CONTINGENT on R3-LFM final adjudication; numbers below marked FINAL when
# arm B completes. Drafted ~14:00 during the probe per draft-ahead doctrine.

**Ask:** when a raw-driver submission is rejected, re-send the ORIGINAL
prompt plus one line: "Your previous output was rejected: <validator
errors>. Emit the corrected complete JSON object." Today drain_tasks
re-sends task.prompt unchanged — retries are error-blind resamples; R1/R2
message quality reaches only agent drivers.

**Evidence (R3 series):**
- qwen3.5:4b (plan cell): arm A ceiling'd — feedback unadjudicable there;
  reflect cell flat. NEGATIVE.
- qwen3.5:0.8b: feedback LOST (33% vs 38%) — error text derails a model
  that can't parse it. NEGATIVE.
- lfm2.5-thinking:1.2b (new sub-4B class rep), grade+route stems:
  arm A [FINAL: __/32, mean __] vs arm B [FINAL: __/32, mean __] —
  interim +24 to +36 points, bar was +15. POSITIVE (pending final).
- MECHANISM (why this isn't noise): feedback rescues verbatim-evidence
  failures 5/7 (model re-reads and quotes correctly when told) and
  missing-required-fields 0/9 (those are upstream rule-phrasing failures —
  the W4 arm's territory). The win is class-specific and explainable.

**Design implication:** enrichment must be CALIBER-GATED — a fulfiller
profile / config flag (default off), on for models measured to benefit
(currently: lfm2.5-thinking:1.2b), never for sub-1B tiers where it
measured negative. Token cost: one extra line + the original prompt
re-send (unchanged size) per retry; density math rides the acceptance
gain (each rescued retry saves a full regeneration).

**Owner decision points:** (1) approve the drain_tasks change behind a
config flag; (2) naming + default; (3) whether the flag belongs in the
per-kind model routing table proposed separately (mixed-model deployment).
