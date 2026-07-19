# RETIRED ~14:15 — R3-LFM adjudicated NEGATIVE (A 39% vs B 52% = +13,
# bar +15; subs −0.12, bar −0.5). This proposal does NOT ship. Kept as
# the negative-result record; the only live remnant is a grade-stems-only
# hypothesis (A 11 vs B 15 ok) requiring a FRESH pre-registered
# replication before anything is proposed (forking-paths guard).
#
# Original contingent draft below, for the record:

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
