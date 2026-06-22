# ADR 005: Hybrid Execution & Perpetual Maintenance Phases

## Status
Accepted

## Context
As campaigns reach completion, we need a clean mechanism to transition the learner's study topics into a long-term "maintenance" review pool without:
1.  **Ballooning Code Complexity:** Creating entirely distinct database schema structures or parallel Python execution pipelines for learning vs. maintaining.
2.  **Unnecessary LLM Overhead:** Making expensive, slow AI connector requests for simple, static fact recall or offline vocabulary practice.
3.  **Miscalibrated Maintenance:** Bombarding the user with atomic concept drills once they have already mastered the macro-level skill (e.g. practicing basic addition instead of solving complex formulas).

---

## Decisions

### 1. Maintenance as a Perpetual Plan Phase
Dojo will represent campaign completion and maintenance as a structured, dynamic phase revision managed through the Pedagogical Journal. 
*   When all active curriculum phases are passed, the consolidator LLM (`dojo admin consolidate`) logs a `"COMPLETE"` action and appends a perpetual **Maintenance Phase** to the `attack_plan_json`.
*   The consolidator updates the campaign's `strategy_profile` to set `scaffolding = "low"` and `difficulty = "advanced"`. This instructs the JIT generator to target macro-level combined skills rather than atomic drills.

### 2. Hybrid Execution (Deterministic Engine vs. Flexible Planner)
We divide execution strictly between Python code and the LLM connector based on the phase `type` registered in the attack plan:
1.  **`type: "recall"` (Static / Fact Recall)**:
    *   **Execution:** 100% deterministic Python. Python reads the active topic and serves existing, cached exercise IDs from the database using spaced repetition intervals.
    *   **Resilience:** Runs completely offline with **zero LLM calls**, ensuring the user can always practice core facts.
2.  **`type: "practice"` (Procedural / Generative Skills)**:
    *   **Execution:** Hybrid. Python manages session state and limits; the default AI connector is called JIT to generate fresh, novel questions based on active topics and the strategy profile.
3.  **`type: "diagnostic"` (Calibration)**:
    *   **Execution:** Hybrid. The AI connector is called to ask targeted onboarding questions, and Python automatically scores the responses as `1.0` and consolidates them.

### 3. Practice Styles on Phase Definitions
Phases in the attack plan will support a `practice_style` property to govern item reuse:
*   `practice_style: "static-recall"`: The JIT queue reuse existing database exercise records, scheduling exact repetitions to cement storage strength.
*   `practice_style: "generative-novelty"`: The JIT generator drafts novel, alternative questions to test skill application across fresh contexts.

---

## Consequences
*   **Offline Resilience:** Vocabulary and fact revision remain fully operational during internet or AI provider outages.
*   **Schema Consistency:** Unified campaign schema remains unchanged; the entire learner flow is governed by the state of the active `attack_plan_json` phase.
*   **Minimal Code Footprint:** Avoids branching state paths in the Python controller, utilizing the phase definition structure as the single source of truth.
