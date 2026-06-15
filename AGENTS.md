# Agent guidance

Before implementing or changing Dojo, read [`docs/pedagogy-foundation.md`](docs/pedagogy-foundation.md).

That document is the foundational pedagogical backbone for this production repo. Product, architecture, CLI/API, adapters, source ingestion, exercise generation, scheduling, scoring, and learner-state work should preserve it.

Key rule: Dojo is not a generic AI tutor, flashcard clone, or toy brain-training arcade. It is a local-first learning engine for mission-grounded, source-backed, calibrated, active practice that builds durable storage strength through retrieval, spacing, interleaving, evidence, and adaptation.

Keep implementation slices small, but do not violate the pedagogy foundation to ship faster.
