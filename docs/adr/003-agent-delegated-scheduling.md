# ADR 003: Agent-Delegated Scheduling & Dynamic Diagnostics

## Status
Accepted

## Context
We need to support scheduled practice reminders (e.g. daily notifications) and a conversational recall gateway without locking Dojo into a specific platform scheduler (like cron, systemd, or Telegram hooks). Additionally, we must ensure that JIT generation doesn't produce intimidating or miscalibrated exercises when Dojo lacks sufficient context about the user's goals or learning style for a given topic.

---

## Decisions

### 1. Agent-Delegated Scheduling
Dojo will not maintain background service daemons or timer execution loops. Instead:
1.  Dojo exposes a lightweight key-value configuration preference interface (`dojo config set <key> <value>` and `dojo config show`).
2.  Learner preferences (such as `schedule.enabled` and `schedule.daily_time_utc`) are stored internally in a flat `configs` SQLite table.
3.  We delegate scheduling execution to the host agent (e.g., Hermes/OpenClaw). The agent reads the preference parameters from the CLI and registers the actual timer, notification, or messaging jobs within its own execution framework.

### 2. Dynamic Pedagogical Diagnostics
To build a highly calibrated, non-intimidating active learning experience:
1.  **Context Gap Detection:** During JIT exercise generation (`exercise.generate`), if the generator determines it lacks sufficient context about the learner's proficiency, learning style, or goals for a given topic, it is instructed to generate 1–3 highly targeted, concise diagnostic questions instead of practice exercises.
2.  **Diagnostic Classification:** Diagnostic questions are marked with `quality="diagnostic"` and bypass traditional correctness grading (scoring `1.0` automatically upon response submission).
3.  **Consolidation Feedback Loop:** Responses are logged in `Attempt` logs and parsed during periodic profile consolidation (`dojo admin consolidate`), synthesizing user responses directly into stable `LearnerHypothesis` records. These hypotheses then automatically calibrate future exercise generation.

### 3. Detailed Data Flow: From Diagnostic Answers to Learning Plan Calibration

To trace exactly how user responses shape the learner's learning path/plan:

1.  **Trigger & Presentation:** A JIT generation session detects a context gap (e.g., no hypotheses matching the topic, or first-time source ingestion) and yields a question like: *"To tailor your learning of this module, do you prefer writing code snippets from scratch, or explaining high-level concepts?"*
2.  **Response Logging:** The user responds to this question. Dojo captures this in an `Attempt` with `score=1.0`.
3.  **Consolidation & Extraction:** Periodic execution of `dojo admin consolidate` triggers the `profile.consolidate` LLM connector. The prompt receives the user's direct responses. The LLM extracts the learning strategy preference and outputs a hypothesis:
    *   **Key:** `preference.practical_code` (or `goals.career_interview`, `scaffolding.high_support`)
    *   **Description:** *"Learner prefers writing code snippets from scratch rather than text explanations."*
4.  **JIT Prompt Calibration (The Strategy Loop):** On the next JIT candidate generation request:
    *   The active hypothesis list is fetched from the DB.
    *   It is appended to the `learner_profile.active_hypotheses` field in `exercise.generate` request payload.
    *   The generator uses this profile to adjust the exercises it drafts (e.g., generating 80% code-completion tasks and 20% conceptual ones), avoiding unwanted question types.
5.  **Campaign Strategy Adaptation:** The host agent framework or campaign director can inspect these hypotheses and dynamically update the active Campaign's `attack_plan_json` (e.g. shifting the sequence of modules, adjusting difficulty limits, or adding scaffolding phases) to accommodate the user's stated goals.

---

## Consequences
*   **Decoupled Host Integrations:** Dojo remains lightweight and platform-agnostic, serving purely as a local configuration and learning state provider.
*   **Concise Agent Primitives:** Agents (Hermes) only need to follow simple, robust instructions to manage practice schedules without parsing complex internal timers.
*   **Pedagogical Calibration:** Exercises are kept strictly within the learner's zone of proximal development, avoiding user annoyance by executing targeted diagnostic questions only when context gaps or intervention needs are identified.
