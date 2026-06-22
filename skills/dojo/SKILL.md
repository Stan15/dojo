---
name: dojo
description: "Use Dojo for learning/training/studying knowledge: ingest notes, create learning campaigns, generate/practice candidate exercises, and run active recall sessions. Trigger on phrases like 'I want to learn X', 'help me study X', 'quiz me', 'practice recall', 'train on X', or 'give me exercises' when the context is knowledge/learning rather than physical fitness."
owner: github.com/Stan15/dojo
---

# Dojo Learning System Skill

Dojo is a local-first active practice and learning engine (incorporating candidate generation, review queueing, practice sessions, recall scoring, and automatic profile consolidation). The agent interacts with Dojo entirely by executing standard CLI commands (passing `--json` to receive structured JSON output).

## Trigger / Recognition Rules

Use this skill when the user asks to:
*   Learn, study, train, drill, quiz, review, memorize, or practice recall on a knowledge topic.
*   Get practice exercises, questions, or flashcards for a subject.
*   Create a learning plan, syllabus, or study campaign.
*   Turn raw notes, text, files, or URLs into practice material.

**Proactive Suggestion Guidance:**
*   If the user says *"I want to learn X"* or *"help me study X"*, suggest:
    *"I can set this up as a Dojo learning campaign and generate practice exercises. Would you like me to plan it?"*
    Then run `dojo campaign plan "X" --json` to get the syllabus and refinement questions.
*   If the user says *"train"* or *"give me exercises"* without clear context:
    *   If the recent conversation involves Dojo, programming, reading, or learning tools, assume Dojo.
    *   Otherwise ask: *"Do you mean Dojo learning practice exercises, or a physical workout?"*


## Goal-Oriented Campaign Ingestion

When the user asks to study a new topic or goal without providing raw text/files (e.g. "I want to learn Docker Compose" or "help me improve my memory"), follow this two-step collaborative protocol to plan and launch their campaign:

1. **Plan Proposal:**
   Run `dojo campaign plan "<goal>" --json`.
   * Extract the returned proposed syllabus and the list of `refinement_questions`.
   * Present the syllabus outline to the user and ask them the refinement questions (e.g., to confirm scope, target level, or specific exclusions).
   * Note: Dojo automatically checks existing topic trees and formats them for consolidation, preventing namespace duplicates.

2. **Finalize & Create:**
   Once the user replies with their preferences:
   * Run `dojo campaign create "<goal>" --level "<beginner|intermediate|advanced>" --feedback "<user refinements>" --json` (optionally pass `--exclude "<exclusions>"` and `--name "<override-name>"` if relevant).
   * Confirm the successful creation of the campaign to the user and show them the final attack plan phases.
   * Start practicing immediately by launching the practice loop!

## The Core Active Practice Loop

When the user requests to start a study session or when a scheduled practice timer triggers, follow this step-by-step protocol:

1. **Initialize the Session:**
   Run `dojo start --json` (optionally pass `--topic <path>` if a specific topic or campaign was requested).
   * Extract the returned `session_id` and the total number of exercises.
   * Note: Dojo automatically consolidates the learner's profile under the hood during this initialization call to ensure strategies and difficulty are calibrated.

2. **Present Exercises Iteratively:**
   For each exercise in the session:
   * **Get Prompt:** Run `dojo ready --session <session-id> --json`.
   * **Deliver Prompt:** Present the returned `prompt` text verbatim to the user.
   * **Wait for Reply:** Stop and wait for the user's response. Do NOT make any tool calls until the user replies.
   * **Submit Response:** Run `dojo answer "<user-response>" --session <session-id> --json`.
   * **Report Grade:** Inform the user if they were correct (`score == 1.0`). If incorrect, display the correct answer.
   * **Loop Check:** Check `is_session_completed`. If `true`, break the loop.

3. **Show Progress:**
   Announce session completion and run `dojo progress` to print the learner's accuracy and latency metrics.

## Progressive Help & Discoverability

All Dojo commands are fully self-documenting. Rather than memorizing advanced rules, parameters, and flags, the agent **MUST** run `dojo <command> --help` to dynamically retrieve parameters and guidelines whenever the user asks to perform advanced operations:

* **Scheduling:** Run `dojo config --help` to see configuration preferences (e.g. `schedule.enabled`, `schedule.daily_time_utc`). To register recurring practice reminders, use the host agent's scheduler or task registration tool (e.g. via the agent's cron command, background scheduler, or system cron) to trigger this practice loop.
* **Skips:** Run `dojo skip --help` to skip an active exercise with a specific reason.
* **Corrections:** Run `dojo correct --help` to override incorrect scoring on the last attempt.
* **Feedback:** Run `dojo feedback --help` to log specific or general learning feedback.
* **Ingestion:** Run `dojo add --help` to ingest new text files or notes and generate candidates.
* **Review:** Run `dojo source --help` or `dojo queue --help` to review and promote candidate exercises.
