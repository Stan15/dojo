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

# --- planning (campaign.plan) ---
PLAN_MAX_TOPICS = 18
PLAN_MAX_TOPIC_DEPTH = 4  # deep enough to EXTEND existing namespaces (music.guitar.fingerstyle.x)
PLAN_MIN_PHASES = 1  # deadline compression may collapse phases; 3-6 is guidance, not a gate
PLAN_MAX_PHASES = 6
PLAN_MISSION_WORDS = 40
PLAN_MAX_QUESTIONS = 3
PLAN_QUESTION_WORDS = 15

# --- routing (capture.route) ---
ROUTE_REASON_WORDS = 12
ROUTE_NEW_NAME_WORDS = 4
ROUTE_NEW_MISSION_WORDS = 15


def word_count(text: str) -> int:
    """Whitespace-token count — the one definition of "word" for every cap."""
    return len(text.split())
