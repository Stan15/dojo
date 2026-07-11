"""Numeric limits shared by prompt templates and result validators.

Every limit a prompt promises ("≤ 40 words", "max 2 new insights") must be
enforced by a Pydantic validator, and tests assert the two never drift
(design/prompts.md §9.2). This module is the single source both sides read.

Word caps are validated as caps on *whitespace-separated tokens* — crude but
deterministic and model-fair (no tokenizer dependence).
"""
from __future__ import annotations

# --- generation (exercise.generate / exercise_diagnostic) ---
GENERATE_PROMPT_WORDS = 120
DIAGNOSTIC_PROMPT_WORDS = 40
GENERATE_ANSWER_WORDS = 80
GENERATE_NOTE_WORDS = 25
GENERATE_MAX_ITEMS = 8  # absolute list bound; exact count per task checked by the applier

# --- meta-learning intervention (exercise.generate escape hatch) ---
INTERVENTION_MAX_QUESTIONS = 3
INTERVENTION_QUESTION_WORDS = 25
INTERVENTION_REASON_WORDS = 25

# --- grading (attempt.grade) ---
GRADE_BANDS = (0.0, 0.3, 0.7, 1.0)
GRADE_EVIDENCE_WORDS = 10
GRADE_FEEDBACK_WORDS = 40
GRADE_ERROR_TAG_WORDS = 4

# --- reflection (campaign.reflect) ---
REFLECT_MAX_NEW_INSIGHTS = 2
REFLECT_INSIGHT_WORDS = 25
REFLECT_REASON_WORDS = 20
REFLECT_JOURNAL_WORDS = 30
REFLECT_MAX_QUESTIONS = 2  # ask-don't-restructure channel (change authority)
REFLECT_QUESTION_WORDS = 25
REFLECT_MAX_RETIREMENTS = 2  # care-exit channel (ADR 017 §6)

# --- planning (campaign.plan) ---
PLAN_MAX_TOPICS = 18
PLAN_MAX_TOPIC_DEPTH = 4  # deep enough to EXTEND existing namespaces (music.guitar.fingerstyle.x)
PLAN_MIN_PHASES = 1  # deadline compression may collapse phases; 3-6 is guidance, not a gate
PLAN_MAX_PHASES = 6
PLAN_MISSION_WORDS = 40
PLAN_TOPIC_SUMMARY_WORDS = 18  # plan responses were the token-fattest output (audit 2026-07-10)
PLAN_MAX_QUESTIONS = 3
PLAN_QUESTION_WORDS = 15

# --- routing (capture.route) ---
ROUTE_REASON_WORDS = 12
ROUTE_NEW_NAME_WORDS = 4
ROUTE_NEW_MISSION_WORDS = 15

# --- task traces (provenance, owner decision 2026-07-09) ---
# Raw submissions are kept TAIL-first: harness CLIs echo the prompt before
# the answer, so the head duplicates the stored payload while the answer and
# its surrounding reasoning live at the end.
TASK_TRACE_CLIP_BYTES = 8 * 1024


def word_count(text: str) -> int:
    """Whitespace-token count — the one definition of "word" for every cap."""
    return len(text.split())


# Every VALIDATOR-ENFORCED cap a fulfiller can trip, per task kind, under the
# placeholder name its template interpolates (owner decision 2026-07-09: the
# template states exactly the limits it needs, values injected from here — a
# number can never go stale, and tests/test_prompts.py fails any template
# missing one of its declared placeholders, so a floor can never go unstated).
# Guidance numbers (e.g. "aim for ≤ 10 topics under deadline") stay literal
# prose: they are pedagogy, not gates.
TEMPLATE_CAPS: dict[str, dict[str, int]] = {
    "exercise.generate": {
        "prompt_words": GENERATE_PROMPT_WORDS,
        "answer_words": GENERATE_ANSWER_WORDS,
        "note_words": GENERATE_NOTE_WORDS,
        "intervention_max_questions": INTERVENTION_MAX_QUESTIONS,
        "intervention_question_words": INTERVENTION_QUESTION_WORDS,
        "intervention_reason_words": INTERVENTION_REASON_WORDS,
    },
    "exercise.diagnostic": {
        "diagnostic_prompt_words": DIAGNOSTIC_PROMPT_WORDS,
    },
    "attempt.grade": {
        "evidence_words": GRADE_EVIDENCE_WORDS,
        "feedback_words": GRADE_FEEDBACK_WORDS,
        "error_tag_words": GRADE_ERROR_TAG_WORDS,
    },
    "campaign.reflect": {
        "max_new_insights": REFLECT_MAX_NEW_INSIGHTS,
        "insight_words": REFLECT_INSIGHT_WORDS,
        "reason_words": REFLECT_REASON_WORDS,
        "journal_words": REFLECT_JOURNAL_WORDS,
        "max_questions": REFLECT_MAX_QUESTIONS,
        "question_words": REFLECT_QUESTION_WORDS,
        "max_retirements": REFLECT_MAX_RETIREMENTS,
        "topic_depth": PLAN_MAX_TOPIC_DEPTH,  # new phase topics (apply_reflect hygiene)
    },
    "campaign.plan": {
        "max_topics": PLAN_MAX_TOPICS,
        "topic_depth": PLAN_MAX_TOPIC_DEPTH,
        "max_phases": PLAN_MAX_PHASES,
        "max_questions": PLAN_MAX_QUESTIONS,
        "question_words": PLAN_QUESTION_WORDS,
        "mission_words": PLAN_MISSION_WORDS,
        "topic_summary_words": PLAN_TOPIC_SUMMARY_WORDS,
    },
    "capture.route": {
        "reason_words": ROUTE_REASON_WORDS,
        "new_name_words": ROUTE_NEW_NAME_WORDS,
        "new_mission_words": ROUTE_NEW_MISSION_WORDS,
    },
    "goal.route": {
        "reason_words": ROUTE_REASON_WORDS,
        "new_name_words": ROUTE_NEW_NAME_WORDS,
        "new_mission_words": ROUTE_NEW_MISSION_WORDS,
    },
}
