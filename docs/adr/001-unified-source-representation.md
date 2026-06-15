# ADR 001: Unified Source Representation (Factual Material vs. Learning Plan)

## Status
Accepted

## Context
Dojo must support two core modes of learning:
1.  **Material-Grounded Learning:** The user provides raw reference notes, textbook chapters, or codebase files, and wants to practice active recall on the specific facts contained within.
2.  **Goal-Oriented Learning:** The user provides a high-level syllabus, study roadmap, or target goal (e.g., "Master Python lists in 5 days") and wants Dojo to guide their study progression.

This introduces a tension in how we represent these inputs in the database and the JIT generation pipeline:
*   **Option 1: Overloaded Sources (Unified Table).** Treat syllabi/roadmaps and factual notes both as `Source` records. JIT generation must dynamically infer the type of source to decide whether to extract facts or synthesize questions.
*   **Option 2: Separated Entities (`Source` vs. `LearningPlan`/`Campaign`).** Store raw factual material in `Source`, and structured outlines/sequencing in a separate `LearningPlan` or `Campaign` table. This keeps the schema clean but increases cognitive friction, database complexity, and API surface.

---

## Evaluation of Options

### Option 1: Overloaded Sources
*   *Pros:* Minimal schema surface. One command (`dojo add`) covers all inputs.
*   *Cons:* Difficult to track campaign execution state (e.g. "which topic is active?") inside raw text. Increased prompt engineering complexity for the AI connector.

### Option 2: Separated Entities
*   *Pros:* High separation of concerns. Easy to query and track active study progress.
*   *Cons:* If a user adds a textbook chapter that contains *both* a chapter syllabus and factual sections, they are forced to split the document or register it twice under different concepts.

---

## Resolution: Resolving the False Dichotomy (Hierarchy as Curriculum)

The tension between "Factual Reference" and "Learning Plan" is a **false dichotomy**. 
*   A **Factual Reference** is just a learning plan with rich textual body sections.
*   A **Learning Plan / Syllabus** is just a factual reference document with empty or summarized body sections.

Both share the exact same structural property: **a hierarchical outline of headings and subheadings mapping to topic paths.**

### The Unified Architecture
We resolve the tension by treating every `Source` as a hierarchical document structured around topic nodes:

```text
       Source Document
              │
      ┌───────┴───────┐
   [Heading]      [Heading]   <── Topic Paths (e.g., python.lists)
      │               │
  [Content]       [Content]   <── Factual Paragraphs OR High-Level Goals
```

*   **Extract-Based Generation (Factual):** If a topic node contains rich factual content, the JIT pipeline instructs the AI connector to extract and draft exercises strictly from the provided text.
*   **Synthetic-Based Generation (Goal-Driven):** If a topic node contains only a high-level goal, summary, or syllabus description, the JIT pipeline instructs the AI connector to synthesize practice exercises using its general knowledge.
*   **Campaign Sequencing:** A `Campaign` represents the active execution of a learning plan. Rather than duplicating content, a `Campaign` simply points to a `Source` (or a subset of a Source's topic paths) and tracks the `active_phase_index` indicating which topic heading the learner is currently practicing.

## Consequences
*   **Simplicity:** Keeps the database schema lightweight. The `Source` table remains the single repository for all user-provided materials, outlines, and roadmaps.
*   **Flexibility:** JIT generation works uniformly. It reads the source outline, evaluates the content density under the target topic, and decides whether to extract (grounded) or synthesize (general knowledge) candidates.
*   **Resiliency:** Campaign state is decoupled from the content itself. If the user updates the source syllabus text, the campaign's topic pointers remain intact.
