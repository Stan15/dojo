# Product north star

## North star

Dojo helps serious learners turn trusted source material into durable, calibrated practice.

The product should make it easy to go from:

```text
source I care about → concepts worth retaining → reviewable practice candidates → active recall sessions → evidence of retention, atrophy, and next best practice
```

The promise is not “chat with an AI tutor.” The promise is: **what you read, watch, study, and care about becomes an adaptive practice system that helps you remember and use it later.**

## The source problem

Most learning tools start from either:

- blank flashcards the learner must author manually;
- generic decks and quizzes detached from the learner’s actual sources;
- chat conversations that produce explanations but little durable practice state;
- AI-generated exercises with unclear provenance and inconsistent quality.

Dojo starts from the learner’s own trusted material: notes, articles, videos, papers, books, conversations, projects, and other sources.

The core source problem is to preserve provenance while transforming material into useful practice:

1. **Capture source context** without losing where ideas came from.
2. **Identify topics and subtopics** without forcing a single flat label too early.
3. **Generate or author candidate exercises** that remain reviewable before becoming trusted practice.
4. **Queue a small number of useful items** instead of flooding the learner.
5. **Track attempts and evidence** so scheduling adapts to performance, recency, confidence, and atrophy.

Source provenance matters because learners need to trust what they are practicing, revisit the original material, and audit or improve generated candidates.

## Product stance

Dojo should be:

- **standalone first**: the core product must work independently of Hermes, Telegram, MCP, or any single LLM provider;
- **local-first**: personal learning data should live locally by default;
- **source-grounded**: practice should trace back to trusted material or explicit user intent;
- **review-before-trust**: generated candidates are not automatically authoritative;
- **calibrated**: difficulty should be just above demonstrated ability, not randomly hard or trivially easy;
- **non-bombarding**: the product should avoid overwhelming the learner with giant curricula or endless generated items;
- **adapter-friendly**: Telegram, Hermes, MCP, browser capture, web/mobile, and model providers are optional boundaries around the core, not the core itself.

## What Dojo is not

Dojo is not:

- a generic AI tutor;
- a flashcard clone with AI sprinkled on top;
- a toy brain-training arcade;
- a chat transcript manager;
- a benchmark game;
- a system where generated content silently becomes trusted truth.

## MVP learning loop

The first production slice should validate one narrow loop:

1. Add a source or note.
2. Ask a configured AI command connector to draft candidate practice items.
3. Review candidates by topic/provenance.
4. Queue a small number into practice.
5. Start a practice session.
6. Reveal one prompt at a time.
7. Answer and record attempts.
8. Show progress/retention signals.

A feature belongs in the current slice only if it helps this loop ship or keeps the architecture reversible for it.

## Success signals

Strong signals:

- users import their own sources;
- users review and queue candidates;
- users complete practice sessions;
- users return later because the system remembers what needs maintenance;
- generated items can be traced to source material;
- progress views expose useful retention/atrophy evidence;
- the core workflow runs locally without privileged agent infrastructure.

Weak signals by themselves:

- repo stars;
- one-time demos;
- impressive AI output with no review or retention state;
- generic quizzes not tied to user sources;
- large future architecture plans without a shipped source-to-practice loop.
