# ADR 015: Anki Interop — Import and One-Way Export, Never Live Sync

## Status
Accepted direction, tagged **backlog** (2026-07-07). Nothing in v1 milestones.

## Context
The product owner asked whether Dojo should integrate with Anki ("meet users where
they are"), explicitly delegating the decision to the north star. Options surveyed:

1. **Anki as practice client / live sync (AnkiConnect):** reviews happen in Anki.
2. **Deck import:** ingest a user's existing .apkg decks as Dojo sources.
3. **One-way export:** emit Dojo `recall` items as an .apkg (genanki, MIT).

## Decision
**No live sync or Anki-as-client, ever-until-rethought.** Dojo's differentiator is
the evidence loop (attempts, latency, error tags → insights → calibration →
scheduling). Reviews executed inside Anki produce no evidence Dojo can learn from,
and two schedulers claiming the same memories breaks the retention guarantee
(ADR 012's determinism assumes one scheduling authority). Anki also covers only
the recall lane — none of campaigns, generative skills, rubric grading, or
provenance. Per the north star: adapters are optional boundaries around the core,
and Dojo is not a flashcard clone. The priority user practices inside an AI
harness conversation, not inside Anki.

**Two aligned, bounded interop features go to backlog:**

1. **`dojo import anki <deck.apkg>`** — decks are *material*, and meeting users
   where their material is, is pure north star. Cards become a Source (provenance:
   deck name, note ids) whose facts flow the normal candidate → review → active
   path. Feasible: .apkg is a zip containing sqlite; read-only parsing, no Anki
   installation required.
2. **`dojo export anki`** — one-way handoff of `recall` items via genanki (MIT)
   for phone review. Exported items are marked `custody: external` and Dojo
   **stops scheduling them** (no double-scheduling; the evidence loss is explicit
   and shown at export time). Honest degradation, not silent duplication.

## Consequences
- v1 scope unchanged; both features are bounded, independent backlog items.
- The custody flag (`custody: external`) enters the domain model vocabulary now so
  M1 schemas can reserve it cheaply.
- If demand ever justifies live sync, this ADR is the argument that must be
  defeated first: name where the evidence loop's authority would live.
