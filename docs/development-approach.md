# Development approach

## Execution principle

Build Dojo as a standalone local-first product with optional adapters, not as a wrapper around the prototype or a Hermes-only workflow.

The execution model is:

```text
north-star vision → architecture spine → smallest valuable slice → shipped learning loop → measured next bet
```

## Source of truth

- **Repo docs**: durable product vision, architecture spine, implemented behavior, and explicitly labeled non-authoritative planning notes.
- **Code/tests**: current working behavior.
- **Linear**: active sprint execution, issue status, dependency graph, and implementation sequencing.
- **Planning ramblings**: future-facing sketches only; they are not current contracts.

Agents should not treat `docs/ramblings-planning-not-authoritative/` as an implementation checklist. Use it for background only after reading the current docs and Linear issue.

## Architecture spine

Keep the product logic in a core library, with clients/adapters around it:

```text
Dojo core services
  -> local state (markdown store behind the Store protocol; ADR 011)
  -> stable CLI
  -> optional TUI/web/mobile clients
  -> optional adapters: Hermes, Telegram, MCP, browser capture
  -> optional AI connectors/providers/harnesses
```

Provider-specific or platform-specific behavior should sit behind explicit interfaces. The core should not depend on Telegram, Hermes, or a particular model provider.

## Current implementation bias

Use the smallest coherent production slice. Prefer:

- Python core and CLI first;
- markdown-file storage behind the `Store` protocol (ADR 011) for local state;
- typed request/result boundaries for AI tasks;
- command-backed AI connectors before provider-specific SDK lock-in;
- integration/E2E tests at seams;
- explicit provenance and validation over hidden LLM assumptions.

## Development rules for agents

1. **Read the north star first.** Start with `README.md`, `AGENTS.md`, `docs/product-north-star.md`, and `docs/pedagogy-foundation.md`.
2. **Check Linear for active work.** Use the Linear project for current story scope and dependencies.
3. **Keep slices small.** Implement the next user-visible step or architecture seam; do not expand the MVP because a future idea is attractive.
4. **Preserve real blockers.** Parallelize independent work, but do not fake independence by hiding necessary sequencing.
5. **Prefer integration tests at seams.** CLI ↔ persistence, connector invocation, source candidate flow, queueing, and practice sessions need real boundary tests. Unit tests can support, not replace, these checks.
6. **Do not over-mock.** Use fakes only when real dependencies are unavailable, unsafe, slow, flaky, expensive, or genuinely no-tradeoff. Pair early fakes with later real integration coverage.
7. **Do not silently trust generated content.** AI output should enter as candidates with provenance, validation status, raw output, and review path.
8. **Document current behavior only.** Do not write future API surfaces as if they already work. If a document is speculative, label it clearly.
9. **Keep adapters optional.** Hermes/Telegram/MCP are convenience integrations; the core product must remain usable without them.
10. **Commit verified work regularly.** Keep `main` green and push completed slices to avoid stale unmerged branches.

## Verification baseline

Before reporting production work done:

```bash
python -m pytest -q
git diff --check
git status --short --branch
```

For GitHub-backed work, be precise about lifecycle:

- implemented locally;
- committed;
- pushed;
- Linear updated;
- merged/main verified.

Do not call a task done merely because a prototype branch contains similar work.
