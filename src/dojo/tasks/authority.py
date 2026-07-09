"""Change authority for AI plan revisions (owner directive 2026-07-09).

The learner's attack plan is a CONTRACT, not a dial: the system may adapt
difficulty/scaffolding silently, but structural change needs either the
learner's own words as provenance or their explicit confirmation — nothing
restructures under their feet. This module holds the deterministic half:

- `classify_plan_delta`: additive/cosmetic edits are MINOR (apply + journal
  snapshot + announce, revertable); anything that removes, reorders, or
  tightens what the learner signed up for is MAJOR.
- `confirmed_plan_baseline`: the plan as of the learner's last explicit
  yes (campaign creation, `dojo plan confirm`, revert). The anti-drip rail:
  a revision is classified against this baseline, not the current plan, so
  many small edits cannot add up to a silent rewrite.
- `revision_is_user_initiated`: a revision whose `evidence` cites attempts
  carrying the learner's own non-empty feedback was asked for — it applies
  directly (still journaled + announced).

The applier (`service.apply_reflect`) consumes these; `DojoAPI.plan_*` owns
the confirm/reject/revert lifecycle. Proposals and applied changes live as
pedagogical-journal entries (the campaign's event log) — no new storage.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from ..schemas import AttackPlanPhase

# Journal actions owned by this module (CREATE/PHASE_ADVANCE/REFLECT are older).
PLAN_CONFIRMED = "PLAN_CONFIRMED"  # learner said yes to this exact plan
PLAN_APPLIED = "PLAN_APPLIED"      # minor or user-initiated revision, applied
PLAN_PROPOSED = "PLAN_PROPOSED"    # major inferred revision, awaiting the learner
PLAN_REVERTED = "PLAN_REVERTED"    # learner undid an applied revision

_BASELINE_ACTIONS = ("CREATE", PLAN_CONFIRMED, PLAN_REVERTED)


def _phases(plan: list[Any]) -> list[dict]:
    """Normalizes AttackPlanPhase models / dicts to plain dicts."""
    return [p.model_dump() if isinstance(p, AttackPlanPhase) else dict(p) for p in plan]


def classify_plan_delta(baseline: list[Any], proposed: list[Any]) -> str:
    """"minor" iff the proposal only ADDS or relaxes: every baseline phase
    keeps its position and its full topic set (extra topics allowed), criteria
    only loosen (min_attempts/min_accuracy never rise), and new phases only
    append. Removing/moving a topic, dropping/reordering/inserting phases, or
    tightening criteria is "major" — that changes what the learner agreed to."""
    base, prop = _phases(baseline), _phases(proposed)
    if len(prop) < len(base):
        return "major"
    for old, new in zip(base, prop):
        if not set(old.get("topics") or []) <= set(new.get("topics") or []):
            return "major"
        oc, nc = old.get("criteria") or {}, new.get("criteria") or {}
        if float(nc.get("min_attempts", 0)) > float(oc.get("min_attempts", 0)):
            return "major"
        if float(nc.get("min_accuracy", 0.0)) > float(oc.get("min_accuracy", 0.0)):
            return "major"
    return "minor"


def confirmed_plan_baseline(campaign) -> Optional[list[dict]]:
    """The plan snapshot from the learner's most recent explicit plan act
    (campaign creation, confirm, revert), or None for legacy campaigns whose
    journal predates snapshots — callers fall back to the current plan (no
    drip protection until the first confirm, which is honest)."""
    for entry in reversed(campaign.pedagogical_journal):
        if entry.get("action") in _BASELINE_ACTIONS and entry.get("plan_snapshot"):
            return entry["plan_snapshot"]
    return None


def revision_is_user_initiated(store, campaign_id: str, evidence: list[str]) -> bool:
    """True when any cited attempt carries the learner's own voice: explicit
    `feedback`, or an answer to a DIAGNOSTIC question (the system asked, the
    learner told it — onboarding calibration and the reflect `questions`
    channel both land here). Deterministic reading of "the learner asked for
    this". (Citations are already validated ⊆ shown attempts by the applier.)"""
    for att_id in evidence:
        att = store.attempts.get(campaign_id, att_id)
        if att is None:
            continue
        if (att.feedback or "").strip():
            return True
        ex = store.exercises.get(campaign_id, att.exercise_id)
        # An answered diagnostic retires to "spent" (outcomes.land_score).
        if ex is not None and ex.quality in ("diagnostic", "spent"):
            return True
    return False


def journal_entry(action: str, *, reason: str, task_id: str,
                  plan_snapshot: list[Any], proposed: Optional[list[Any]] = None) -> dict:
    """One plan-authority journal entry. `plan_snapshot` is always the
    PRE-change plan (what revert restores); PROPOSED entries also carry the
    proposed phases and a pending status that confirm/reject resolves."""
    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "trigger": f"reflection task {task_id}",
        "hypothesis": reason,
        "status": "pending" if action == PLAN_PROPOSED else "applied",
        "plan_snapshot": _phases(plan_snapshot),
        "announced": False,
    }
    if proposed is not None:
        entry["proposed_phases"] = _phases(proposed)
    return entry


def pending_proposal(campaign) -> Optional[dict]:
    """The newest still-pending PLAN_PROPOSED journal entry, or None."""
    for entry in reversed(campaign.pedagogical_journal):
        if entry.get("action") == PLAN_PROPOSED and entry.get("status") == "pending":
            return entry
    return None


def last_revertable(campaign) -> Optional[dict]:
    """The newest applied-and-not-reverted PLAN_APPLIED entry, or None."""
    for entry in reversed(campaign.pedagogical_journal):
        if entry.get("action") == PLAN_REVERTED:
            return None  # a revert closes the undo window; older applies were accepted
        if entry.get("action") == PLAN_APPLIED and entry.get("status") == "applied":
            return entry
    return None
