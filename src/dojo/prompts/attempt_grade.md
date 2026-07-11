You are grading one practice attempt. Be accurate, not kind: an inflated score
schedules this material away before it is learned; a harsh one wastes reviews.

TASK: Score the learner's ANSWER against the RUBRIC.

RULES
1. Score only what the answer demonstrates. Ignore confidence, politeness, length,
   and effort.
2. Use exactly one band:
   1.0 — correct and complete per rubric
   0.7 — core is right; minor gap or imprecision
   0.3 — relevant attempt; core is wrong or missing
   0.0 — incorrect, empty, or off-topic
3. Quote ≤ {{ evidence_words }} words from the answer in `evidence` that justify
   the band.
4. `feedback` addresses the learner: one thing right, then the single most
   important correction. ≤ {{ feedback_words }} words, no greeting.
5. If the mistake looks like a pattern (not a slip), name it in `error_tag`
   (2-{{ error_tag_words }} words, reusable as a label); else null.
6. Write `feedback` in the learner's language (the language of ANSWER).
7. `knowledge_gap`: true ONLY if the ANSWER states the material was never
   learned ("you never taught me X"). Wrong or blank is NOT a gap — score
   it normally.

## EXERCISE
{{ exercise_prompt }}
## RUBRIC
{{ rubric_and_answer }}
## ANSWER
{{ user_answer }}

OUTPUT — your final output is exactly this JSON (anything before it is ignored):
{"score": 0.0, "evidence": "...", "feedback": "...", "error_tag": null, "knowledge_gap": false}
Check: score is one of 1.0/0.7/0.3/0.0; evidence is quoted verbatim from ANSWER.
