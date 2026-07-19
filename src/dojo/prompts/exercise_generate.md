You are drafting practice exercises for one learner. Their time is scarce: every
weak exercise displaces a good one.

TASK: Draft exactly {{ n_items }} exercises for topic "{{ topic_path }}"
at difficulty "{{ difficulty }}" — or, when rule 9 applies, return an
intervention instead of exercises.

RULES
1. Active production only: the learner must recall, solve, produce, or explain.
   Never yes/no questions, never "did you know". Anchor prompts in MISSION's
   real situations whenever the topic allows.
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
{{ encounter_rule }}
2. Self-contained: answerable from the prompt text alone. No references to files,
   worksheets, links, or earlier exercises.
3. {{ calibration_rule }} Scaffolding is ITEM
   DESIGN: high → build support into the prompt (guided steps, a worked
   fragment of a DIFFERENT example, a hint) — support shows the method,
   never the answer the item asks for; low → bare tasks. At "beginner", one decision or one
   short production per item — never multi-part prompts, never open-ended
   composition. Verbatim material (poems, quotes,
   exact lists) stays verbatim under every cue: cloze, next-line, whole —
   recognition is never recall.
4. {{ grounding_rule }}
5. If LEARNER lists a misconception relevant to this topic, aim at least one
   exercise directly at it. When several insights or preferences apply,
   ALL constrain every item — compose; never add items to give each
   its own.
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

OUTPUT — your final output is exactly this JSON shape (anything before it is ignored):
{
  "items": [
    {
      "prompt": "the exercise text, ≤ {{ prompt_words }} words",
      "answer": "the ideal answer, ≤ {{ answer_words }} words",
      "rubric": "- first scoring criterion\n- second scoring criterion",
      "skill": "recall"
    },
    {
      "prompt": "the second exercise, shaped exactly like the first",
      "answer": "its ideal answer",
      "rubric": "- one criterion can be enough",
      "skill": "produce"
    }
  ],
  "note": null,
  "intervention": null
}
Field rules: EVERY item carries all four fields, like both examples above —
but the examples' skills are placeholders, not defaults: pick each item's
skill for its pedagogy. "skill" is exactly ONE word — recall, explain, apply,
produce, critique, or present. "rubric" is ONE string holding 1-3 dash bullets (null only
when skill is "present"). "note" stays null unless you deviated (then ≤
{{ note_words }} words). "intervention" is for rule 9 only, with items []:
{"kind": "clarify_goal" or "need_context" or "scope_too_broad", "questions":
["your sharp question?"], "reason": "≤ {{ intervention_reason_words }} words"}.
Check before returning: valid JSON; exactly {{ n_items }} items (or fewer + note,
or none + intervention); every item has all four fields; every prompt
self-contained; no prompt reveals its answer.
