# ADR 008: Sliding Window History in Campaign Reflection

## Status
Accepted

## Context
Dojo processes learner progress and calibration through periodic Campaign Reflection runs (CLI: `dojo reflect`). To ensure files are readable, attempts that have been analyzed by the reflection engine are marked as reflected (`reflected: true` in frontmatter).

However, if the reflection system *only* processes unreflected attempts (those generated since the last reflection run), it acts on a very narrow slice of data. This introduces a **blind spot for slow-developing patterns** (or "micro-signals"). For example:
*   If a learner makes a recurring grammatical or logical mistake once every 3 sessions over a span of 10 sessions, each individual reflection run will only see a single isolated mistake.
*   In isolation, the engine will categorize this mistake as a minor slip rather than a systematic misconception.
*   Consequently, no active Insight is created, and the slow-developing pattern is never caught.

We need a design that allows the reflection engine to recognize long-term, slow-occurring patterns without bloating prompt context or keeping historical attempts permanently unreflected.

---

## Decisions

### 1. Sliding Window History Payload
When compiling the payload for a reflection run, the engine will include:
1.  All **unreflected attempts** (where `reflected: true` is not set).
2.  A **sliding window of the $N$ most recent attempts** (typically the last 15–20 attempts, regardless of whether they have already been consolidated/reflected).
3.  The complete set of currently **active Insights** (which represent the consolidated long-term memory of patterns detected in past runs).

This ensures that the reflection engine has visibility over a window of historical attempts, allowing it to perform cross-session trend analysis in a single LLM context.

### 2. Pattern Matching & Evidence Aggregation
The reflection LLM compares the sliding history against active insights:
*   **Merge & Append:** If the sliding history shows a recurring failure pattern matching an active insight, the reflection engine updates the insight's description and appends the new attempts to its `sources` frontmatter list.
*   **New Insight:** If the sliding history reveals a new recurring pattern (not yet represented by an active insight), it creates a new active `Insight` with the relevant attempts listed as sources.
*   **Resolution:** If the sliding history shows consistent mastery on a topic that has an active insight, the insight is marked as `status: resolved`.

---

## Consequences
*   **Cross-Session Pattern Recognition:** Slow-occurring errors are easily caught because the LLM has visibility over a window of historical attempts.
*   **Deduplication:** Active insights serve as a persistent "long-term registry," preventing duplicate insight files from being created across consecutive reflection runs.
*   **Token Efficiency:** A sliding window of 15–20 attempts represents a very small token footprint (typically <2,000 tokens), making it highly performant and cost-effective.
*   **Auditability:** Insight files retain a rich, growing list of clickable relative links pointing directly to the attempts that serve as evidence.
