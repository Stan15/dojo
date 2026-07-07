# ADR 011: Store Protocol with Markdown as Canonical Backend

## Status
Accepted (design phase, 2026-07-07).

## Context
Human-readable markdown storage is a product feature (the learner can read their
entire learning life in files, versioned by git). But an app milestone will want a
database (Postgres). The prototype's store is markdown-only and leaks storage
details upward: entities carry file paths (`Attempt.session` is a root-relative
path), the facade duplicates every repository method, and git auto-commits fire per
entity write with errors swallowed.

## Decision
1. **A `Store` protocol** is the only storage surface the domain sees: typed
   repositories per entity, **ID-based references only**, declared query filters,
   and an `audit(message)` hook for backend-appropriate versioning. Backend chosen
   by `store.backend` config (`markdown` now, `postgres` later).
2. **One shared conformance suite** (round-trip property tests, filter semantics,
   concurrency/locking behavior, audit behavior) parameterized over backends. A
   backend exists when it passes; the suite *is* the contract.
3. **The markdown format is a documented public contract** (blueprint §5):
   frontmatter = schema fields with defaults omitted; body = the entity's single
   designated long-text field; IDs are identity, filenames are presentation;
   unknown/extra frontmatter keys survive round-trips (human edits are sacred).
4. **Audit batching:** one git commit per CLI command, not per entity write; git
   failures surface in `dojo doctor` instead of being silently swallowed.

## Consequences
- Postgres later is a bounded task: implement the protocol, pass the suite — zero
  domain changes. This de-risks the app stretch goal now, at the cost of one
  indirection layer.
- Path-leaks in current schemas must be migrated to IDs (M1).
- Human edits to files are a supported input, which the conformance suite must
  cover (edited-file fixtures), not an anomaly.
