# ADR 012: Deterministic Pedagogy Core (Allocation ≠ Memory; State on Stable Nodes)

## Status
Accepted (design phase, 2026-07-07). Refines and accepts the direction proposed in
ADR 007.

## Context
Two scheduling problems exist: *which campaigns get today's attention* and *what to
practice within a campaign*. The user's instinct was "spaced repetition at both
tiers." First-principles check: SR models forgetting curves — but campaigns don't
forget, learners under-attend them. Meanwhile per-item SR state for generative
skill exercises would model memories of items that, by the novelty principle
(ADR 007), never repeat — pure bloat. And an LLM must never do date math: retention
guarantees cannot depend on model caliber.

## Decision
1. **Tier 1 is allocation, not memory.** A deterministic, explainable priority
   score per campaign (due pressure, days-since-touch atrophy, deadline proximity,
   user weight; weights in config) ranks campaigns; the daily packet fills slots
   from the top with interleaving. Every choice carries a one-sentence reason.
2. **Tier 2 attaches memory state to stable nodes.**
   - `recall` (fact) exercises: FSRS-inspired per-item state `{due, stability,
     difficulty, reps, lapses}` updated by a pure function of (state, score,
     latency, clock).
   - `skill` topics: SR state lives on the **topic** (`topics.yaml`), not the
     exercise; a due skill topic triggers JIT generation of a novel item, and
     spent skill items retire. Scheduling state is bounded by syllabus size, not
     practice history.
3. **Two lanes per campaign:** retain (due memory state) and advance (frontier
   topic of the active phase, gated by deterministic criteria). Packet composition
   (maintenance + weak + frontier + optional new; cap 5 default / 8 hard) is a pure,
   seeded function — non-bombardment is enforced at one code choke point.
4. **The LLM influences scheduling only through validated structured outputs**
   (difficulty ratings, phase criteria, plan revisions via `campaign.reflect`),
   which feed the deterministic engine. It never selects, never dates.

## Consequences
- Retention math is offline, testable (seeded property tests), and identical under
  any model — the system's strongest guarantee lives in its cheapest code.
- Scheduling state stays small and human-readable (a few floats per fact item, one
  YAML per campaign for topics).
- FSRS-lite parameters start as sane defaults; per-learner parameter fitting is
  backlog, and the pure-function design leaves room for it without migration.
