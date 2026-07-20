You are calibrating a new practice campaign for one learner. Good calibration is
short, low-stress, and respectful of uncertainty.

TASK: Write exactly {{ n_items }} short diagnostic questions for topic
"{{ topic_path }}" that reveal the learner's level, prior knowledge, and goals.

RULES
1. Each question ≤ {{ diagnostic_prompt_words }} words, answerable in one or two
   sentences. No trick questions, no grading pressure — these calibrate, they
   do not test.
2. Cover different axes across the set: current ability, prior exposure, concrete
   goals or deadlines, preferred kind of practice — but skip every axis LEARNER
   already answers. A fact stated there is settled: never re-ask it — a
   narrower or rephrased version of a stated goal or preference is still a
   re-ask; probe past it (where it breaks down, under which constraint, how
   confident) or take an axis it leaves open.
3. Self-contained: no references to files, links, or earlier exercises.
4. Do not ask the learner to design curricula or schedules; ask what they want
   and what they know.

## MISSION
{{ mission }}
## LEARNER
{{ insights_digest }}

OUTPUT — your final output is exactly this JSON (anything before it is ignored):
{
  "items": [
    {
      "prompt": "one diagnostic question, ≤ {{ diagnostic_prompt_words }} words",
      "answer": null,
      "rubric": null,
      "skill": "diagnostic"
    }
  ],
  "note": null
}
Field rules: in EVERY item, "skill" is exactly the word diagnostic, and
"answer" and "rubric" stay null. "note" stays null unless you returned
fewer than {{ n_items }} items (then ≤ {{ note_words }} words saying why).
Check before returning: valid JSON; exactly {{ n_items }} items; every skill is
"diagnostic"; answers and rubrics are null.
