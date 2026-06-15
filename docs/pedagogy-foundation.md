# Pedagogy foundation

This is authoritative product guidance for agents and humans implementing Dojo. Treat it as the pedagogical backbone of the system. Architecture, CLI/API design, scheduling, source ingestion, exercise generation, and adapters should preserve these principles.

This guidance adapts Matt Pocock's `teach` skill methodology into production product behavior. Dojo is not a one-off chat tutor or a pile of generated quizzes. It is a local-first learning engine that turns trusted source material and learner goals into durable knowledge, usable skill, and long-term retention.

## Core thesis

Dojo should help a learner practice what they actually care to retain.

A good Dojo loop:

1. starts from the learner's mission;
2. grounds knowledge in high-trust sources;
3. calibrates to the learner's current level;
4. asks for active production before feedback;
5. builds long-term storage strength through retrieval, spacing, and interleaving;
6. records evidence about what happened;
7. adapts future practice without overwhelming the learner.

The product should optimize for useful transfer, not benchmark scores, streak theatre, or toy brain-training prompts.

## Mission first

Every learning flow should be tied to the learner's reason for caring.

The system should capture enough mission/context to answer:

- What does the learner want to be able to do or understand?
- Why is this worth retaining?
- Where might this knowledge or skill transfer outside Dojo?
- What level of depth is useful now?
- What should be excluded or deferred?

If the mission is unclear, ask a small number of targeted questions before generating practice. Do not produce a broad curriculum just because a topic was named.

## Knowledge, skill, and wisdom

Dojo should distinguish three kinds of learning value:

- **Knowledge:** facts, concepts, vocabulary, source claims, examples, and mental models.
- **Skill:** active capabilities the learner can perform: recall, explain, identify, compare, apply, solve, recognize, critique, or create.
- **Wisdom:** judgment from real-world use, communities, practitioners, context, and feedback beyond the practice environment.

Production behavior should not collapse these into generic flashcards. A source-derived fact, a practiced skill, and an external real-world judgment loop need different product surfaces and evidence.

## High-trust resources before fact teaching

For fact-heavy topics, source trust is part of pedagogy.

Dojo should prefer:

- user-provided trusted material;
- explicit source provenance;
- cited claims;
- source version/date where relevant;
- durable references/glossaries extracted from sources;
- validation or review gates before promotion into active practice.

LLMs may help extract, draft, summarize, rubric-grade, or propose exercises, but the LLM should not become the hidden source of truth. When facts matter, store the source behind the fact.

## Zone of proximal development

The learner should feel challenged just enough.

Dojo should infer or ask for the learner's current level, then choose practice slightly above demonstrated ability. Unknown level means calibration, not hard generated content.

Good calibration is:

- short;
- low-stress;
- diagnostic;
- respectful of uncertainty;
- designed to reveal prerequisites and confusions;
- followed by practice near the learner's frontier.

Avoid both extremes:

- too easy: creates boredom and false confidence;
- too hard: creates overload, shame, and noisy evidence.

## Fluency vs storage strength

Immediate ease is not mastery.

Dojo should track the difference between:

- **Fluency strength:** in-the-moment speed/ease after exposure;
- **Storage strength:** durable ability to retrieve or apply after time, interference, and varied cues.

The product should build storage strength with desirable difficulty:

- retrieval practice before explanation;
- spaced review;
- interleaving related skills where appropriate;
- varied cues and transfer contexts;
- delayed checks;
- occasional maintenance of old strengths.

Do not over-promote an item or skill based on a single fluent response.

### Strategy customization and novelty ratios

Not all items or skills benefit from the same repetition scheduling:
- **Repetitive Retrievability (Knowledge/Facts):** Static items (e.g. key glossary terms, exact vocabulary, rules) benefit from spaced repetition of the exact same item to cement retrievability.
- **Generative Novelty (Skills/Procedures):** Dynamic items (e.g. coding syntax application, problem solving, analysis tasks) require varied, novel cues matching the skill path to ensure the user does not merely memorize the specific prompt. Scheduling for these must prioritize refreshing via alternative candidate exercises rather than exact item repetition.
- **Personalized Adaptation:** The training frequency, ideal novelty ratio, and optimal scheduling interval should be calibrated against the user's specific learning goals, demonstrated latency, and custom style.

## Active production before feedback

The learner should produce an answer, prediction, sketch, explanation, choice, or attempt before seeing the solution whenever possible.

Good prompts:

- are short enough to fit working memory;
- make the target skill clear to the system, not necessarily to the learner before timing starts;
- have a scorer or review rubric;
- can be answered naturally in the target client;
- avoid leaking clues through formatting or answer length;
- support immediate feedback after the attempt.

Explanations should usually come after the attempt, not before it.

## Short lessons, compact references, durable records

Dojo should preserve what matters in durable product surfaces:

- **References:** compact, source-backed summaries, glossaries, maps, algorithms, fact sheets, or checklists for review.
- **Learning records:** non-obvious learner insights, misconceptions, breakthroughs, mission changes, and future scaffolding implications.
- **Attempt/event evidence:** answers, timings, hints, skips, corrections, confidence signals, scoring details, and prompt-quality feedback.

Lessons or packets should be small and actionable. Reference material can be richer, but should remain skim-friendly and useful later.

## Non-bombardment is a product invariant

Dojo should feel sustainable.

Default practice should be short, bounded, and confidence-preserving. A packet should usually contain a small mix of:

- one easy or maintenance item;
- one weak/recently missed item;
- one near-frontier challenge;
- optionally one new high-value item.

Do not dump entire taxonomies, huge lists, or large generated banks into the learner's daily flow. Breadth belongs in source/reference/candidate surfaces; practice should be scheduled and paced.

## Exercise quality bar

Dojo should reject toy prompts.

An exercise is not good merely because it is answerable or generated. It should have:

- a clear target skill;
- a meaningful reason the learner should care;
- realistic constraints;
- a credible path to transfer;
- a scorer or rubric;
- source backing when factual;
- difficulty metadata;
- known distractors or common confusions where useful;
- a repair path if the prompt is ambiguous or low-quality.

If a learner complains that a prompt is useless, confusing, too easy, too hard, or toy-like, treat that as curriculum evidence, not learner failure.

## Adaptation and evidence

Dojo should adapt from evidence, not vibes.

Useful signals include:

- correctness;
- latency;
- hints;
- skips;
- corrections;
- answer edits;
- self-rating when provided;
- repeated error types;
- prompt-quality feedback;
- long-term retention checks;
- successful transfer to adjacent contexts.

Store raw attempt/event evidence and distill it into learner hypotheses. Generators and schedulers should consume compact, current, provenance-linked summaries rather than unbounded raw chat.

## Product boundaries

The core learning engine should own pedagogy-critical behavior:

- source provenance;
- candidate quality gates;
- exercise definitions;
- scoring/rubrics;
- attempt/event state;
- learner hypotheses;
- scheduling policy;
- calibration and intervention decisions.

Adapters such as Telegram, Hermes, MCP, web, mobile, browser extensions, and external LLM harnesses should not become the source of truth for learning state. They deliver interactions; the core owns learning.

## Implementation checklist for agents

Before adding or changing a learning feature, answer:

- What learner mission does this support?
- What trusted sources ground the knowledge?
- What skill is being practiced?
- What is the learner's current level, and how do we know?
- How does this stay inside the zone of proximal development?
- What active production happens before feedback?
- What evidence will be recorded?
- How will scheduling use that evidence later?
- How will we avoid bombardment?
- What makes this non-toy and transferable?
- What is the smallest useful slice to ship now?

If these questions cannot be answered, pause and design the pedagogy before writing more product surface.
