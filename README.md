# Dojo

Practice what you're learning.

Dojo is a planned standalone, local-first source-to-practice app. It turns trusted material — notes, articles, videos, papers, conversations, projects — into active recall, spaced practice, and retention/atrophy feedback, guided by what the user actually cares to retain about the topic at hand.

This repository is the fresh productionized version of the earlier Cognitive Dojo prototype. The initial purpose of this repo is to define the clean product/API/CLI surface before implementation accretes around prototype-specific assumptions.

## Foundational pedagogy

Agents and humans implementing this repo should read [`AGENTS.md`](AGENTS.md) and [`docs/pedagogy-foundation.md`](docs/pedagogy-foundation.md) first. The pedagogy foundation is the backbone of the production product: mission-grounded teaching, source-backed knowledge, zone-of-proximal-development calibration, active production before feedback, retrieval practice, spacing, interleaving, durable evidence, and adaptation without bombardment.

## Product stance

Dojo should be:

- standalone first;
- local-first and privacy-respecting;
- source-grounded rather than chat-first;
- usable from a canonical CLI;
- adaptable through optional clients/adapters such as Telegram/Hermes, MCP, web, mobile, and browser extensions;
- simple by default, precise when needed.

## Current docs

- [`docs/cli-interface-design.md`](docs/cli-interface-design.md) — future-aware CLI design to build features against.
- [`docs/llm-provider-interface.md`](docs/llm-provider-interface.md) — provider/harness-agnostic LLM integration design.
- [`docs/ai-connector-interface.md`](docs/ai-connector-interface.md) — task/artifact/capability connector interface for arbitrary LLMs, harnesses, tool use, and generated verifiers.
- [`docs/terminal-ux-and-tech-stack.md`](docs/terminal-ux-and-tech-stack.md) — Python/Typer/Rich/Textual stack recommendation and input/choice interaction patterns.

## Early architecture target

```text
core learning engine
  -> stable CLI / library API
  -> optional adapters: Telegram/Hermes, MCP, desktop/web/mobile
  -> optional connectors: files, Markdown, RSS, Obsidian, Anki, etc.
```

The MVP should validate one narrow thesis first:

> Serious learners will use a local/open-source tool that turns trusted source material into active recall, spaced practice, and retention feedback.

Do not let the product become a generic AI tutor, generic flashcard clone, or broad brain-training arcade before this loop works.
