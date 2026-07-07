# ADR 014: Adopt py-fsrs for Retention Scheduling

## Status
Accepted (2026-07-07). Realizes the "FSRS-inspired pure function" of ADR 012;
product owner directed reuse of existing SR tooling over bespoke maintenance.

## Context
ADR 012 specifies per-item memory state `{due, stability, difficulty, reps,
lapses}` updated by a pure function, with per-learner parameter fitting as a
backlog wish. Writing our own FSRS-lite means maintaining memory-model math —
exactly the kind of dense, subtly-wrong-prone machinery the method says to either
prove or not own at all.

Candidates surveyed (2026-07-07):

| Library | Algorithm | License | Fit |
|---|---|---|---|
| **py-fsrs** (`fsrs` on PyPI, v6.3.1 Mar 2026) | FSRS-6, official reference impl (Anki's algorithm) | MIT | Dependency-free core; Python ≥ 3.10; `Card` state is exactly ADR 012's; JSON serialization; optional `fsrs[optimizer]` for per-learner fitting; actively maintained by open-spaced-repetition |
| fsrs-rs-python | FSRS (Rust bindings) | — | Binary dependency; performance we don't need |
| ebisu | Bayesian half-life | MIT | Parameters hand-tuned by design; no optimizer; different paradigm |
| supermemo2 | SM-2 | MIT | Benchmarks: FSRS needs 20–30% fewer reviews at equal retention |

## Decision
1. Depend on **`fsrs` (py-fsrs, MIT)**, pinned to major version 6. The core
   scheduler is the only required piece; `fsrs[optimizer]` stays an optional
   extra for future parameter fitting.
2. **One memory model, two node types** (per ADR 012): an FSRS `Card` attaches to
   each `recall` exercise and to each `skill` topic (rated from the attempt
   outcome on that topic's generated item). Card state serializes into
   frontmatter / `topics.yaml` via its JSON form — human-readable, round-trippable.
3. **Score-band → Rating mapping** lives in one dojo-owned pure function:
   `0.0, 0.3 → Again`, `0.7 → Hard`, `1.0 → Good`, and `1.0` with fast latency
   (or a `too_easy` skip) `→ Easy`. Bands stay dojo's grading language (ADR 010
   prompts); FSRS ratings stay an internal detail.
4. Dojo wraps the library behind a thin `scheduling` module boundary (pure
   functions in/out of our domain types) so the dependency is swappable and the
   conformance/property tests are ours, not the library's.

## Consequences
- We stop owning memory-model math; upstream benchmarking (500M+ Anki reviews)
  and FSRS-6 improvements arrive by version bump.
- Per-learner optimization becomes a bounded backlog task instead of a research
  project.
- New runtime dependency (MIT, pure Python, zero transitive deps) — acceptable.
- Python floor stays 3.11 (Q5), comfortably above py-fsrs's 3.10 requirement.
- The wrapper boundary + seeded property tests (M3) remain our correctness
  guarantee; we treat the library as a component, not as the specification.
