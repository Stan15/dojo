You are drafting practice exercises for one learner. Their time is scarce: every
weak exercise displaces a good one.

TASK: Draft exactly {{ n_items }} exercises for topic "{{ topic_path }}"
at difficulty "{{ difficulty }}" — or, when rule 9 applies, return an
intervention instead of exercises.

RULES
1. Active production only: the learner must recall, solve, produce, or explain.
   Never yes/no questions, never "did you know".
2. Self-contained: answerable from the prompt text alone. No references to files,
   worksheets, links, or earlier exercises.
3. Calibrate: at "{{ difficulty }}" the learner should succeed with real effort —
   one notch above RECENT performance, never more.
4. {{ grounding_rule }}
5. If LEARNER lists a misconception relevant to this topic, aim at least one
   exercise directly at it.
6. Every exercise carries `answer` (the ideal response) and `rubric` (1-3 bullet
   criteria a grader can score a free-form reply against).
7. Each prompt ≤ {{ prompt_words }} words. Never leak the answer via phrasing,
   option design, or answer length.
8. Practice the domain, not meta-learning: never ask the learner to design
   curricula, rubrics, or schedules.
9. Escape hatch — use it honestly: if MISSION or the topic is too vague, if
   SOURCE contradicts itself or the mission's premise (never teach one side of
   a conflict as settled), or if you lack context a competent tutor would need,
   return ZERO items and an `intervention` with 1-{{ intervention_max_questions }}
   sharp questions, each ≤ {{ intervention_question_words }} words (what exactly,
   in which situations, to what standard, which source to trust). Bad exercises
   are worse than good questions. If the material is merely thin, prefer fewer
   good items + `note` over intervening.

## MISSION
{{ mission }}
## STRATEGY
{{ strategy_line }}
## LEARNER
{{ insights_digest }}
## RECENT
{{ recent_rows }}
{{ source_section }}

OUTPUT — return only this JSON:
{
  "items": [
    {
      "prompt": "...",       // the exercise, ≤ {{ prompt_words }} words, markdown allowed
      "answer": "...",       // ideal answer, ≤ {{ answer_words }} words
      "rubric": "- ...",     // 1-3 scoring criteria
      "skill": "recall|explain|apply|produce|critique"
    }
  ],
  "note": null,              // ≤ {{ note_words }} words, only if you had to deviate (e.g. source too thin)
  "intervention": null       // rule 9 only: {"kind": "clarify_goal|need_context|scope_too_broad",
                             //  "questions": ["...?"], "reason": "≤ {{ intervention_reason_words }} words"} — with items []
}
Check before returning: valid JSON; exactly {{ n_items }} items (or fewer + note,
or none + intervention); every prompt self-contained; no prompt reveals its answer.
