# Blog strategy for the HN pulse — the honest build story

_Owner-facing plan (2026-07-18). Companion to growth-strategy.md §6 Phase 1
("2-3 deep-dive posts seeded to the AI-tools orbit"). Every post is written
in YOUR voice about YOUR decisions; none claims authorship of code you
didn't write. The standing honesty frame (below) is itself part of the
positioning._

## 0. The honesty frame — use it verbatim, in every post

> *Dojo's implementation was written by AI sessions (Claude) working under
> a method I direct: written state handoffs between sessions, human-gated
> phase transitions, ratcheted test/eval baselines, and a blind holdout
> protocol that keeps the AI from gaming its own evals. The product
> decisions, the pedagogy rulings, and the method are mine; the diffs are
> the machine's; every claim below links to the repo's decision records.*

Why lead with this instead of hiding it: in 2026 every reader assumes AI
wrote the code anyway. Saying it FIRST — and then showing a direction
system rigorous enough to be the story — converts the suspicion into the
hook. It also makes post #1 possible at all.

## 1. The post lineup (six, ranked; first three are the Phase-1 seeds)

### P1 · "I run my AI coding sessions like an engineering org"
**The meta post — likely the biggest, and it frames all the others.**
- *Your material (all yours):* the method — sessions treated as one
  continuous engineer via `STATE.md` / `QUESTIONS.md`-with-defaults /
  `INSIGHTS.md`; phase gates only a human opens; value-ordering (never
  lose directed work, strictly highest-value-first); delegation's
  certainty + break-even gates; delete-over-retain; "an out-of-date STATE
  is a bug you introduced."
- *Beats:* the async QUESTIONS board with your inline one-word rulings
  ("agree", "ok") · a real mid-session course-correction · the day a
  session got contaminated and the protocol disqualified it (twice — show
  the STATE entries; the system catching its own operator is the proof it
  is real) · what you DON'T do (no vibes-driven "keep going" prompting).
- *Receipts:* screenshots of STATE/QUESTIONS diffs, owner-ruling commit
  messages (85 of them), the method file itself.
- *Channel:* HN-shaped on its own; also the AI-tools newsletter orbit.

### P2 · "My AI kept gaming its own evals, so I built it a blind holdout"
**The rigor post — the most technically novel; nobody writes this one.**
- *Your material:* the directive itself ("the prompts shouldn't reward
  hack; create a holdout set"); the contamination principle you ruled —
  *a model cannot firewall information inside its own context window; "I
  read it but won't use it" does not exist*; total blindness tightened to
  names-and-counts; burn-and-replace for exposed scenarios; cold-context
  subagents as scenario authors; ONE consumable bit per gate run.
- *Beats:* why prompt iteration reward-hacks visible rubrics · the
  protocol mechanics · the v1.0.0 gate that FAILED honestly (gap 0.184)
  and the remedy rule (broaden visible, never peek) · the two
  contamination events and their blind remedies — including pytest ids
  leaking holdout names and the fix that made ids opaque.
- *Receipts:* the gate code (aggregate-only by construction), STATE's
  contamination entries, the ratchet baselines.
- *Channel:* HN + evals/LLM-engineering communities. This is the post the
  Show HN comment section will cite.

### P3 · "I gave the LLM the keys to my learning app. Then I took them back."
**The architecture arc — honest because the wrong turn was also yours.**
- *Your material:* the origin (installed Hermes; wanted meaningful use;
  wanted to retain the math/ML/physics YouTube firehose and train memory
  and mental math); first build let the agent schedule reviews (ADR 003,
  archived SQLite implementation in-tree as the fossil record); the
  reversal you drove: scheduling is date math, LLMs do vibes — the
  deterministic core + AI-as-validated-tasks split (ADRs 010/012); the
  harness-first inversion (the agent you already pay for IS the model —
  no second bill, no API keys).
- *Beats:* what breaks when an LLM schedules · the one seam (schema-
  validated single-shot tasks; weak model can't corrupt state) · "the
  archived_implementation/ directory is my mistake, kept on purpose."
- *Receipts:* ADR 003 vs 012 side by side; the fossil directory.
- *Channel:* HN; also the local-first community.

### P4 · "Duolingo can't say no. My learning app refuses me daily."
**The pedagogy-ethics post — anchors the Show HN itself (per growth §2).**
- *Your material (rulings, verbatim from the ledger):* the streak counter
  you cut — *a live counter creates loss-anticipation no gentle wording
  removes*; push surfaces get principles, pull surfaces get numbers;
  at-request-only (`dojo more` is never offered, only answered, and
  refuses with the numbers when the 7-day review budget says no);
  no-guilt returns (two weeks away → a sane packet, not 400 reviews);
  calibration measures, never gates; you're never graded on material
  nobody taught you.
- *Beats:* each ruling as invariant-enforced-in-code, not copywriting ·
  the SRS-abandonment table from growth §1 (every scar → shipped answer).
- *Channel:* Show HN anchor + r/Anki companion (with the import demo when
  A1 ships).

### P5 · "Every belief my app holds about me comes with receipts"
**The transparency post — and the most personal one.**
- *Your material:* the ownership directive ("insanely well thought out
  visibility tools so the user feels complete ownership"); your word
  outranks the machine's hypothesis (resolve --because, verbatim).
- *The story that makes it:* your own store caught
  `practice.avoidance_when_unsure` — receipts showing you literally typed
  "/exit" and "i don't wanna practice this anymore." into the answer box,
  and the system named the pattern. Self-deprecating, human, and the
  single best demo of evidence-not-vibes.
- *Channel:* broad; the most shareable/quotable of the six.

### P6 · "Nine measured ways small models mangle your JSON prompts"
**The engineering-notes post — cheap to write, evergreen search traffic.**
- *Your material:* the campaign you commissioned and its spend rules
  (free local evidence first; owner-gated strong-tier runs); the
  best-in-class caliber ruling (benchmark the strongest model per
  footprint, or the floor is a lie); the mutual non-regression rule
  (quality work runs token gates, token work runs quality gates — both
  tested).
- *Beats:* the measured failure modes from prompts/README.md (enum echo,
  comment poisoning, example-length anchoring, quote-wrapping, the
  empty-list update-op bait…) each with the fix that survived; the
  output-byte ratchet idea (rejections are the real token cost).
- *Channel:* HN + local-LLM communities; pairs with `dojo benchmark`
  scorecards as the call to action.

## 2. Sequencing against the pulse (growth §6)

1. **Now → tag:** nothing publishes. Finish the gate work; polish drafts.
2. **Phase 1 (weeks 1–4 after v1.0.0 + GIF):** P1, then P2, then P3 —
   one per week, seeded to newsletters; repo + docs already public so
   every claim is checkable. Watch for the organic-pull heuristic
   (a stranger files an issue / posts a scorecard).
3. **The pulse:** Show HN anchored on P4's story ("the learning app that
   refuses you"), first comment links P1/P2/P3; P5 published the same
   week as the human follow-up while attention is warm.
4. **Post-pulse trickle:** P6 + community scorecard roundups; r/Anki with
   the import demo when A1 lands.

## 3. Craft rules for every post

- Your voice, first person, decisions and reasons — the AI is a named
  tool, prominent in the honesty frame, invisible in the prose otherwise.
- Every claim links a receipt (ADR, ledger line, commit, test) — the
  public repo is the citations section.
- One story per post; cut the rest (the same discipline as the README).
- End each with the same two links: the repo and the 60-second install.
- No launch language before the pulse; these are engineering notes, not
  announcements.
