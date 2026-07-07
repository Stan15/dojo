# ADR 009: Value Injection (Pseudo-Skill) Prompt Design

## Status
Accepted

## Context
Dojo requires interfacing with Large Language Models (LLMs) to perform JIT exercise generation, diagnostic calibration, and campaign consolidation. 

Traditionally, autonomous agent architectures grant the LLM direct access to execution tools, allowing the model to run CLI commands (e.g., `dojo list-attempts`) or execute terminal scripts in a multi-turn reasoning loop to assemble context and execute changes. 

However, in local-first environments, this approach presents critical design challenges:
1. **Security & Sandbox Escape:** Dojo ingests raw, third-party reference sources. Granting an LLM shell-execution tools exposes the host system to **Indirect Prompt Injection** attacks, where malicious files could hijack the agent loop to execute destructive system commands.
2. **User Disruption:** Local command-line agents (like Claude Code) prompt the user for permission before running any terminal command. A multi-turn command loop would bombard the learner with repetitive "Approve/Deny" gates.
3. **Environment & PATH Dependencies:** Connectors might execute inside Docker containers or isolated environments where Dojo binaries are not locally available.
4. **Latency & Cost:** Multi-turn token loops multiply token consumption and processing times, which degrades local CLI responsiveness.

We need a design that leverages LLM adaptability while ensuring strict security boundaries, low latency, and zero user disruption.

---

## Decisions

### 1. Value Injection Pipeline (Dojo as Host)
The Dojo Python runtime retains absolute control over the execution flow. Instead of giving the LLM tools to pull information, Dojo programmatically queries the workspace state (reading relevant attempts, active campaign insights, configurations, and source outlines), formats this context into a structured markdown block, and injects it directly into the prompt.

### 2. Prompt-as-a-Skill Separation
Prompt templates (e.g., [exercise_generate.md](file:///Users/stans/projects/dojo/src/dojo/prompts/exercise_generate.md)) are declared as self-contained "Skills" in plain Markdown files. They specify the task instructions, pedagogical constraints, and structured output expectations. Dynamic context blocks are represented via simple double-brace placeholders (e.g., `{{ learner_profile_context }}`) and safely interpolated by Dojo at runtime.

### 3. Strict Single-Turn Transactions
The LLM interaction is limited to a single-turn transaction:
1. Dojo compiles the context and renders the prompt template.
2. Dojo invokes the configured connector, transmitting the prompt and expecting a JSON payload.
3. The LLM processes the payload and returns the structured JSON (e.g., candidate exercises or strategy profiles).
4. Dojo's Python runtime parses and validates the JSON schema using Pydantic models, executing all disk writes and state modifications programmatically.

---

## Consequences

*   **Universal Connector Compatibility:** By eliminating local command-calling dependencies, this prompt model functions identically on any LLM connector (remote APIs, local offline models, or third-party CLI agents).
*   **Zero Shell-Injection Risk:** The LLM cannot execute system commands or escape the sandbox because it has no access to shell tools.
*   **Uninterrupted User Experience:** The study and generation loops run silently in the background without triggering security consent prompts in agentic terminal interfaces.
*   **Performance & Low Cost:** Reduces execution latency to a single API call, optimizing token consumption.
*   **Decoupled Prompt Maintenance:** Pedagogical rules and instructions remain isolated in Markdown files, enabling easy template updates without modifying core Python service files.
