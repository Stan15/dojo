# ADR 003: Dynamic JIT Replenishment over Static Upfront Candidate Generation

## Status
Accepted

## Context
In early iterations of Dojo, ingesting a source immediately triggered candidate generation to produce a large pool of exercises. However, this upfront generation has significant limitations:
1.  **Rigidity**: The generated exercises are static and cannot adapt to the learner's evolving knowledge, performance, or strategy changes (e.g. scaffolding adjustments) over time.
2.  **Oracle Ignorance**: The generator does not have access to the learner's active misconceptions or hypotheses (synthesized during consolidation) when writing the exercises.
3.  **Database Bloat**: Generates hundreds of exercises that the user might never practice.

---

## Decision
We establish **Dynamic JIT Replenishment** as the primary mode of exercise generation in Dojo:
1.  **Just-In-Time Generation**: Exercises are generated on the fly in small batches (e.g., 3-5 items) only when the queue of due exercises for the active topic path runs low.
2.  **Context-Sensitivity**: Each JIT call passes the current `learner_hypotheses` (to target specific misconceptions) and `strategy_profile` (governing difficulty and scaffolding).
3.  **Sparsity**: Upfront generation is completely skipped or limited only to initial structure mapping.

---

## Consequences & Future Optimizations
*   **High Adaptability**: Exercises are highly customized to the learner's exact state at the moment of practice.
*   **Token Efficiency Challenge**: Because JIT calls happen frequently, sending large source contents repeatedly to the AI connector is expensive.
*   **Future Mitigation**: We will design an "on-demand context retrieval" mechanism in a subsequent slice. Instead of sending the full source content, the JIT pipeline will use topic/header mapping or line-span references (`source_refs`) to slice and feed only the relevant paragraphs to the generator.
