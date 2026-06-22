Draft practice candidates from the provided source references.
If topic is provided, treat it as an optional parent-topic hint, not a single-topic assertion.
Return candidates that may span multiple subtopics.
If you realize you lack sufficient context about the user's goals, prior knowledge, or learning style for this topic to generate useful, calibrated exercises, or if you determine a pedagogical intervention is needed, you may instead generate 1–3 highly targeted, concise diagnostic questions to help personalize future sessions (set their 'quality' to 'diagnostic').

ADDITIONAL PEDAGOGICAL GUIDELINES:
1. Self-Containment (No Fake Attachments): If no grounding source material is available (source content is empty), you must NOT refer to external or non-existent files, templates, worksheets, or 'checklists below'. Ensure all instructions and tasks are fully self-contained and answerable using only the text inside the prompt.
2. Domain-Specific Practice: Focus practice exercises on active production, retrieval, and application of the target topic domain itself. Unless the target topic path explicitly directs learning about study methodology or planning concepts, avoid plan-reflection or meta-study exercises (such as asking the user to define their own study schedules, targets, or rubrics).
3. Complete Prompt Packaging: The complete body of the exercise (including any sub-tasks, checklist items, options, or context) must be written entirely inside the single string 'prompt' field. Do NOT output custom keys like 'learner_tasks' or 'tasks' for prompt content.

{{ active_topics_context }}
{{ phase_focus_context }}
{{ learner_profile_context }}
{{ schema_instructions }}
