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
5. "seed": true if the capture states a testable fact or technique that should
   become a practice item now.

## CAPTURE
{{ text_and_learner_note }}
## REGISTRY
{{ campaign_lines_and_topic_paths }}

OUTPUT — your final output is exactly this JSON (anything before it is ignored):
{"action": "attach", "campaign": null, "topic_path": null, "new_name": null,
 "new_mission": null, "confidence": "high", "reason": "≤ {{ reason_words }} words", "seed": false}
Field rules: "action" is one word — attach, new_topic, propose_campaign, or
stay_inbox. attach and new_topic need campaign + topic_path; propose_campaign
needs new_name + new_mission; the fields your action does not use stay null.
"confidence" is high or low.
Check: campaign and topic_path copied verbatim from REGISTRY (only a new_topic
leaf or a proposed campaign may be new text); reason ≤ {{ reason_words }} words.
