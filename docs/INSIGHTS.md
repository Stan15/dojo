# INSIGHTS — append-only, dated

Non-obvious learnings. Newest at the bottom. Never delete; strike through only if disproven (with a dated note).

## 2026-07-07

- **The priority user is an AI harness, which inverts the connector architecture.**
  The prototype has dojo shell out to an LLM subprocess. But when a harness (Claude
  Code etc.) drives dojo, an intelligent model is *already in the loop* — spawning a
  second one duplicates cost, requires API-key config (breaking "install the skill and
  it just works"), and triggers permission prompts. Inversion: dojo emits schema-bound
  task envelopes; the harness fulfills them inline. Subprocess connectors demote to an
  optional headless adapter. (ADR 010.)

- **Weak models follow a concrete example skeleton better than a formal JSON Schema.**
  `model_json_schema()` dumps are several KB and weak models still violate them. A
  literal example JSON with inline field constraints is both cheaper (context tokens)
  and more reliably followed. Formal validation stays in Pydantic at submit time —
  the schema is for the machine, the skeleton is for the model.

- **Mandatory free-form `thinking` fields are a generation-token tax.** The prototype
  requires a `thinking` string in every LLM response to keep reasoning out of data
  columns. It works, but invites unbounded rambling from weak models. Bounded planning
  fields ("`plan`: ≤ 3 sentences") keep the benefit at a fraction of the cost.

- **Scheduling state must attach to stable nodes, not ephemeral items, or it bloats.**
  For generative skills, exercises are disposable (novelty principle, ADR 007) — so
  per-exercise SR state is state for things that will never repeat. Attach memory
  state to the *topic* for skills, to the *exercise* only for static-recall facts.

- **Campaign-level scheduling is an allocation problem, not a memory problem.**
  SM-2/FSRS models a forgetting curve; campaigns don't forget — learners under-attend
  them. What's needed across campaigns is fair, urgency-weighted rotation with atrophy
  pressure and deadline awareness: a deterministic priority score, fully explainable.

- **The path-leak was already a latent bug, not just a smell (2026-07-07, M1 dig).**
  `Attempt.session` stores `"active_session.json"` — a reference that silently goes
  stale the moment the session archives to `archive/sessions/…` — and
  `Attempt.exercise` is built as `exercises/{id}.md` (api.py submit path) while
  `save_exercise` actually writes `{date}_{counter}_{slug}.md`, so attempt refs can
  point at files that never existed. Consumers recover IDs via `Path(ref).stem`,
  compounding the confusion. Validates ADR 011's ID-based refs as a bug fix.

- **Repo drift found during survey (2026-07-07):** `pydantic` is imported throughout
  but absent from `pyproject.toml` dependencies; two ADRs share number 003; README
  says v1.0.0 while pyproject says 0.1.0; `docs/api-specification.md` still documents
  the SQLite era. Tracked in OPEN-PROBLEMS.

## 2026-07-07 — First real Tier-3 run: the eval system audits its own authors
The first (codex,codex) quality run (mean 0.52) split cleanly into three kinds
of findings, and two of them were OURS, not the model's:
- **Scenario bugs**: pure_recall's judge couldn't verify grounding because the
  source facts weren't in scenario_context (the judge sees only context +
  output); too_easy seeded 5/6=0.83 accuracy while the reflect prompt's own
  threshold says raise only >0.85 — codex obeyed the prompt and the rubric
  punished it. Lesson: **rubrics must be checked for coherence against the
  prompts they judge**, and the judge must be given every fact a verdict needs.
- **Prompt weaknesses**: an escape hatch buried in rule 9 loses to an imperative
  TASK line ("draft exactly 3") — the alternative must appear IN the imperative;
  "compress" without a number doesn't compress (codex: 15 topics under a
  2-week deadline).
- **Real model signal** (kept as baseline): codex is excellent at grading
  integrity and preference adherence (1.00), conservative to a fault on state
  changes (won't resolve mastered insights, hesitates to raise difficulty).
Also: judges wrap verbatim quotes in ellipses — evidence matching needs
edge-tolerant comparison or ~15% of honest passes get discarded.

## 2026-07-09 — Docs system: tool choice, ecosystem shift, and the pass-as-audit
- **pdoc was the easy reach, not the best fit.** Dojo's behavior lives in
  docstrings AND ~10 authoritative prose docs; a docstrings-only site
  structurally under-documents it. MkDocs+Material+mkdocstrings renders both
  into one searchable site with zero custom UI. General rule: pdoc when
  docstrings ARE the docs; MkDocs+mkdocstrings when docs = docstrings + prose.
- **MkDocs is abandoned upstream (2026); ProperDocs is the maintained 1.x
  continuation** the plugin ecosystem (gen-files/literate-nav/section-index)
  migrated to; griffe split into griffe(CLI)+griffelib(lib). First contact
  looked EXACTLY like a supply-chain attack: an unknown package advertising
  itself in build output, already installed. The discriminator between
  "typosquat" and "post-cutoff ecosystem event" is convergent evidence the
  package can't control: other trusted packages' live PyPI metadata, upstream
  issue trackers, independent news. Author-email fields prove nothing.
- **A docstring pass is a disguised audit.** Forcing an honest one-sentence
  description of each function surfaced a dead no-op loop (get_source_topics),
  two functions whose source_id argument silently does nothing (candidates
  carry no source provenance), and the apply_reflect consent gap. When you
  can't write an honest docstring, the code is the problem.
- **The coverage gate is what makes generated docs a system** rather than a
  snapshot: tests/test_docs_coverage.py fails on any undocumented public
  symbol AND on placeholder (<4 word) docstrings, so the reference site can't
  silently rot.

## 2026-07-09 (route-first / capacity / ownership session)

- **Every server-side validator a model can trip must be STATED in the
  template it gates — invisible floors are the corpus's dominant failure
  class.** All four eval failures triaged today were the same bug wearing
  different clothes: `limits.py` enforced a cap (topic depth 4, intervention
  question ≤ 25 words, route reason ≤ 12 words) or Pydantic demanded a shape
  (plan_revision phases) that the prompt never showed. Codex did the RIGHT
  pedagogy and failed mechanically — the fixes moved scores 0.0→0.83,
  fail→1.0, fail→0.67 with one-line prompt edits. Discipline going forward:
  when adding a limit or schema field, grep the template for it in the same
  commit (prompts.md §7b now models this).
- **Reuse must be enforced mechanically before it is prompted.** Topic
  hygiene had prompt-level "prefer attaching" but nothing stopped a router
  from minting `new_topic` for a path that already exists, a prose leaf, or
  a 6-level nest — and no eval measured reuse-over-create for either router.
  Now: applier rejects (exists→"use attach", `[a-z0-9_]+` leaf, depth cap),
  and the `routing` corpus category benchmarks the semantic half the rails
  can't check. Rails catch what's checkable; benchmarks watch what isn't.
- **Push surfaces get principles, pull surfaces get numbers** (owner ruling,
  capacity channel): the daily-completion message carries no counters — a
  streak number above "come back tomorrow" is chain pressure however gently
  worded — while `dojo stats` (consulted by choice) keeps the derived facts.
  The same shape generalizes: announce-once notices state facts with doors
  (maintain/archive/extend), never scores.

## 2026-07-09 (field-bug session)

- **A path filter must test paths relative to the root it guards, never the
  absolute string.** `sync_index`'s hidden-dir skip (`"/." in root`) matched
  the store's OWN prefix (`~/.local/share` → `.local`), making the entire
  default-location store invisible: every `get()` → None, everything
  downstream of it lying. Tests missed it because pytest tmp dirs contain no
  dot-component — conformance now pins a store rooted under `.local/…`.
  The general form: os.walk filters belong on `dirs[:]` (names inside the
  tree), not on `root` (which embeds where the tree lives).
- **A gate that can destroy working state must separate structural findings
  from advisory ones.** install.sh's doctor gate read a mid-command dirty
  store (a NORMAL awaiting-audit state) as non-compliance and rolled back
  the owner's install — while the owner was mid-`dojo learn`. Doctor now
  exits non-zero only on structural categories; recoverable states render
  as ⚠ advisories. Corollary the same evening: long-lived processes must
  not depend on their install staying on disk — templates now snapshot
  in-process at first render, so an upgrade/uninstall under a running
  conversation can't kill it.
- **"Not found" and "already done" are different facts; a loop that
  `continue`s over both reports success it can't prove.** drain_tasks
  skipped unresolvable task refs silently and returned ok — the crash
  surfaced two frames later as `NoneType.context`. Every honest-degradation
  path needs the distinction pinned.
- **The ratchet writer runs at teardown and believes the card, not the
  asserts.** The first live holdout gate persisted the very 0.0 floor its
  own bootstrap assert refused (session-scoped fixture teardown sees all
  collected scores). Ratchet writers must re-apply acceptance rules at
  write time (`merge_holdout_baseline`: zeros never floor, unknown scenarios
  merge in, existing floors immutable).

## 2026-07-11 — encoding-era session learnings

- **Contamination is contextual, not intentional.** A model cannot firewall
  info in its context window; "read but won't use" doesn't exist. Proven
  live: an IDE-selection relay leaked holdout rows into the working session
  minutes after the rule was written. Remedy: burn + regenerate the exposed
  scenario (the transcript then describes a test that no longer exists).
- **Judge-evidence verbatim checks must decode JSON escapes** — LaTeX/regex
  outputs (`\\[` raw vs `\[` decoded) had every honest judge pass discarded
  as "unproven". Fixed in evidence_haystacks; the discard mechanism itself
  is sound anti-reward-hacking machinery.
- **Single-sample floor bootstraps are noise-prone**: two scenarios floored
  at a lucky 1.0 failed on a DIFFERENT criterion each re-run. Multi-sample
  spread + a different-criterion-each-time signature = variance, not a
  failure mode. Owner-approved floor adjustment with documented notes.
- **Structure models must emit is structure models can corrupt**: plan phase
  numbers were retyped by models yet every consumer reads list position —
  now position-assigned at validation. Generalized owner principle.
- **Reflect variance is an architecture smell**: the mega-task juggles five
  jobs; per-sample criterion-dropping is the measurable symptom (STATE 7d).
- **Reasoning-neutral output anchors**: "return only this JSON" suppressed
  deliberation weak models may need; "your final output is exactly this
  JSON (anything before it is ignored)" tells the extraction truth without
  inviting token burn. Empirical check owed via the Ollama pairs.

## 2026-07-17 — learn-ride-along session learnings

- **A rule that partially states a required object teaches omission.** The
  plan template's rule 3 named only `min_attempts` for phase 1 while the
  schema required `min_accuracy` → models dutifully omitted it (field
  crash). The invisible-validation-floor class has a subtype: not just
  caps never stated, but *statements that say less than the schema
  requires*. The statement gate now also asserts the full criteria shape.
- **A mode stamp without its clearing edge is a bug with a delay.** The
  direct-create door stamped `strategy_profile.mode="diagnostic"`; nothing
  anywhere cleared it (reflect writes only difficulty/scaffolding), so
  such campaigns would replenish diagnostics forever. Found only because
  the materialize fix was about to import the same stamp. Rule: every
  state stamp lands in the same commit as the transition that clears it.
- **Interactive flows must spend the budgets the contract already grants.**
  `max_submissions=3` existed for I5, but drain_tasks gave up after one
  rejection — an agent driving via SKILL would have retried; the human
  flow silently threw the budget away. When a contract carries a retry
  budget, every consumer either spends it or says why not.

## 2026-07-17 — token-diet session learnings

- **A benchmark caliber is a resource class, and its representative must be
  the best of that class.** Nobody running locally picks a weaker model at
  the same footprint, so anchoring the "1B story" on gemma3:1b when
  qwen3.5:0.8b exists at the same ~1GB misstates the floor the product
  actually faces — and can misdirect prompt-shape work toward failure modes
  the real floor model doesn't have. Re-survey the model landscape before
  each benchmarking campaign (it moves fast); keep weaker same-class models
  only as robustness points. (Owner directive; standing in STATE.)
- **Example values anchor everything: length, format, field presence, AND
  content distribution.** The campaign's central discovery, measured four
  independent ways: descriptive values teach cap-breaking (reflect 11/20→0
  when the journal example said "2-4 sentences" into a 30-word cap);
  id-like tokens in example prose get copied into id fields; example skills
  skew the generated-skill distribution (recall+explain 24%→58%) and an
  example null suppresses plan revisions even at codex tier; trailing
  example fields get truncated by small models (required fields first).
  Skeletons must DEMONSTRATE compliance with content orthogonal to real
  decisions. Lint-enforced: src/dojo/prompts/README.md item 9.
- **A shape-pass can be a vacuous pass — read the passing outputs too.**
  lfm's 7/20 baseline reflect "successes" were all empty-op no-ops;
  hardened templates converted hollow compliance into honest capability
  failures that LOOK like a regression. Before calling a regression, check
  what the old passes actually contained.
- **Single-run deltas need a variance floor.** Identical templates, driver,
  and corpus re-ran at ±3/kind and ±3 overall (4B): replicate before
  adjudicating small deltas; ±1-scenario noise bands are fantasy at this
  scale. Bonus: shape-hardening itself collapsed run sd 3.2→0.6 —
  determinism is a measurable product win.
- **The driver is part of the measurement.** Endpoint (generate vs chat),
  CLI version (0.32 rewrap junk in piped stdout), and think-binding
  differences each produced fake deltas bigger than most real effects.
  Never compare batteries across driver configs; re-baseline instead.

## 2026-07-18 — empty-INSIGHTS reflect payloads bait update-ops from 4B models
Nine consecutive single-shot failures (qwen3.5:4b ×6, gemma3:4b ×3) on a
reflect payload whose INSIGHTS section was empty: the models repeatedly
emitted `op: "update"` (with attempt ids or prose stuffed into `id`) though
there was nothing to update. The skeleton's FIRST example is an update op —
example-bleed (README failure mode 9) makes it the default move even when
the context forbids it. Candidate future arm (not shipped): compiler-side
fragment that leads with the create-op example when the store has zero
active insights — branching in the compiler, never the model (craft rule 5).
Codex/gpt-5.5 landed the same payload first try; visible-corpus reflect
ok-rates for 4B models (~27% qwen) already price this in.

## 2026-07-18 — near-empty registries bait URL syntax into route topic paths
gpt-5.5, routing a capture whose locator was a URL into a campaign with NO
listed topics (root only): three straight rejections proposing slash-bearing
leaves ('git/bisect run', 'git/bisect') then new_topic for the existing
root. With a realistic topic registry the same model routed first-try. Two
reads: the locator's path syntax bleeds into topic_path when the registry
offers no path-shaped exemplars to imitate; and the near-empty-registry
case (fresh direct-door campaigns) is the hostile edge for routers. Not
corpus-covered; candidate visible scenario for a future (fresh) session.

## 2026-07-18 — a refusal scenario must PIN its refusal, or it punishes the sanctioned door
Owner probe on the skill tier's respect_the_no: `dojo more` IS the
sanctioned pathway for an explicit "give me more" (the completion envelope
names it), so the ideal driver runs it — and the scenario's
no_extension_session check is only fair if the seed GUARANTEES the debt
guard refuses. The original seed carried ~3 dues against capacity 28; the
refusal came from the flimsy no-material branch, and a daily-first agent
(replenishment → stock appears) could have been granted, then scored 0 for
walking the sanctioned door correctly. General rule for behavioral evals:
any check that rewards ABSENCE of an action must be paired with a free
test proving the system deterministically refuses that action under the
seed — otherwise the scenario grades the fixture, not the agent.

## 2026-07-18 — fresh-machine sandboxes need shadowing, not removal
Bootstrap-install scenario (skill tier): simulating "no dojo binary" by
dropping dojo-bearing PATH entries breaks the driver itself — agent CLIs
routinely live BESIDE dojo in ~/.local/bin (install.sh symlinks there).
And running install.sh under the real $HOME would let its venv rollback
`rm -rf $HOME/.dojo/venv` clobber the owner's live install. Both isolations
want the same shape: REPLACE the container and re-link everything except
the excluded names (PATH entry → shadow-bin minus dojo/pipx; $HOME →
sandbox home minus .dojo/.local, so agent auth like ~/.claude passes
through while every install write lands sandboxed). pipx is excluded with
dojo deliberately: it pins install.sh to its deterministic venv route and
keeps `pipx install --force` from ever seeing real state.

## 2026-07-18/19 — drop-diagnosis session learnings

- **A judge can fail a driver honestly: set-level criteria vs the verbatim-quote
  gate.** "Spans three axes" is proven by SEVERAL short quotes; the judge joins
  them `"a", "b", "c"` and the joined string is no substring of the output → the
  weight-4 pass was discarded as unproven and diagnostic_axis_coverage sat
  capped at 0.6 while the driver output was fine. Fixed (3c3041f): fragment
  splitting, every substantial fragment must be verbatim. Same family as the
  2026-07-11 escape-decoding fix — when a floor won't move, audit the JUDGE
  MECHANICS before the prompt.
- **Model-side conditional branches in templates don't fire — at any caliber.**
  The 10b downward-calibration rule ("when RECENT shows repeated struggle, go
  gentler") was executed by nobody: codex anchored on the TASK line's nominal
  difficulty twice (floor stuck at 0.3). The compiler knows the condition
  deterministically; craft rule 5 was right all along — a conditional the
  compiler can evaluate must be a compiler-selected fragment, not model prose.
  (Same fix shape as the empty-INSIGHTS create-first skeleton.)
- **The skeleton-final anchor pattern-locks token one to `{`.** 55/62 battery
  runs started with `{` at byte zero; the "anything before it is ignored"
  license is a dead letter in practice — prompts END with a JSON skeleton, and
  pattern completion continues it. Whether this RESTRICTS models that think by
  outputting (~4B open models; internal thinkers are unaffected, sub-1B is
  measurably hurt by invitations) is an open empirical question — the
  deliberation trap-benchmark design (QUESTIONS) measures thinking by its
  FRUIT (trap-avoidance delta between anchor variants), immune to the
  internal-vs-visible thinker confound.
- **Example-content bleed reconfirmed live at 4B (README mode 9).**
  mastery_resolution, qwen3.5:4b: op text "rushes multi-step problems" /
  "process.skips_checking" copied verbatim from the skeleton's example values
  into real ops — shape-pass, pedagogy-wrong. Skeleton example values must stay
  orthogonal to any real decision the scenario could want.
- **Battery latency is not product latency.** Single-stream, real counters
  (qwen3.5:4b, real 7KB reflect payload): prompt processing 106 tok/s,
  generation 7.6 tok/s, 47s total. The same call inside a 3-concurrent battery
  reads as 150-220s and the worst collisions hit the 240s driver timeout (7
  infra-errors in iterW). Never quote battery wall-clocks as user-facing
  latency; prefill (not decode) dominates single-stream cost on weak hardware,
  which is what keeps input-side compression (parked armACC-in) interesting.
- **Skeleton examples anchor COUNT and TYPE, not just content (2026-07-19;
  README mode 10).** An empty-store ops example showing two `create` ops made
  models at BOTH tiers emit exactly two creates (codex plateau_remediation
  'two insights, not one' 0.12; qwen README-demo 2 creates in 2/2 budgets);
  the mixed update+create example never did this. One example op per
  distinct valid TYPE, never a repeated type, unless multiplicity itself is
  the lesson. Same family: gemma copied the DESCRIPTIVE placeholder value
  "the insight's id" verbatim 3× in one battery — every skeleton value must
  be a realistic literal (P9 queued).
- **A skeleton must satisfy the template's own Check line (2026-07-19).**
  campaign_plan's topics literal declared `a.b.c` while the phases literal
  referenced `a.b` — the skeleton DEMONSTRATED the violation ("every phase
  topic appears in topics") and gemma reproduced it as a stable two-sample
  failure. Fixing the one literal removed the class at both models. Lint
  candidate: compile every skeleton through its own validators.
- **Rule bytes are not free even when semantically right (2026-07-19).**
  +349B of correct new reflect rules doubled 4B journal-omissions and cost
  −3 ok (11→8/23); the same semantics at −213B scored 13/23 — ABOVE the
  pre-change bar. Weak models pay attention-tax per byte of rule mass near
  tail fields; state each decision once, delete generalizer sentences that
  repeat what cases already state inline.
- **A starved machine voids measurements; contention voids plan minis
  (2026-07-19).** Load 135/8-cores + 90% swap produced 7/9 driver timeouts
  that vanished on the recovered machine; 3 concurrent plan-length
  generations blow the 240s timeout even on a healthy box (first wave gets
  1/3 GPU each). Resource checks before batteries are data hygiene, not
  courtesy; plan-only minis run workers=1.
- **The deliberation invitation is caliber-divergent — measure, never
  assume (2026-07-19, 6i grid).** The same compiler-appended invitation
  ("think it through step by step first — write your thinking, then the
  JSON") made qwen3.5:4b write ~450B of pre-JSON deliberation and raised
  deterministic trap-avoidance 44%→75% with shape flat — while gemma3:4b
  ignored it entirely (pre_bytes unchanged) and got slightly worse
  (rejects 2→4). Same 4B footprint class, opposite response. This is WHY
  anchor behavior is a fulfiller PROFILE (opt-in config, compiler-
  selected) and never a default: the default stays byte-identical
  neutral, and the profile carries per-caliber guidance. Also proven en
  route: the trap corpus discriminates (gemma neutral near-ceiling 0
  hits; qwen neutral hit both plan dependency-root traps), and
  pre_bytes is a sufficient mechanism check — no thinking-trace access
  needed.
