You are filing one captured note into a learner's existing learning system.

TASK: Decide where CAPTURE belongs, using only REGISTRY.

RULES
1. Prefer attaching to an existing topic. Copy campaign and topic path EXACTLY as
   written in REGISTRY.
2. Fits a campaign but no listed topic → "new_topic" with the closest existing
   parent path and a new leaf (≤ 3 words).
3. Fits no campaign → "propose_campaign" (name ≤ {{ new_name_words }} words,
   mission ≤ {{ new_mission_words }} words). Never force a bad fit.
4. Torn between two homes → choose the better one, set confidence "low".
5. "seed": true ONLY if the capture itself carries enough substance to write
   an exercise from (a stated fact, rule, or technique — not a bare topic
   mention); when the campaign's normal replenishment would cover it, false.

## CAPTURE
{{ text_and_learner_note }}
## REGISTRY
{{ campaign_lines_and_topic_paths }}

OUTPUT — your final output is exactly this JSON (anything before it is ignored):
{"action": "attach|new_topic|propose_campaign|stay_inbox", "campaign": null,
 "topic_path": null, "new_name": null, "new_mission": null,
 "confidence": "high|low", "reason": "≤ {{ reason_words }} words", "seed": false}
Check: campaign and topic_path copied verbatim from REGISTRY (only a new_topic
leaf or a proposed campaign may be new text); reason ≤ {{ reason_words }} words.
