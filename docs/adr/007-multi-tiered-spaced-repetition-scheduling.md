# ADR 007: Multi-Tiered Spaced Repetition and Scoped Scheduling

## Status
Proposed (Planned for future implementation)

## Context
As Dojo moves to support multiple active Campaigns (learning tracks) interleaved within a single study session, we need a scheduling architecture that resolves two separate problems:
1. **Cross-Campaign Scheduling (Session-Level)**: Determining *which* campaigns the learner should focus on during a given practice session, based on time constraints, recency, and retention levels.
2. **Campaign-Scoped Scheduling (Concern-Specific)**: Determining *which* exercises are due within a single campaign. Different topics require different scheduling models (e.g., static memory recall benefits from traditional SM-2 spaced repetition, whereas procedural coding skills require generative novelty scheduling to avoid memorizing specific prompt wordings).

---

## Decision
We establish a **Multi-Tiered Scheduling Architecture** that separates campaign orchestration from campaign-local execution.

```text
               [ Practice Session ]
                        │
            ┌───────────┴───────────┐
     (Tier 1: Cross-Campaign Spaced Repetition)
            │                       │
      [ Campaign A ]          [ Campaign B ]
            │                       │
     (Tier 2: Scoped)        (Tier 2: Scoped)
     ┌──────┴──────┐         ┌──────┴──────┐
  [Memory]   [Skill]      [Memory]   [Skill]
  (SM-2)    (Novelty)     (SM-2)    (Novelty)
```

### 1. Tier 1: Cross-Campaign Spaced Repetition (Session-Level)
The `PracticeSession` acts as the top-level orchestrator. When the user starts a session (`dojo start`), the scheduler evaluates all active campaigns:
- **Campaign Urgency**: Evaluates campaigns based on the ratio of due exercises, elapsed time since the last practice, and active milestones.
- **Interleaving**: The session constructs a blended exercise list (e.g. drawing 3 high-urgency cards from Campaign A and 2 medium-urgency cards from Campaign B). This implements interleaving—a key desirable difficulty technique that forces the brain to switch contexts, improving long-term storage strength.

### 2. Tier 2: Campaign-Scoped Scheduling (Concern-Specific)
Within a single Campaign, scheduling is delegated to specific algorithms based on the learning concern of the active phase:

#### A. Memory/Fact Recall (Static-Recall)
- **Use Case**: Vocabulary, rules, math constants, static code API signatures.
- **Algorithm**: Standard spaced repetition (such as SuperMemo SM-2 or a modified half-life decay model).
- **Execution**: Evaluates attempts on the *same* exercise, calculating the next due date based on score, latency, and ease factor. It schedules exact repetitions of identical items to cement retrievability.

#### B. Generative Skills (Generative-Novelty)
- **Use Case**: Problem-solving, writing code scripts, oral argument construction, reading comprehension.
- **Algorithm**: JIT novelty replacement.
- **Execution**: Instead of scheduling exact item repetition (which leads to memorizing the question text rather than the skill), the scheduler tracks *topic mastery*. When a topic is due, it requests a *novel, alternative candidate* from the JIT generator matching the target difficulty and scaffolding level.

---

## Consequences
* **Desirable Difficulty**: Interleaving campaigns natively prevents the learner from getting comfortable in a single subject, enhancing storage strength.
* **Flexible Pedagogical Concerns**: By dividing scheduling into tiers, the top-level engine doesn't need to know how to schedule memory vs skills. It simply asks the active campaign for its "due list," and the campaign resolves its internal items according to its own local concerns.
* **No Database Overlap**: Campaigns remain completely isolated on disk. All cross-campaign interleaving happens in-memory at the session level.
