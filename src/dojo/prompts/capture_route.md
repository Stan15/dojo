You are filing one captured note into a learner's existing learning system.

TASK: Decide where CAPTURE belongs, using only REGISTRY.

RULES
1. Prefer attaching to an existing topic. Copy campaign and topic path EXACTLY as
   written in REGISTRY.
2. Fits a campaign but no listed topic → "new_topic" with the closest existing
   parent path and a new leaf (≤ 3 words).
3. Fits no campaign → "propose_campaign" (name ≤ 4 words, mission ≤ 15 words).
   Never force a bad fit.
4. Torn between two homes → choose the better one, set confidence "low".
5. "seed": true if the capture states a testable fact or technique that should
   become a practice item now.

## CAPTURE
{{ text_and_learner_note }}
## REGISTRY
{{ campaign_lines_and_topic_paths }}

OUTPUT — return only this JSON:
{"action": "attach|new_topic|propose_campaign|stay_inbox", "campaign": null,
 "topic_path": null, "new_name": null, "new_mission": null,
 "confidence": "high|low", "reason": "...", "seed": false}
Check: campaign and topic_path copied verbatim from REGISTRY (only a new_topic
leaf or a proposed campaign may be new text).
