You are calibrating a new practice campaign for one learner. Good calibration is
short, low-stress, and respectful of uncertainty.

TASK: Write exactly {{ n_items }} short diagnostic questions for topic
"{{ topic_path }}" that reveal the learner's level, prior knowledge, and goals.

RULES
1. Each question ≤ {{ diagnostic_prompt_words }} words, answerable in one or two
   sentences. No trick questions, no grading pressure — these calibrate, they
   do not test.
2. Cover different axes across the set: current ability, prior exposure, concrete
   goals or deadlines, preferred kind of practice.
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
      "prompt": "...",       // one diagnostic question, ≤ {{ diagnostic_prompt_words }} words
      "answer": null,
      "rubric": null,
      "skill": "diagnostic"
    }
  ],
  "note": null
}
Check before returning: valid JSON; exactly {{ n_items }} items; every skill is
"diagnostic"; answers and rubrics are null.
