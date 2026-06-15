# Agent guidance

Before implementing or changing Dojo, read these in order:

1. [`docs/product-north-star.md`](docs/product-north-star.md) — vision, north star, source problem, MVP loop, and success signals.
2. [`docs/pedagogy-foundation.md`](docs/pedagogy-foundation.md) — the pedagogical backbone for product behavior.
3. [`docs/development-approach.md`](docs/development-approach.md) — how to build slices, use Linear, preserve architecture seams, and verify work.
4. [`docs/api-specification.md`](docs/api-specification.md) — programmatic & CLI semantics and structural specifications.
5. [`docs/adr/`](docs/adr/) — formal Architecture Decision Records, including the JIT pipeline and unified source representation (ADR 001, ADR 002).
6. The active Linear issue/project — current sprint scope and dependencies.

Product, architecture, CLI/API, adapters, source ingestion, exercise generation, scheduling, scoring, and learner-state work should preserve those docs.

Key rule: Dojo is not a generic AI tutor, flashcard clone, or toy brain-training arcade. It is a standalone, local-first learning engine for mission-grounded, source-backed, calibrated, active practice that builds durable storage strength through retrieval, spacing, interleaving, evidence, and adaptation.

Keep implementation slices small, but do not violate the north star, pedagogy foundation, or architecture records to ship faster. Do not treat `docs/ramblings-planning-not-authoritative/` as current implementation guidance.
