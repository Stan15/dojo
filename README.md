# Dojo: Active Practice for Serious Learners

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/Stan15/dojo)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://python.org)
[![Local First](https://img.shields.io/badge/local--first-100%25-brightgreen.svg)](#design-philosophy)

**Dojo** is a standalone, local-first learning engine that transforms your trusted study materials—notes, articles, books, papers, video transcripts, and projects—into calibrated active recall practice. 

Unlike generic flashcard decks or chat-based AI tutors, Dojo preserves exact source provenance. Every practice prompt it drafts remains bound to the source material it was extracted from, allowing you to trace, audit, and trust your practice.

---

## 🎯 The Core Philosophy

Most AI learning tools start from blank text boxes or generate quiz questions detached from what you actually read. Dojo starts with your trusted sources and operates on a structured lifecycle:

```text
[Source Document] ──> [AI Drafting] ──> [Human Review] ──> [Active Queue] ──> [Calibrated Practice]
       ▲                                                                               │
       └───────────────────────── Provenance Audit & Recall Feedback ──────────────────┘
```

1. **Capture Provenance**: Keep reference coordinates (anchors, line numbers) back to the original source.
2. **Review Before Trust**: AI drafts candidate questions; you audit, edit, or reject them before they become active exercises.
3. **Calibrate and Adapt**: Active recall sessions adjust dynamically based on retrieval latency, scoring accuracy, and forgetting curves.

---

## ⚡ Quick Start (Get practicing in 60 seconds)

### 1. Installation

Dojo runs locally on macOS and Linux.

Run the automated installer script to configure Dojo globally:
```bash
curl -fsSL https://raw.githubusercontent.com/Stan15/dojo/main/install.sh | sh
```
*(For pipx, manual source installations, or local binary compilation, see the [Installation Guide](docs/installation.md).)*


### 2. Connect Your AI Agent

Dojo routes exercise generation and grading through **AI Connectors**. The automated `install` command copies the agent-agnostic practice skills to your assistant AND configures it as Dojo's default AI connector in one go:

```bash
# Connect Hermes
dojo install hermes

# Connect OpenClaw
dojo install openclaw
```

<details>
<summary>⚙️ Custom AI Connectors (Ollama, OpenAI API, custom scripts)</summary>

If you are not using a standard agent or want to configure a custom API connector (e.g. Ollama or a custom shell script), you can register any executable command as a default connector:
```bash
dojo connect ai command local-llm --default -- ~/.local/bin/my-ollama-wrapper
```

Verify your connection:
```bash
dojo connect ai test
```
</details>

---

### 🤖 Auto-Onboarding: Just Tell Your Agent!

If you are using an AI coding assistant (like Hermes, OpenClaw, Claude Code, or Gemini/Claude in the terminal) inside this repository, you don't need to configure things yourself. You can just copy and paste this command into your agent's chat:

> "Please install the Dojo learning system skill, verify the installation, configure a default AI command connector for yourself, and run the smoke tests to make sure everything works."

Because Dojo's CLI supports non-interactive execution and outputs structured JSON envelopes, your agent will read the instructions, call `dojo install` to register the skill, configure the connector, and verify the setup automatically!

---

### 3. Ingest a Source and Draft Candidates

Add raw text, web URLs, or local markdown files. The `--generate` flag calls your connector to draft topic-specific candidates:

```bash
dojo add --text "Calculus: The derivative of f(x) = x^2 is f'(x) = 2x, representing the instantaneous rate of change." \
         --title "Derivatives" \
         --topic "math.calculus" \
         --mission "Master basic calculus rules" \
         --generate
```

### 4. Review & Promote to Active Queue

Inspect the topics extracted from your source, audit draft questions, and promote them to your active learning queue:

```bash
# View candidate count per topic path
dojo source topics src_abcdef12

# Launch the interactive review CLI to accept/reject/edit drafts
dojo source review src_abcdef12
```

### 5. Start a Recall Practice Session

Once candidates are queued, start a practice session. Dojo tracks your response, latency, and correctness:

```bash
# Start a session for 5 active calculus exercises
dojo start --topic "math.calculus" --limit 5

# Reveal the first question
dojo ready

# Submit your answer
dojo answer "2x"
```

---

## 🛠️ CLI Command Reference

| Command | Action | Example |
| :--- | :--- | :--- |
| `dojo add` | Ingests a new study source (file, URL, or raw text) | `dojo add notes.txt --title "My Notes"` |
| `dojo source list` | Lists all ingested sources and candidate counts | `dojo source list` |
| `dojo source review` | Launches interactive review CLI for candidate drafts | `dojo source review <source_id>` |
| `dojo queue` | Bulk-promotes candidates to active exercises | `dojo queue --source <source_id>` |
| `dojo start` | Starts/resumes a practice session | `dojo start --limit 10` |
| `dojo ready` | Reveals the prompt for the active exercise | `dojo ready` |
| `dojo answer` | Submits your answer and records latency/accuracy | `dojo answer "42"` |
| `dojo progress` | Displays your practice dashboard and metrics | `dojo progress` |
| `dojo install` | Installs operator capabilities directly to agents | `dojo install hermes` |

---

## 🤖 AI Assistant Integration (Hermes, OpenClaw, etc.)

If you use autonomous coding or study assistants like **Hermes** or **OpenClaw**, you can register Dojo's capability set directly into their skillsets:

```bash
dojo install hermes
```

This copies the agent-agnostic skill configurations (`skills/dojo/SKILL.md`) to the agent's active environment. Once installed, your agent can programmatically:
*   Automatically queue topics from sources you reference during chat.
*   Draft, edit, and queue high-quality study exercises behind the scenes.
*   Return structured JSON outputs using `--json` mode.

---

## 🛡️ Design Principles

*   **100% Local-First**: Your learning metrics, sqlite database, sources, and configurations reside entirely on your local machine.
*   **Simple by Default, Precise when Needed**: Human-friendly Rich layouts for terminals, alongside stateless `--json` / `--no-input` modes for agents and automation.
*   **Durable Storage Strength**: Leverages spaced retrieval concepts to build durable mental storage strength.

---

## 📚 Further Reading

For architectural insights and product vision, explore:
*   [Product North Star](docs/product-north-star.md) - Vision, provenance, and product stance.
*   [Pedagogical Foundation](docs/pedagogy-foundation.md) - Active recall, spacing, and adaptation.
*   [Development Approach](docs/development-approach.md) - Slicing, architecture seams, and verification.
*   [CLI Design Baseline (Draft)](docs/ramblings-planning-not-authoritative/cli-interface-design.md) - Future-aware CLI design exploration.

