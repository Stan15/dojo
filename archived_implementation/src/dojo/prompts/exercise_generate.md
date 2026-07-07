Draft practice candidates from the provided source references.
If topic is provided, treat it as an optional parent-topic hint, not a single-topic assertion.
Return candidates that may span multiple subtopics.
If you realize you lack sufficient context about the user's goals, prior knowledge, or learning style for this topic to generate useful, calibrated exercises, or if you determine a pedagogical intervention is needed, you may instead generate 1–3 highly targeted, concise diagnostic questions to help personalize future sessions (set their 'quality' to 'diagnostic').

ADDITIONAL PEDAGOGICAL GUIDELINES:
1. Self-Containment: Ensure all instructions, tasks, and questions are fully self-contained. Do not refer to external or non-existent files, worksheets, or checklists. Every exercise must be fully complete and answerable using only the text provided in its prompt.
2. Domain-Specific Practice (No Learner-as-Teacher Tasks): Focus practice exercises on active production, retrieval, and application of the target topic domain itself. Do not ask the learner to perform the teacher's role (e.g. asking them to design their own curriculum, define grading rubrics, or schedule their own practice calendar). It is, however, completely appropriate for the system to ask the student targeted diagnostic or clarifying questions about their learning goals, targets, or prior knowledge at strategic milestones.
3. Complete Prompt Packaging: The complete body of the exercise (including any sub-tasks, checklist items, options, or context) must be written entirely inside the single string 'prompt' field. Do NOT output custom keys like 'learner_tasks' or 'tasks' for prompt content.

{{ active_topics_context }}
{{ phase_focus_context }}
{{ learner_profile_context }}
{{ strategy_context }}
{{ schema_instructions }}
