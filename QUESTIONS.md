# QUESTIONS for the product owner

Non-blocking. Each has the default I will proceed on if unanswered. Answer inline
whenever convenient.

1. **Grading source of truth.** For free-form answers, default flow is: harness grades
   against the stored rubric (task `attempt.grade`), learner can override with
   `dojo correct`. Alternative: self-assessment first (learner rates own recall,
   Anki-style), AI grading only on request — cheaper in tokens, slightly weaker
   evidence. **Default: AI-grades with rubric when a harness is present; self-report
   fallback offline.**

2. **Daily packet size.** Default packet: 5 items, ~10 minutes, hard cap 8. Bigger?
   Smaller? **Default: 5, configurable `daily.packet_size`.**

3. **Subprocess connectors.** Keep as secondary supported adapter (headless cron
   replenishment, non-agent users), or drop entirely until someone asks? Keeping costs
   ~500 lines of maintained code. **Default: keep, but demoted and quarantined behind
   the same task contract.**

4. **`archived_implementation/`.** Delete after M1 (git history preserves it), or keep
   in-tree? **Default: delete at end of M1.**

5. **Python floor.** pyproject says `>=3.11`; README badge says 3.8+. **Default: 3.11.**

6. **Capture routing autonomy.** When you capture a fact and routing confidence is
   high, should the item auto-file into the campaign (you see it at next review), or
   always ask you to confirm the route first? **Default: auto-file, with the route
   noted in the item's provenance and reversible via `dojo inbox`.**
