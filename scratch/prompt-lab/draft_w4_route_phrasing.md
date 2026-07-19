# W4 draft — replace "is one word" meta-descriptor with the enum form
# (apply ONLY when tree unfreezes: after R3-LFM probe arms both complete)

Mechanism (3/3 sampled lfm-think route transcripts): thinking-class models
take "one word" LITERALLY, spiral on underscore-containing values
("propose_campaign is two words?!"), and emit JSON with required fields
omitted. attempt_grade.md already uses the safe enum form ("score is one of
1.0/0.7/0.3/0.0") — this makes the other four templates consistent with it.

Full protocol: prompts/README.md re-read (done 2026-07-19, modes 1-10),
docs/design/prompts.md open during the edit; goldens + token-footprint +
output-budget rebuild same commit (template hash changes!). Statement gate
unaffected (no numeric caps touched).

## Exact edits (byte-minimal, one per template)

campaign_reflect.md:
- OLD: `Field rules: "op" is one word — create, update, or resolve.`
- NEW: `Field rules: "op" is exactly one of create, update, resolve.`

campaign_plan.md:
- OLD: `Field rules: "kind" is one word — recall or skill.`
- NEW: `Field rules: "kind" is exactly one of recall, skill.`

goal_route.md:
- OLD: `Field rules: "action" is one word — attach, new_topic, or propose_campaign.`
- NEW: `Field rules: "action" is exactly one of attach, new_topic, propose_campaign.`

capture_route.md:
- OLD: `Field rules: "action" is one word — attach, new_topic, propose_campaign, or\nstay_inbox.`
- NEW: `Field rules: "action" is exactly one of attach, new_topic, propose_campaign,\nstay_inbox.`

(Adjust line-wraps to actual bytes at apply time; keep each rule a single
sentence; do NOT reintroduce enum-echo — the skeleton values stay single
realistic literals, README mode 1.)

## Decision rule (pre-registered in WORKBENCH)

Primary: lfm2.5-thinking route mini (route_ + goal_route_ scenarios) ≥4/11
(from 0/11). Guard: 4B route cells flat-or-better (gemma 6/6+1/2 baseline,
qwen 1/6+0/2 — the qwen route weakness is a separate open problem, must not
worsen); plan/reflect minis both 4B models flat (the kind/op lines changed
too). Byte delta ≈ 0 (same-length sentences) — footprint should be ~neutral;
rebuild anyway (hash).
