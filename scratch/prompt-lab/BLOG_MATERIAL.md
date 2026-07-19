# BLOG MATERIAL — running dossier (standing owner directive 2026-07-19)

_CAPTURE FIRST, CURATE LATER (owner clarification): anything valuable or
interesting goes in — about ANY topic, not just the prompt lab. Whether it
becomes a post is decided later. Each entry: the hook, the hard numbers,
where the raw data lives. The owner writes the posts; this file is the
quarry. Append-only in spirit; newest first. Raw evidence:
scratch/token-diet/baselines/*.jsonl (all committed),
evals/reports/quality-*.json, docs/INSIGHTS.md, WORKBENCH ledger._

## Post angle 1 — "A prompt-improvement flywheel, grounded by a strict holdout"

The frame: an autonomous loop (observe → root-cause → pre-register →
cheap-test → adopt/revert → record) that CANNOT overfit its own benchmark
because the holdout is epistemically sealed, not just "not trained on."

- **The blindness protocol is the story.** Holdout scenarios are authored by
  cold-context subagents whose briefs BAR them from reading the visible
  corpus; they report back filenames and counts only. The tuning session
  never sees holdout content — and contamination is defined CONTEXTUALLY:
  "a model cannot firewall information inside its own context window; 'I
  read it but won't use it' does not exist" (owner ruling 2026-07-11). One
  leaked scenario was burnt and regenerated. The gate yields ONE bit
  (aggregate gap vs visible mean); even scenario NAMES are withheld.
- **Pre-registration with decision rules, before every test.** Example (W1):
  "shape ok-rates same-or-better both models; expect question-cap classes to
  convert; ±3 single-run variance → replicate before adjudicating." Losers
  get recorded as negative results with a do-not-blind-retest rule.
- **The reward-hacking rails in writing**: never edit a scenario/rubric so a
  score rises; judge changes must be mechanics-honesty fixes; fixes must
  state the PRINCIPLE, not the rubric's phrase. A "genuinely wrong rubric"
  claim needs evidence independent of the score it unlocks.
- **Numbers for the arc**: quality 0.732 → 0.895 (blind-holdout era, July
  wk1); visible corpus 61 → 104 scenarios; corpus floors 89, mean 0.874;
  tests 241 → 937, all green at every commit.

## Post angle 2 — "The day the sub-4B verdict flipped" (2026-07-19)

Hook: we'd documented "below 4B, models miss the output contracts too often"
as a measured capability floor. It was true of the models we HAD, false of
the class. The owner's push — "the class verdict must not rest on one
model" — forced a deep-research pass + 7-model bake-off. Result:

- lfm2.5-thinking:1.2b (730MB!): **51%** single-shot vs the old rep's 10%
  (qwen3.5:0.8b) — 5× at smaller footprint. Plan 11/13, diagnostic 7/7.
- Family non-uniformity kills interpolation: qwen3.5 = 59% (4b) / 23% (2b) /
  10% (0.8b). granite4:1b bf16 57% but its 1.5B hybrid-q8 sibling 30%.
- Per-kind profiles diverge more than totals: lfm-INSTRUCT has the best
  route cell in the whole table (10/13) and 0/27 reflect; its thinking
  sibling is the mirror image. → mixed-model deployment proposal.
- Method note: the old 0.8b number was re-measured under the same tree as
  the challengers (13/92 → 10/104 replicated) — never compare across arms.
- Lesson worth a heading: **"caliber-class verdicts expire."** Data:
  bakeoff_*.jsonl, commit cb4a170 + 0d5c4e0.

## Post angle 3 — "Rejections are the token tax" (the ArmS/W-series doctrine)

Density = judged quality × acceptance ÷ whole-trace tokens. A rejection is
quality zero at full cost, then pays again. The whole W-series is variations
on one move: stop rejecting semantically-correct output.

- **W1 (word caps = suggestions, wall at 1.5×):** 100% of gemma's historical
  refinement-question rejections were 16-22 words against a 15-word cap —
  a few words of overshoot, each costing a full plan regeneration. Fix:
  templates keep stating the tight cap (the ANCHOR — models cluster around
  it), validator rejects only past ceil(cap×1.5) (the GATE — stops true
  rambles). Result: gemma plan 9/11 → 13/13; post-adoption audit found only
  4 overshoot fields in ~70 accepted outputs — the anchor held; the wall
  admits a tail, not drift. Separating anchor from gate is the reusable
  idea: raising the cap would have moved the whole distribution.
- **W2 (questions-object coercion):** models at EVERY caliber stochastically
  emit `{"question": ...}` objects for contracted string lists — 119
  archived rejections, 5.5% of all recorded failures. Also the root cause
  of a mystery: qwen reflect scored 9/23 twice under W1 while the change
  was provably monotone-looser — the "regression" was a format lottery.
  Confirmation battery after coercion: 0 hits (was 2-5/run).
- **W3 (evidence decoration):** honest verbatim quotes rejected for wearing
  quotation marks or a trailing "..." — 25 archived cases. Stripping
  decoration is NOT loosening semantics: the remainder must still be a
  verbatim substring. Bonus: closed a latent hole where EMPTY evidence
  vacuously passed the substring check.
- **The monotone-adjudication trick** (methodology gem): a change that only
  loosens acceptance cannot regress identical outputs, so a measured drop
  under it is sampling churn BY CONSTRUCTION — go read the transcripts for
  the real cause instead of reverting a good change. That's how W2 was
  found inside W1's "failure."

## Post angle 4 — "Negative results are wins" (the graveyard, with receipts)

The discipline: every disproven theory is recorded with a do-not-retest
rule. The graveyard from this campaign:

- **R3 retry-feedback, three times over**: telling a weak model WHY its
  output was rejected does not beat blind resampling — qwen 4B (ceiling'd
  cell redesigned mid-probe, amendment pre-registered before arm B data),
  qwen 0.8b (33% vs 38% — feedback LOST), and [R3-LFM verdict pending].
- **W5 evidence-core rescue**: naive sizing said 28 near-miss converts; the
  honest re-sizing against LIVE production (W3 already deployed) found the
  marginal was 3 mangled fragments. The first sizing double-counted a
  fix that already existed. Killed by its own decision rule. Lesson:
  **size the MARGINAL, not the gross.**
- **W2b type-shape coercion**: 304 archive hits looked like a class; the
  transcripts were old-era degenerate output from superseded templates.
  Archives mix eras — date your evidence.
- **P11c, armACC-in, 6i-for-gemma**: same pattern, earlier eras (ledger).

## Post angle 5 — "What tiny models actually do" (failure-mode field guide)

The measured weak-model failure modes in prompts/README.md are a post by
themselves (each was OBSERVED, with counts, in controlled batteries):

- Enum-echo: `"op": "create|update|resolve"` copied verbatim as the value
  (33× gemma3:1b). // comments in skeletons get copied INTO the JSON.
- "Quote" wording → literal quotation marks that break verbatim checks.
- Example values anchor LENGTH: a "2-4 sentences" example note collapsed a
  30-word-capped field from 11/20 to 0/20. The example IS the instruction.
- Example lists anchor COUNT: two `create` entries in an example → models
  at every tier emit exactly two creates.
- NEW this era — **thinking-model literalism**: "'action' is one word —
  attach, new_topic, or propose_campaign" sends lfm2.5-thinking into
  "propose_campaign is two words?!" rumination spirals ending in omitted
  fields (0/11 route; 3/3 sampled transcripts show the spiral verbatim —
  great pull-quotes). Meta-descriptions of enums are traps; state enums
  as enums. (W4 arm, verdict pending.)
- NEW this era — **example bleed at scale**: ONE skeleton example insight
  ("submits without re-reading the prompt") appears in 59% of gemma and
  33% of qwen reflect outputs. One string, half the outputs. (EX-BLEED
  arm queued; content-orthogonal examples hypothesis.)

## Post angle 6 — "The verbatim-evidence check earns its keep" (trust math)

When the owner asked "should this be softly enforced?", the archive
answered: of 162 rejections, 79% were genuinely ungrounded (paraphrase/
fabrication), 4% were the model quoting the ANSWER KEY — i.e. grading the
wrong text, the exact catastrophe the check exists for — and only 17% were
honest quotes with cosmetic damage (recovered mechanically by W3, no
softening). Rejection frequency and untrustworthiness are the same signal:
the models that trip the check most are the ones whose grades most need it.
A grade that can say "your words: …" is the product's trust anchor.

## Post angle 7 — "Running an autonomous lab without burning the house down"

Operational war stories with teeth:

- **The ssh-agent fire**: a pre-spawn resource check caught 1-min load 135
  on 8 cores with swap 90% full — ~1,715 leaked ssh-agent processes from a
  dotfiles bug, unrelated to the campaign. The slate was deferred, the fire
  root-caused and fixed at source. Doctrine: "throttling and swap-thrash
  are DATA CORRUPTION, not just machine risk."
- **GPU-lane serialization, learned the hard way**: 3 concurrent plan-length
  generations blew the 240s driver timeout (7×240s timeouts, one voided
  battery). ONE battery at a time; a mid-battery "quick smoke test" of
  another model got self-reported as an incident and became a binding rule.
- **Session-death resilience**: cron heartbeat + wakeup pacer + a WORKBENCH
  whose every in-flight lane carries its restart command. The campaign
  survived an account switch losing only its schedulers.
- **The exhaustion checklist** (owner correction, same day): "candidates
  exhausted" was claimed twice and both times a prompt surfaced 3+ missed
  items (unpaid pre-reg debts, undrafted diffs). Fix: a 7-category sweep
  that must be named before any wait — and a standing rule that a missed
  candidate is a DIRECTIVE bug, patched the same session.
- **The single-writer + quiet-tree discipline**: parallel cognitive lanes,
  serial adoption; briefs as contamination firewalls ("reports back are
  filenames/counts/verdicts when content would contaminate").

## Post angle 8 — smaller gems (one-paragraph sidebars)

- The compiler branches, the model executes (craft rule 5): weak models
  can't branch; move every conditional to the compiler.
- Tokens are latency: decode ~7.6 tok/s locally → every 100 output bytes
  ≈ +3s. Density wins are UX wins for exactly the users who need them.
- The deliberation anchor is caliber-divergent: the same "think it through"
  line lifted qwen trap-avoidance 44%→75% and made gemma WORSE — why
  anchor behavior is an opt-in profile, never a default.
- Thinking-class models bring their own deliberation: lfm2.5-thinking
  passed both dependency-root traps (9KB of self-generated thinking) that
  neutral qwen-4b hit — no invitation needed; the cost moves to latency.
- Judge mechanics honesty: evidence caps once fired BEFORE the substring
  check and taught models the WRONG fix (shorten analysis instead of
  quoting). Error-message pedagogy is prompt engineering too.
- The example-count trap: an example list with two creates made codex —
  a frontier model — emit "two insights, not one." No caliber is immune
  to example anchoring.

## CAPTURE INBOX — everything else valuable (any topic; curate later)

**Product & architecture stories (pre-campaign, previously uncaptured):**

- **The markdown store as a public contract**: the entire learner state is
  human-readable markdown files; the format is a tested contract (fixture
  round-trip + blueprint update required in the same commit). Your
  spaced-repetition history survives the app. Anki interop rides on it.
- **Two audiences, one guarantee**: every command works for both a human at
  a TTY and an agent with `--json` — with a TESTED tripwire that agent mode
  can never hit interactive input. Designing a CLI for humans AND agents as
  co-equal users is its own post.
- **The task contract** (ADR 010): AI work is typed tasks (plan / generate /
  grade / reflect / route) with schema'd results, byte-budgeted compiled
  payloads, and appliers that verify before any state changes. "The AI
  proposes, the applier disposes." The consent-gated attack plan
  (authority.py): AI restructures of YOUR study plan never apply blind.
- **Single-shot by design**: the task contract is deliberately one-shot (no
  multi-turn, no tool calls) — that constraint is what makes weak-model
  measurement, token budgeting, and the whole eval methodology tractable.
- **FSRS + disposable exercises** (ADR 012): only verbatim recall repeats
  under FSRS; everything else is disposable and topic-scheduled. Encoding
  events (ADR 017): a first-encounter miss is FREE — it initializes the
  schedule instead of punishing it, because a miss on never-taught material
  is an encoding event, not a lapse. Pedagogy encoded in scheduling math.
- **Byte budgets as tested invariants**: compiled payload sizes are
  asserted in CI (±5% footprint gate); output budgets ratchet per driver.
  "Context economy as a test suite" — nobody does this.
- **Tokens-are-latency table**: prefill ~106 tok/s vs decode ~7.6 tok/s
  measured locally — the asymmetry that makes OUTPUT bytes the enemy and
  input bytes almost free. Every 100 output bytes ≈ +3s for a local user.
- **The owner-as-field-tester loop**: the owner installs from the repo
  checkout and reports bugs mid-session ("treat those as the highest-signal
  tests you have") — day-one bombardment, diagnostic dead-loop, French
  accents, attempt-filename overwrite: all field-caught.
- **Delete-over-retain**: no legacy code in tree, ever; git is the archive;
  the old SQLite implementation lives in archived_implementation/ as a
  mine, never an import. Cultural rule with teeth.
- **The ProperDocs sanity check**: "MkDocs is abandoned; properdocs is the
  maintained continuation and griffelib is legit, not a typosquat" — the
  2026 supply-chain-paranoia workflow of verifying a fork's legitimacy
  before adopting it is relatable content.

**Method & meta stories (this era):**

- **An autonomous overnight lab with a human rudder**: the owner's three
  mid-session corrections (never idle-wait → think deeply → checklist-
  verified exhaustion) each got encoded into the directive THE SAME DAY,
  with the failure that prompted them recorded. The directive is a living
  artifact whose git history shows the operator learning loop.
- **The heartbeat that defuses itself**: a cron prompt whose FIRST clause
  is "if the session is busy, say one line and return" — designing
  interruptions that can't derail the interrupted. (Two live firings
  defused exactly as designed today.)
- **Chained lanes**: arm B launched by a watcher on arm A's exit; zero
  dead GPU time between serial stages of a multi-hour probe.
- **The entry that vanished**: a WORKBENCH pre-registration was lost in an
  edit chain and only noticed because a later step tried to update it —
  argument for append-only ledgers + verify-on-commit. Small, honest,
  relatable failure.
- **Judged quality is the anti-Goodhart numerator**: shape ok-rate is
  cheap and local; judged quality is expensive and remote; the doctrine
  keeps BOTH so that terse-but-hollow can never score as a win.
- **Cold-context subagents as an epistemic tool**: spawning agents
  specifically for what they DON'T know (blind authoring, independent
  replication, fresh-eyes second opinions). "The brief is the firewall."

**Numbers bank (for any post):** 937 tests; 104 visible scenarios + sealed
holdout; 110+ committed battery jsonls; 12+ commits in one autonomous
session; quality 0.732→0.895 across the campaign; 5 adopted arms + 3 closed
negatives in a day; 0.8b→1.2b class rep flip at 5× quality per GB.

## Housekeeping for the writer

- Every number above has committed raw data. Battery jsonls:
  scratch/token-diet/baselines/ (110+ files). Ledger: WORKBENCH.md
  (+ git history). Durable findings: docs/INSIGHTS.md. Era summaries:
  docs/STATE.md changelog.
- The holdout numbers usable in posts: only aggregate gap/verdicts as
  reported by the OWNER-run gate — this dossier deliberately contains no
  holdout details, and the posts must keep it that way (the blindness IS
  the story; breaking it in a blog post would be the ironic failure).
- Standing practice from today: new material lands here in the same
  commit as the adjudication that produced it — and the bar is CAPTURE
  FIRST: anything interesting goes in regardless of topic; curation is
  the writer's job, later.

## APPENDED ~14:15 — "The win that evaporated" (pre-registration's finest hour)

The retry-feedback probe on the new sub-4B champion looked like a triumph
mid-run: at 20 scenarios, arm B (error feedback) led arm A (blind resample)
by +36 points — more than double the pre-registered +15 bar. Three prior
negatives about to be avenged. Final tally at 33 scenarios: +13. Bar
missed by two points; verdict NEGATIVE; no production proposal. What
happened: the easy grade scenarios ran first (feedback rescues verbatim-
evidence failures 5/7 — the model genuinely re-reads and quotes when
told), and the route tail ran last (feedback rescues field-omission 0/12,
because that confusion is upstream in the rule phrasing — a different
fix's territory). Interim leads are sampling-order artifacts. If the
decision rule hadn't been written down BEFORE the data, this ships.
Fourth R3 negative; the mechanism table (rescued 5/7 vs 0/12) is the
consolation prize — it says exactly which retry classes are feedback-
shaped, and keeps one narrow grade-only hypothesis alive for a fresh,
separately pre-registered test. Data: retryprobe_lfmthink_{A,B}.jsonl.

## APPENDED ~16:35 — "The rumination that migrated" (W4 negative)

We removed the phrase that sent a thinking model into "propose_campaign is
two words?!" spirals — and watched the spiral re-attach to the next
informal descriptor in sight ("is 'backyard-birding' one word?"; 0/13
before, 0/13 after). Root cause refined: for small thinking models the
trigger isn't any particular phrase, it's deliberation-budget exhaustion
against a rule-dense payload — the model spends its coherence deliberating
every rule and drops required fields from the final JSON. Phrase surgery
can't fix a budget problem. The live fix direction is structural: a
thinking-class fulfiller profile that states fewer rules and lets the
validator teach the rest. Also a clean demo of revert discipline: negative
by pre-registered bar → templates checked out, tests green, GPU for the
guard batteries never spent. Data: iterW4_lfmthink_route.jsonl.
