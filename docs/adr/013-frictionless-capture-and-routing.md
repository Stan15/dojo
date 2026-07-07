# ADR 013: Frictionless Capture with Deferred, Validated Routing

## Status
Accepted (design phase, 2026-07-07).

## Context
The learner encounters something worth retaining mid-reading/mid-conversation and
wants one utterance — "remember this" — to guarantee it enters practice. Every
filing question at capture time (which campaign? what topic? what difficulty?)
erodes the habit; but unfiled material that silently accumulates never gets
practiced. Routing is a judgment call (which campaign/topic fits), so it belongs to
the AI — yet a weak model must not be able to file things into nonexistent places.

## Decision
1. **Capture ≠ filing.** `dojo capture "<text>" [--why "<note>"]` durably writes a
   **micro-source** to `inbox/` before any AI is involved. Capture never asks
   questions and cannot fail for classification reasons.
2. **Routing is a task** (`capture.route`, per ADR 010) carrying a budgeted
   registry digest (campaign missions one-line each + topic paths). The result
   proposes exactly one of: `attach(campaign, topic)`, `new_topic(campaign,
   parent, name)`, `propose_campaign(name, mission)`, `stay_inbox(reason)` — with
   a confidence.
3. **Code validates the route**: targets must exist in the registry (nonexistent →
   rejected, item stays in inbox). The validated route is a **proposal awaiting
   learner confirmation by default** (product-owner decision 2026-07-07, Q6) —
   confirmed inline in the capturing conversation or later via `dojo inbox`, and
   nagged in the next `daily` envelope so the inbox cannot silently rot.
   `capture.autofile: true` opts into auto-filing high-confidence routes, always
   recorded in provenance and reversible via `dojo inbox`.
4. **A routed capture is an ordinary Source** — the smallest one. It grounds a
   fact-candidate through the same review gate and queue caps as everything else.
   No parallel pipeline.

## Consequences
- One-utterance capture from any harness conversation; the habit survives.
- Weak-model safety: misrouting is structurally impossible beyond "wrong but
  existing target," which provenance + `dojo inbox` make reversible.
- The inbox is a visible, bounded staging state with a nagging surface — not a
  junk drawer.
