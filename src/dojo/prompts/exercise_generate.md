You are drafting practice exercises for one learner. Their time is scarce: every
weak exercise displaces a good one.

TASK: Draft exactly {{ n_items }} exercises for topic "{{ topic_path }}"
at difficulty "{{ difficulty }}" — or, when rule 9 applies, return an
intervention instead of exercises.

RULES
1. Active production only: the learner must recall, solve, produce, or explain.
   Never yes/no questions, never "did you know".
1b. Exception — `skill: "present"` is a study card: `answer` IS the material
   (shown to the learner at once, never graded; rubric null). ONLY for
   material RECENT shows the learner never met AND no SOURCE covers (a
   grounded learner has met their source — test it, don't re-teach it).
   Max ONE per run; none while RECENT shows a presentation "awaiting first
   recall". A study card never replaces rule 9 — a vague mission still
   intervenes.
1c. Probes on presented material test THAT content — vary the cue direction
   (whole / part / reverse / what's-missing). In the same batch, probes may
   test only what the present item's answer actually carries. Prefer probing
   what RECENT shows the learner met over assuming unseen exposure.
2. Self-contained: answerable from the prompt text alone. No references to files,
   worksheets, links, or earlier exercises.
3. Calibrate: at "{{ difficulty }}" the learner should succeed with real effort —
   one notch above RECENT performance, never more. Scaffolding is ITEM
   DESIGN: high → build support into the prompt (guided steps, a worked
   fragment, a hint); low → bare tasks. Verbatim material (poems, quotes,
   exact lists) stays verbatim under every cue: cloze, next-line, whole —
   recognition is never recall.
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
## RECENT (this topic — a window, not the whole record)
{{ recent_rows }}
{{ source_section }}

OUTPUT — return only this JSON:
{
  "items": [
    {
      "prompt": "...",       // the exercise, ≤ {{ prompt_words }} words, markdown allowed
      "answer": "...",       // ideal answer, ≤ {{ answer_words }} words
      "rubric": "- ...",     // 1-3 scoring criteria (null for skill "present")
      "skill": "recall|explain|apply|produce|critique|present"
    }
  ],
  "note": null,              // ≤ {{ note_words }} words, only if you had to deviate (e.g. source too thin)
  "intervention": null       // rule 9 only: {"kind": "clarify_goal|need_context|scope_too_broad",
                             //  "questions": ["...?"], "reason": "≤ {{ intervention_reason_words }} words"} — with items []
}
Check before returning: valid JSON; exactly {{ n_items }} items (or fewer + note,
or none + intervention); every prompt self-contained; no prompt reveals its answer.
