---
name: dojo
description: Guidance on using the Dojo Learning System CLI to ingest notes, manage candidate exercises, and run practice recall sessions.
---

# Dojo Learning System Skill

This skill allows the agent to interact with the Dojo Learning System CLI, enabling it to ingest notes, manage exercises, and run study sessions.

## Overview of CLI Commands

All commands support the `--json` flag to return structured JSON envelopes, and should be run with `--json` in agent/non-interactive environments.

### 1. Ingesting Sources & Generating Candidates
To add a text source and automatically generate practice candidates:
```bash
dojo add --text "Calculus notes here." --title "Calculus" --topic "math.calculus" --mission "Learn derivatives" --generate
```
*   `--generate`: Triggers exercise candidate drafting via the configured AI connector.
*   Outputs a JSON object containing the `source_id` (e.g., `src_abcdef12`).

### 2. Inspecting Candidates
*   **List Topics:** List inferred topics and candidate counts for a source:
    ```bash
    dojo source topics <source-id>
    ```
*   **List Candidates:** List all candidate drafts for a source, optionally filtered by topic:
    ```bash
    dojo source candidates <source-id> [--topic <topic>]
    ```

### 3. Queueing/Promoting Candidates
*   **Bulk Queue:** Promote candidate drafts matching a topic from a source to active exercises:
    ```bash
    dojo queue --source <source-id> [--topic <topic>] [--limit <limit>]
    ```
*   **Queue by ID:** Promote a single candidate to active exercise:
    ```bash
    dojo queue <candidate-id>
    ```

### 4. Running Practice Sessions
*   **Start Session:** Open or resume a practice session (returns `session_id`):
    ```bash
    dojo start [--topic <topic>] [--limit <limit>]
    ```
*   **Reveal Prompt:** Get the active prompt and start the timer (run with `--json` or `--no-input` to avoid TTY block):
    ```bash
    dojo ready [--session <session-id>]
    ```
*   **Answer Prompt:** Submit the answer to the active prompt. Calculates latency and evaluates correctness:
    ```bash
    dojo answer <user-answer> [--session <session-id>]
    ```
*   **Progress Dashboard:** List recall latency, accuracy, and recent attempts:
    ```bash
    dojo progress
    ```
