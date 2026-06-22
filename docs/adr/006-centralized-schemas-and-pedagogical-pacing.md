# ADR 006: Centralized Pydantic Schemas and Pacing-Aware Campaign Consolidation

## Status
Accepted

## Context
When JIT replenishment or campaign profile consolidation runs, external AI models receive prompts to draft exercises or build/adjust syllabi. 
Previously:
1. System prompts lacked a strict output JSON schema contract, leading to LLMs producing rich interactive fields (like `learner_tasks` or `checklist` arrays) that the core library parsed out and discarded, resulting in broken prompts.
2. The consolidation engine enforced rigid rules (such as requiring a specific phase structure) rather than domain-agnostic, generic pedagogical guidelines.
3. There was no clean way to calibrate campaign progression and syllabus density to a user's tight target timeline or deadline, causing long, multi-phase syllabi to be generated for short-term targets.

## Decisions
We make the following design and architectural changes:

1. **Centralized Pydantic Schemas**:
   - Define all LLM response payload schemas as standard Pydantic v2 `BaseModel` classes in `src/dojo/schemas.py`.
   - Utilize Pydantic's `Field(description="...")` to document every field's purpose, optionality, and execution rules.
   - Inject the schema into task requests by serializing it to a standard JSON Schema string (`.model_json_schema()`), providing a clear contract for the model.
   - Mandate a `"thinking"` reasoning key in all schema outputs. This acts as a sandbox for LLM pacing and pedagogical planning before writing structured outputs, preventing raw thought pollution in core database columns.

2. **Temporal and Pacing-Aware Consolidation**:
   - Write campaign consolidation prompts in a fully domain-agnostic, generic style.
   - Guide the LLM to inspect the user's self-stated timeline constraints (e.g. exams, milestones, availability). If a near-term target is found, it must dynamically compress the syllabus phases to focus on high-yield active topics and lower completion criteria (`min_attempts`) to fit the time horizon.

3. **Parser Fallback Packaging**:
   - Enhance the candidate parser in `src/dojo/generate.py` to recursively traverse and extract stray structural keys (such as `learner_tasks`, `checklist`, `questions`, or `scaffolding`).
   - If they exist, format and append them to the main `prompt` body in clean Markdown to prevent prompt data loss during LLM output drift.

4. **Preserved Thinking Blocks**:
   - The `"thinking"` reasoning logs remain fully preserved in the `raw_output` column of the `generation_runs` table for auditing and debugging.

## Consequences
- **Robustness**: Any minor LLM output format drift (such as using checklists instead of prompts) is recovered gracefully, preventing broken exercises.
- **Pedagogical Alignment**: Syllabi are dynamically paced. Under tight timelines, Dojo behaves as a targeted crash-course engine; for long-term targets, it builds progression roadmaps for durable storage strength.
- **Maintainability**: Core system prompts are completely generic and focused on structural boundaries, whereas niche-specific execution is guided by the input payload data.
