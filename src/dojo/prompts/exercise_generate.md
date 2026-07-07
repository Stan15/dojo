You are drafting practice exercises for one learner. Their time is scarce: every
weak exercise displaces a good one.

TASK: Draft exactly {{ n_items }} exercises for topic "{{ topic_path }}"
at difficulty "{{ difficulty }}".

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
7. Each prompt ≤ 120 words. Never leak the answer via phrasing, option design, or
   answer length.
8. Practice the domain, not meta-learning: never ask the learner to design
   curricula, rubrics, or schedules.

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
      "prompt": "...",       // the exercise, ≤ 120 words, markdown allowed
      "answer": "...",       // ideal answer, ≤ 80 words
      "rubric": "- ...",     // 1-3 scoring criteria
      "skill": "recall|explain|apply|produce|critique"
    }
  ],
  "note": null               // ≤ 25 words, only if you had to deviate (e.g. source too thin)
}
Check before returning: valid JSON; exactly {{ n_items }} items (or fewer + note);
every prompt self-contained; no prompt reveals its answer.
