# Token-diet workbench (dev/token-diet) — session continuation state

**Directive (owner, 2026-07-17):** on this dev branch, massively reduce token
usage — output tokens above all — via prompts incl. SKILL.md. Binding
constraints, verbatim in spirit:
- Build for VERY weak agents (Raspberry Pi 5 16GB class = ~4B local models);
  ollama bench is the proving ground; codex spend is limited — use
  `codex exec -c model_reasoning_effort=low --skip-git-repo-check -s read-only`
  (no separate mini model exists on the owner's account) and sparingly.
- NEVER reward hack. Theories from traces across multiple calibers → tested
  across the WIDE visible-scenario variety. Holdout is NEVER touched/read.
- Judge on the WHOLE trace (thinking + JSON + retries), not JSON alone.
- No tiny gains; performance must stay SAME OR BETTER everywhere.
- Conventions are challengeable when something is genuinely better
  (owner: e.g. evidence_words rejection semantics).

**Method:** `measure.py` runs every visible quality scenario through the real
compile→model→submit path, one-shot, recording raw/json/json-min/pre bytes +
ok/errors per driven step. `analyze.py` aggregates per kind. `hypotheses.md`
holds pre-registered hypotheses + the anti-reward-hack decision rule — READ IT
FIRST. Ollama models: gemma3:1b, LiquidAI/lfm2.5-1.2b-instruct, gemma3:4b,
qwen3:4b (thinking arrives on stdout → pre_bytes).

**Caliber ruling (owner, 2026-07-17b): class verdicts come from the BEST
model of each resource class** — users run the strongest model their hardware
allows. Best-in-class as of 2026-07: qwen3.5:0.8b (~1GB tier) and qwen3.5:4b
(~3.4GB tier), official ollama tags. gemma3:1b/lfm/gemma3:4b/qwen3:4b stay as
robustness points only. ollama upgraded 0.13.4→0.32.1 (older client can't
pull qwen3.5); both models pulled.

**Thinking-mode ruling (probed 2026-07-17b, decisive):** qwen3.5 thinks on
stdout by default and is single-shot-UNUSABLE that way: trivial one-field
JSON probe = 121s/17.7KB (0.8b), 164s/1.2KB (4b); with `--think=false`: 1-2s,
22 bytes, correct. qwen3:4b base battery DNF'd the same way (every completed
row a 240s driver timeout — kept as base_qwen4b.DNF-think-timeouts.jsonl).
So ALL qwen batteries run `--think=false` (driver-side flag; prompt text
untouched per reasoning-neutrality; the flag pipes fine in 0.32.1). H-B
deliverable: fulfiller docs must say think-off for local thinking models.
**Driver ruling (2026-07-18, supersedes the note above): `ollama run` piped
is UNUSABLE on 0.32.x** — the CLI writes its word-rewrap rendering into
non-TTY stdout: ANSI erase sequences + re-printed word fragments INSIDE JSON
string values, even doubled closing quotes (breaks balance). Short outputs
don't wrap, so smoke probes lied; the first qwen3.5:0.8b battery came back
0/64 with 48× "no JSON found" purely from driver junk. TERM=dumb does not
help. All batteries now drive via `api_driver.py` (HTTP /api/generate,
stream=false, optional --no-think; prints thinking then response = whole-
trace stdout parity). Old 0.13.4-CLI baselines verified clean (0/64 rows
with ESC) so they stay comparable. PRODUCT IMPLICATION for H-B docs
deliverable: any fulfiller config using piped `ollama run` on ≥0.32 submits
corrupted output — benchmark/driver guidance must say use the API.

**Findings so far (evidence in baselines/base_gemma1b.jsonl):**
- gemma3:1b single-shot pass: 2/63. The failure is SKELETON SYNTAX, not
  capability: models copy `"a|b|c"` enum strings as values (reflect op 33×,
  route action 6×, generate/diagnostic skill), emit rubric as a list, omit
  comment-crowded fields, and write grader ANALYSIS into grade `evidence`
  (14/14 grade rejections = evidence word-cap; the cap fires before the
  substring check so the retry error teaches the wrong fix).
- Rejections are the dominant weak-model token cost (every retry re-emits
  everything). Fixing them raises quality AND cuts tokens — the owner's
  "same or better" constraint is satisfied by construction.
- ws% (pretty-print waste) 10-22% on nested kinds; qwen thinking is the other
  big sink (drivers-side lever, prompt text is off-limits by the
  reasoning-neutrality ruling).

**Arms staged:**
- `arms/armJ/` — 7 shape-hardened template variants (copy over
  src/dojo/prompts/): realistic literal skeleton values, no `//` comments, no
  enum-in-string; constraints in a "Field rules" block. Watch for content
  bleed: skill/action distribution vs baseline (example values could bias).
  AUDIT NOTE (2026-07-17b): exercise_generate/exercise_diagnostic moved
  numeric caps (≤ {{ prompt_words }} etc.) from // comments INTO skeleton
  string values — a potential rumination focal point; if thinking-model
  pre_bytes balloons on those kinds under armJ, move the caps to the Field
  rules block. armS anchors verified against current source (5 hit src, 1
  correctly targets the armJ grade template post-copy).
- `arms/apply_armS.py` — semantic-only validation (apply AFTER armJ): evidence
  cap rejection dropped (substring invariant stays; storage clipped), rubric
  list→string coercion, summary clip-not-reject. Verified anchors.
- ArmA (compact JSON) / ArmD (omit nulls) — NOT built during main work; they
  are the accumulate-after batch (owner clarification 2026-07-18: marginal-
  but-sound wins are deferred to a cheap post-main pass, not discarded —
  and not investigated mid-campaign).

**State: baselines DONE (5)** — gemma1b 2/63 · lfm 7/64 · gemma4b 39/63
(62%) · qwen35_08b 4/64 (6%) · qwen35_4b 27/62 (44%). DNF/deferred:
qwen3:4b — think-on all-timeouts (kept as evidence); think-off DEFERRED to
post-main (its API think=false does not bind even via /api/chat — old qwen3
needs a model-specific soft-switch; marginal robustness point, not worth
mid-campaign debugging). Cross-caliber taxonomy: enum-echo + field-omission
at every caliber (capture.route 0% at gemma4b); qwen35_4b UNIQUE mode:
evidence quote-wrapping — added quote chars defeat the verbatim-substring
check AND leak escapes that break the whole JSON (7/8 of its no-JSON rows);
its profile is inverted (plan 86%/generate 80% BEST of all, grade 7%).
armJ grade template updated in response: "copied character-for-character,
no added quotation marks" (apply_armS.py anchor 6 kept coherent). New armS
candidates ledgered: refinement_questions cap (3/5 gemma4b plan failures,
user-facing → judged check required); H-K(b) quote-stripping tolerant
extraction now justified by the CLASS-VERDICT model, not just 1B.

**RUNNING (2026-07-18): armJ battery** — templates overlaid UNCOMMITTED on
src/dojo/prompts; battery order: qwen35_08b, qwen35_4b, gemma1b, lfm,
gemma4b (all API driver; qwens --no-think). Tree stays QUIET until
ALL_BATTERIES_DONE.

**Arm-snapshot convention (owner, 2026-07-18):** when an arm's battery
completes, commit the EXACT measured tree + its result jsonls as an "arm
snapshot" wip commit before applying the next arm on top. Stacked arms stay
attributable (armJ vs base; armJS vs armJ = armS marginal); snapshots make
every battery reproducible via git checkout. Losing arms are reverted by
the winner commit — git is the archive.

**Exact next actions:**
1. armJ battery done → analyze.py armJ_* vs base_*: ok-rate must rise
   sharply; raw bytes/successful task must fall; skill/action distributions
   must not skew (content-bleed check); qwen35_4b pre_bytes watch
   (rumination on caps embedded in generate/diagnostic skeleton values).
2. armS on top (arms/apply_armS.py) → armJS battery, same comparisons.
   Compare with analyze.py: ok-rate must rise sharply; raw bytes per
   SUCCESSFUL task must fall; skill/action distributions must not skew.
3. Apply armS on top → `run_battery.sh armJS`. Same comparisons.
4. qwen think experiment (H-B): rerun qwen battery with
   "ollama run --think=false qwen3:4b" IF flag works piped; compare ok-rate +
   total bytes. Deliverable is DOCS/benchmark guidance only — never prompt text.
5. Winner → repo: template edits + schema/limits/service edits (from
   apply_armS.py) + tests for coercion/clip + golden/footprint updates +
   TEMPLATE_CAPS coherence, full pytest gate. **PLUS the bidirectional
   regression gates (owner directive 2026-07-17c, standing in STATE):**
   (a) static shape-lint tests in test_prompts.py, default gate — no
   `a|b|c` enum strings as skeleton values, no `//` comments in skeletons,
   no numeric constraints inside skeleton string values (constraints live
   in rules/Field-rules lines); templates and lint made coherent in the
   same commit (campaign_plan's summary value + generate/diagnostic prompt
   values currently embed caps — resolve per the armJ qwen rumination
   data); (b) ratcheted output-bytes-per-successful-task baseline per
   driver (evals/baselines/), asserted in the opt-in real-model marker the
   way quality floors are; (c) docs/design/prompts.md §1 rule 7 rewritten
   to the armJ-proven skeleton style + a token-shape rules subsection, so
   future prompt editors inherit the awareness (that doc is mandatory-open
   for template edits). Baseline cards: quality floors
   for (codex,codex) may shift — owner-authorized validation run at the end:
   ONE `-m eval -q` with the codex low-effort driver, update ratchets same
   commit if moved.
6. Judged spot-set (cheap codex judge, ~8-10 scenarios spanning categories)
   comparing old vs new templates on QUALITY — the same-or-better proof.
7. SKILL.md content-preserving trim last; static gates bind (60 lines,
   needles, footprint ±5% — deliberate change updates baseline same commit).
8. Report: byte deltas per kind × caliber (whole trace), pass-rate deltas,
   spend ledger; STATE update; commits on dev/token-diet only — owner gates
   the merge.

**Gotchas:** run measure.py from repo root (imports dojo from src via the
venv); the tree must be QUIET during a battery (template edits contaminate
in-flight arms); `timeout` doesn't exist in this zsh; ollama spinner junk goes
to stderr (harmless); extraction reads the LAST balanced JSON object.
