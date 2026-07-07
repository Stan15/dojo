# ADR 004: Campaign-Scoped Calibration & Feedback

## Status
Accepted

## Context
As Dojo expands to support multiple active campaigns interleaved within a single practice session, we need a way to personalize practice and process user feedback without:
1.  **Context Drift & LLM Bloat:** Storing a global, cross-campaign LLM-managed learner style profile that grows bloated and contradictory over time.
2.  **Calibration Ambiguity:** Misrouting feedback or performance metrics when campaigns target overlapping topic paths (e.g. Git Basics vs. Git Advanced).
3.  **Janky Interfaces:** Forcing agents or users to manually specify keys, tags, or campaign IDs when providing natural language feedback.

---

## Decisions

### 1. Campaign-Scoped Calibration
All personalization state, goals, and scaffolding parameters are stored campaign-locally. Dojo does not maintain a global, cross-campaign LLM learner profile.

### 2. Consolidator-Led Strategy (Reflection)
The consolidator (now renamed to "Reflection", CLI: `dojo reflect`) owns pedagogical planning. It analyzes attempts and feedback, refines the Campaign's `mission`, updates its `strategy_profile` (mode, difficulty, scaffolding), and writes transient insights. The JIT generator is a pure executor, following the Campaign's strategy profile.

To prevent slow-developing mistake patterns (e.g., repeating a specific error once every three sessions) from being discarded as isolated slips, the reflection engine implements a **two-tiered memory model**:
*   **Short-term working context**: The LLM is fed all *unreflected* attempts along with a *sliding window of recent history* (e.g., the last 15–20 attempts, regardless of whether they have already been consolidated). This allows cross-session pattern recognition of slow-occurring trends.
*   **Long-term active state**: The list of persistent, active `Insights` is fed into every reflection run. The LLM can confirm, refine, resolve, or append new evidence to these persistent insights rather than creating duplicates.

### 3. "Raw-to-Refined" Feedback via `LearnerHypothesis`
Natural-language user feedback logged via `dojo feedback "<comment>"` is saved in the `LearnerHypothesis` table with key `feedback.user.<uuid>`, the campaign's `topic_path`, and `status="active"`. 
*   **Immediate Effect:** The JIT generator reads it on the next run to tailor exercises.
*   **Consolidation:** The consolidator LLM synthesizes it into structured hypotheses later and marks the raw feedback hypothesis as resolved.

### 4. Campaign ID on `Attempt` Table
We add a nullable `campaign_id` foreign key to the `Attempt` table. This maps every exercise attempt unambiguously to the campaign that requested it, enabling precise calibration in interleaved sessions.

---

## Consequences
*   **Encapsulation:** All learning state remains isolated, preventing cross-topic contamination and prompt context bloat.
*   **Zero Heuristics:** Dojo core avoids complex, rigid Python heuristics, letting the consolidator LLM make smart, structured planning updates.
*   **Zero User Friction:** Users can comment naturally (e.g. `dojo feedback "Too easy"`), and Dojo automatically resolves the campaign context based on the user's last attempt.
*   **Precise Calibration:** Overlapping topics are calibrated independently.
