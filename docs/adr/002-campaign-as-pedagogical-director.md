# ADR 002: Campaign as Pedagogical Director of the JIT Pipeline

## Status
Proposed

## Context
In ADR 001, we resolved the tension between factual sources and syllabi by establishing a topic-centric registry where:
1.  `Source` documents attach as grounding evidence to Topic nodes.
2.  `Campaign` progression represents traversal paths through those Topic nodes.

However, we need a way to coordinate this JIT generation pipeline under a consolidated learning plan or strategy (e.g., deciding the difficulty, scaffolding rules, spacing, and application depth of generated items). If the JIT generator simply queries topic nodes in isolation, the resulting exercises will be disjointed and fail to respect the learner's broader progression goals.

---

## Decision
We establish the `Campaign` table as the **Pedagogical Director** of the generation pipeline. 

A Campaign stores two key execution structures in its schema:
1.  **The Attack Plan (Syllabus):** A sequenced progression of phases, where each phase maps to a set of topic paths and specifies completion criteria (e.g. accuracy metrics).
2.  **The Strategy Profile:** Configuration parameters governing JIT generation execution (e.g., target depth, novelty ratios, and scaffolding level).

### Pipeline Execution Flow
During JIT replenishment, Dojo executes the following pipeline:
1.  **Inspect Active Campaign Progress:** Reads the syllabus to identify the active phase's target topics.
2.  **Read Strategy Parameters:** Extracts the campaign's target depth (conceptual vs. procedural), novelty threshold, and scaffolding constraints.
3.  **Collect Grounding Snippets:** Scans the `Source` table for text spans associated with the active topic paths.
4.  **Extract Active Misconceptions:** Queries the `learner_hypotheses` table for active patterns matching the active topics.
5.  **Compile unified Task Request:** Bundles the factual source text, target topic, active misconceptions, and strategy instructions, then dispatches the request to the default AI connector (`exercise.generate`).

---

## Consequences
*   **Decoupled & Flexible Content:** Factual content remains independent of the campaign sequence. Multiple campaigns (e.g., a "Quick Review" campaign vs. a "Deep Mastery" campaign) can target the same sources but generate completely different exercises by utilizing different Strategy Profiles.
*   **Structured Progression:** Tracking campaign state is clean and simple via the database (`active_phase_index`), eliminating the need to parse raw text syllabi during execution.
*   **Targeted Calibration:** AI prompts are highly focused, leading to less hallucination and better-calibrated challenges in the learner's zone of proximal development (ZPD).
