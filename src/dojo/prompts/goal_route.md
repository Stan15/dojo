You are routing a learner's NEW LEARNING GOAL against their existing campaigns.

TASK: Decide whether GOAL extends an existing campaign or needs a new one,
using only REGISTRY.

RULES
1. A listed topic already covers the goal → "attach". Copy campaign and topic
   path EXACTLY as written in REGISTRY.
2. Goal fits a campaign's mission but no listed topic → "new_topic" with the
   closest existing parent path and a new leaf (≤ 3 words).
3. No campaign fits → "propose_campaign" (name ≤ 4 words, mission ≤ 15 words,
   in the learner's own framing). Never force a bad fit.
4. Torn between two homes → choose the better one, set confidence "low".
5. Never "stay_inbox": a goal always takes one of the three actions above.

## GOAL
{{ goal_verbatim }}
## REGISTRY
{{ campaign_lines_and_topic_paths }}

OUTPUT — return only this JSON:
{"action": "attach|new_topic|propose_campaign", "campaign": null,
 "topic_path": null, "new_name": null, "new_mission": null,
 "confidence": "high|low", "reason": "≤ 12 words", "seed": false}
Check: campaign and topic_path copied verbatim from REGISTRY (only a new_topic
leaf or a proposed campaign may be new text); reason ≤ 12 words.
