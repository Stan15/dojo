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
- `arms/apply_armS.py` — semantic-only validation (apply AFTER armJ): evidence
  cap rejection dropped (substring invariant stays; storage clipped), rubric
  list→string coercion, summary clip-not-reject. Verified anchors.
- ArmA (compact JSON) / ArmD (omit nulls) — NOT built; only if armJ/armS
  leave material waste (owner: no tiny gains).

**State: baselines** — gemma1b DONE (base_gemma1b.jsonl). lfm PARTIAL
(~54/64, base_lfm.PARTIAL.jsonl — rerun it). gemma3:4b, qwen3:4b NOT run.

**Exact next actions:**
1. Restart ollama parallel (see run_battery.sh header), finish baselines:
   `zsh scratch/token-diet/run_battery.sh base` (comment out the gemma1b line).
2. Apply armJ templates → `run_battery.sh armJ` (at minimum gemma1b + one 4B).
   Compare with analyze.py: ok-rate must rise sharply; raw bytes per
   SUCCESSFUL task must fall; skill/action distributions must not skew.
3. Apply armS on top → `run_battery.sh armJS`. Same comparisons.
4. qwen think experiment (H-B): rerun qwen battery with
   "ollama run --think=false qwen3:4b" IF flag works piped; compare ok-rate +
   total bytes. Deliverable is DOCS/benchmark guidance only — never prompt text.
5. Winner → repo: template edits + schema/limits/service edits (from
   apply_armS.py) + tests for coercion/clip + golden/footprint updates +
   TEMPLATE_CAPS coherence, full pytest gate. Baseline cards: quality floors
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
