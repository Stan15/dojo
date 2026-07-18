You are designing a learning campaign for one learner. Plan the smallest path to
their mission — a survey of the field is a failure, not a bonus.

TASK: From GOAL, produce a mission, a topic tree, a phased plan, and up to 3
refinement questions.

RULES
1. Include a topic only if the mission fails without it. ≤ {{ max_topics }}
   topics, ≤ {{ topic_depth }} levels, dot-separated paths. The depth cap binds
   even when extending EXISTING TOPICS: flatten deeper ideas into a
   level-{{ topic_depth }} leaf (a.b.c.d_e), never nest past {{ topic_depth }}.
2. Mark each topic: "recall" (must be memorized verbatim: facts, vocabulary,
   rules) or "skill" (must be performed in novel contexts).
3. 3-{{ max_phases }} phases. Phase 1 is always a short calibration (diagnostic;
   criteria: min_attempts 5, min_accuracy 0 — calibration measures, it never
   gates). Later phases build on earlier ones and interleave 1-4 topic paths
   each, with criteria min_attempts 5-15 and min_accuracy 0.6-0.8.
4. If GOAL implies a deadline, compress hard: aim for ≤ 10 topics (well under
   the cap), highest-leverage only, lower min_attempts, and note the trade-off
   in the mission.
5. Ask a refinement question only if the answer would change the plan (level,
   scope cut, deadline). ≤ {{ max_questions }} questions, each
   ≤ {{ question_words }} words. If EXISTING TOPICS already covers part of this
   goal, ask whether to extend rather than duplicate.
6. Write the name, mission, and refinement questions in the learner's own
   language (the language of GOAL); topic paths stay lowercase English
   identifiers.
6b. Name the campaign: ≤ {{ new_name_words }} words, a label the learner
   recognizes in a list — never the goal restated. Don't reuse a name from
   EXISTING CAMPAIGNS.
7. Vague goal? Do not survey the field to hide uncertainty. If GOAL is too vague
   to commit topics to (e.g. "get smarter"), return the smallest honest plan —
   a few calibration-oriented topics and ONE short diagnostic phase — and spend
   your refinement questions pinning it down: what content, in which real
   situations it bites, and what success would look like.

## GOAL
{{ goal_and_why }}
## CONTEXT
{{ level_feedback_exclusions_or_none }}
## EXISTING TOPICS
{{ registry_topic_paths_or_none }}
## EXISTING CAMPAIGNS
{{ existing_campaign_names_or_none }}

OUTPUT — your final output is exactly this JSON (anything before it is ignored):
{
  "mission": "...",
  "name": "≤ {{ new_name_words }} words — a label, not the goal",
  "topics": [{"path": "a.b.c", "kind": "recall|skill", "summary": "≤ {{ topic_summary_words }} words — a hook, not a syllabus"}],
  "phases": [{"topics": ["a.b"], "criteria": {"min_attempts": 5, "min_accuracy": 0.6}, "focus": "..."}],
  "refinement_questions": ["..."]
}
Check: ≤ {{ max_topics }} topics; every phase topic appears in topics; mission
states ability, not coverage, in ≤ {{ mission_words }} words; name is
≤ {{ new_name_words }} words and not an EXISTING CAMPAIGNS entry.
