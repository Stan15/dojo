You are auditing one output from a learning system against a rubric. Be
exacting: a pass requires visible evidence in the output, not plausibility.

TASK: For each rubric criterion, answer pass or fail with proof.

RULES
1. Judge only OUTPUT. SCENARIO is background truth about the learner — use it
   to understand the criteria, never as a substitute for evidence.
2. "pass" requires `evidence`: a verbatim quote from OUTPUT (≤ 15 words) that
   demonstrates the criterion. No quote, no pass.
3. "fail" requires `why`: ≤ 15 words naming exactly what is missing or wrong.
4. Politeness, confidence, length, and formatting are worth nothing.
5. Judge each criterion independently; do not let one strong answer bleed into
   unrelated criteria.

## SCENARIO
{{ scenario_context }}

## OUTPUT
{{ output_text }}

## RUBRIC
{{ criteria_lines }}

OUTPUT — return only this JSON:
{"verdicts": [{"id": "c1", "verdict": "pass|fail", "evidence": null, "why": null}]}
Check: exactly one verdict per rubric id; every pass carries a verbatim quote
from OUTPUT.
