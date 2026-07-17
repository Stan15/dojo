"""The Python API behind every dojo surface.

`DojoAPI` is the single façade the CLI, the interactive flows, and the agent
SKILL all call — one behavior, three skins. Every method returns plain dicts
(JSON-ready, so `--json` output is the same object humans see rendered) and
follows the system's two structural rules:

- **Never block on AI** (blueprint I4): anything that needs a model becomes an
  emitted task with a `tasks` list in the response; deterministic work
  (scheduling, scoring floors, phase math) happens inline.
- **Deterministic pedagogy core** (ADR 012): scheduling state changes go
  through `outcomes.land_score`, never ad-hoc.

Responses carry a `next` hint — the one action that keeps the learning loop
moving — because agents and humans alike resume from cold context.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logger import get_logger
from .schemas import (
    Source,
    Campaign,
    Exercise,
    Candidate,
    Attempt,
    Insight,
    PracticeSession,
    AttackPlanPhase,
)
from . import scheduling
from .store import DojoStore, slugify


class DojoAPI:
    """Façade over the store, scheduler, and task system.

    Construct one per process; it owns a `DojoStore` (git-versioned markdown
    under the dojo directory) and a file logger. All state lives in the store —
    the API object itself is stateless and cheap.

    Args:
        dojo_dir: Root of the dojo data directory. `None` resolves the
            default location; a file path is tolerated by using its parent
            (legacy callers passed the old SQLite db file).
    """

    def __init__(self, dojo_dir: str | Path | None = None):
        if dojo_dir is not None:
            path = Path(dojo_dir)
            if path.suffix:
                dojo_dir = path.parent
        self.store = DojoStore(dojo_dir)
        self.log = get_logger(self.store.dojo_dir, "api")

    def _land_score(
        self,
        campaign_id: str,
        exercise_id: str,
        *,
        score: float,
        latency_seconds: float | None = None,
        skip_reason: str | None = None,
    ) -> None:
        """Delegates to outcomes.land_score — the one lane-aware landing
        (ADR 012/014). Provisional scores (pending AI grade) must not call
        this: a placeholder 0.0 would poison the schedule."""
        from .outcomes import land_score

        land_score(
            self.store, campaign_id, exercise_id,
            score=score, latency_seconds=latency_seconds, skip_reason=skip_reason,
        )

    def daily(self, size: int | None = None, reset: bool = False) -> dict[str, Any]:
        """The product's face: one bounded, interleaved, explained packet
        (blueprint §7). Never blocks on AI (I4): missing skill stock becomes
        emitted tasks + honest counts, and recall practice always works."""
        from . import packet as packet_mod
        from .tasks import flows

        now = datetime.now(timezone.utc)

        # daily is the ritual's HEARTBEAT (use-case audit 2026-07-08): every
        # step the learning loop depends on either happens here deterministically
        # or is re-surfaced here — never parked in commands nobody must run.

        # 1. Phase advancement is pure math; it must not wait for a reflect
        # call — and it runs BEFORE the notice scan so a completion detected
        # right now is announced right now, not tomorrow.
        for campaign in self.store.campaigns.list():
            if campaign.status == "active":
                self._evaluate_campaign_phase_advancement(campaign)

        # 1b. Housekeeping is the heartbeat's job too: spent, unreferenced
        # task files age out (git keeps history); provenance-bearing tasks
        # are untouchable. Counted honestly in the envelope when it acts.
        housekept = self._task_housekeeping(now)

        # Plan-authority surfacing (QUESTIONS.md 2026-07-09): pending proposals
        # repeat until resolved; auto-applied changes announce exactly once.
        # Ownership surfacing rides the same machinery: insight changes and
        # campaign completions announce once; idle campaigns are stated as a
        # neutral fact with doors.
        plan_proposals, plan_changes = self._plan_notices()
        insight_notes, completions = self._ownership_notices()
        idle = self._idle_campaigns(now)
        plan_keys = (
            ({"plan_proposals": plan_proposals} if plan_proposals else {})
            | ({"plan_changes": plan_changes} if plan_changes else {})
            | ({"insight_notices": insight_notes} if insight_notes else {})
            | ({"campaign_completions": completions} if completions else {})
            | ({"idle_campaigns": idle} if idle else {})
            | ({"housekeeping": {"spent_tasks_deleted": housekept}} if housekept else {})
        )
        proposal_hint = (
            f" ({len(plan_proposals)} plan proposal(s) await you: dojo plan show)"
            if plan_proposals else ""
        )

        active = self.store.sessions.get_active()
        if active and active.status == "active" and not reset:
            return {
                "is_new": False,
                "session": active.model_dump(),
                "why": active.packet_reasons,
                **plan_keys,
                "next": "resume: dojo ready reveals the next prompt (dojo daily --reset to rebuild)"
                        + proposal_hint,
            }

        pkt = packet_mod.build_packet(self.store, now, size=size)

        # Acquisition discipline (owner field report 2026-07-09): once today's
        # practice happened, daily STOPS being an acquisition surface — no new
        # generation, and freshly-minted stock waits for tomorrow. `dojo more`
        # is the only post-completion acquisition door (debt-guarded there).
        today = now.date().isoformat()
        practiced_today = any(
            a.created_at[:10] == today
            for c in self.store.campaigns.list() if c.status == "active"
            for a in self.store.attempts.list(c.id)
        )

        # 2. Token frugality: at most 2 generation tasks per daily run; the rest
        # wait and are counted honestly (E2E finding: a fresh plan emitted 5 at once).
        MAX_DAILY_TASKS = 0 if practiced_today else 2
        tasks = []
        for need in pkt.needs_generation[:MAX_DAILY_TASKS]:
            campaign = self.store.campaigns.get(need["campaign_id"])
            if campaign is None:
                continue
            try:
                task = flows.request_generation(
                    self.store, campaign,
                    topic_path=need["topic_path"], n_items=2,
                    source_slice=flows.grounding_slice(self.store, campaign, need["topic_path"]),
                    diagnostic=bool(need.get("diagnostic")),
                    auto_promote=not bool(need.get("diagnostic")),
                )
            except Exception as e:
                # The heartbeat never dies because one AI task failed to
                # compile (I4; owner field crash 2026-07-16) — count it,
                # keep serving practice.
                self.log.error(f"generation compile failed ({need['topic_path']}): {e}")
                pkt.skipped["generation_compile_errors"] = (
                    pkt.skipped.get("generation_compile_errors", 0) + 1)
                continue
            tasks.append(flows.task_ref(task))
        deferred = len(pkt.needs_generation) - min(len(pkt.needs_generation), MAX_DAILY_TASKS)
        if deferred:
            key = "generation_waits_for_tomorrow" if practiced_today else "generation_deferred"
            pkt.skipped[key] = deferred

        # Fresh stock minted after today's practice (e.g. a morning
        # replenishment task fulfilled late) is TOMORROW's material: a packet
        # that would consist purely of never-practiced items after completion
        # is acquisition creep, not a session.
        if practiced_today and pkt.items:
            fresh_only = all(
                (ex := self.store.exercises.get(item.campaign_id, item.exercise_id)) is not None
                and ex.sr is None
                for item in pkt.items
            )
            if fresh_only:
                pkt.skipped["new_stock_held_for_tomorrow"] = len(pkt.items)
                pkt.items = []

        # 3. Reflection fires by evidence threshold, not by hoping someone runs
        # `dojo reflect` — the personalization loop must close mechanically.
        REFLECT_THRESHOLD = 5
        reflect_backlog = [
            (sum(1 for a in self.store.attempts.list(c.id) if not a.reflected), c.id)
            for c in self.store.campaigns.list() if c.status == "active"
        ]
        reflect_backlog = [x for x in reflect_backlog if x[0] >= REFLECT_THRESHOLD]
        if reflect_backlog:
            _, campaign_id = max(reflect_backlog)
            try:
                reflect_task = flows.request_reflection(self.store, campaign_id)
            except Exception as e:
                # Same rule (I4): reflection is deferrable, practice is not.
                self.log.error(f"reflection compile failed ({campaign_id}): {e}")
                pkt.skipped["reflection_compile_errors"] = 1
                reflect_task = None
            if reflect_task is not None:
                tasks.append(flows.task_ref(reflect_task))

        # 4. Unfinished AI work from previous runs is re-surfaced every morning
        # (a grade task forgotten yesterday must not starve silently).
        emitted_ids = {t["id"] for t in tasks}
        stale = [
            flows.task_ref(t) for t in self.store.tasks.list(filters={"status": "pending"})
            if t.id not in emitted_ids
        ]

        if not pkt.items:
            # Daily-completion (QUESTIONS 2026-07-09, exact spec'd copy): the
            # learner practiced today and the schedule is drained — today is
            # DONE. Push surfaces get principles, not counters; `dojo more` is
            # mentioned as the ANSWER to a request, never as an offer, and the
            # copy binds the harness to the same no-solicitation rule.
            if practiced_today:
                return {
                    "is_new": False,
                    "session": None,
                    "status": "complete_for_today",
                    "tasks": tasks,
                    "stale_tasks": stale,
                    "skipped": pkt.skipped,
                    **plan_keys,
                    # The copy is static (spec'd verbatim); a pending plan
                    # PROPOSAL still rides along — it is a consent question
                    # that repeats until resolved, not practice solicitation.
                    "next": (
                        "today's practice is complete — tell the learner it's done, "
                        "playfully (go touch grass); tomorrow's session is what makes "
                        "it stick (consistency beats volume); do not offer more "
                        "practice unprompted; if the learner explicitly asks for "
                        "more, run: dojo more --json"
                    ) + proposal_hint,
                }
            return {
                "is_new": False,
                "session": None,
                "tasks": tasks,
                "stale_tasks": stale,
                "skipped": pkt.skipped,
                "campaign_reasons": pkt.campaign_reasons,
                **plan_keys,
                "next": (
                    "nothing is due right now"
                    + ("; fulfill the generation task(s) then re-run dojo daily" if tasks else
                       (" — but finish the pending task(s) below first" if stale else
                        " — enjoy the day off, the schedule is honest"))
                    + proposal_hint
                ),
            }

        session = PracticeSession(
            id=f"sess_{uuid.uuid4().hex[:8]}",
            exercise_ids=[item.exercise_id for item in pkt.items],
            packet_reasons={i.exercise_id: i.reason for i in pkt.items},
            campaign_reasons=pkt.campaign_reasons,
        )
        self.store.sessions.save_active(session)
        self.log.info(f"Daily packet built: {len(pkt.items)} items, {len(tasks)} tasks emitted")

        waiting = sum(
            1 for c in self.store.captures.list() if c.status in ("unrouted", "proposed")
        )
        return {
            "is_new": True,
            "session": session.model_dump(),
            "items": [
                {"exercise_id": i.exercise_id, "campaign_id": i.campaign_id, "reason": i.reason}
                for i in pkt.items
            ],
            "skipped": pkt.skipped,
            "tasks": tasks,
            "stale_tasks": stale,
            "inbox_waiting": waiting,
            **plan_keys,
            "next": "dojo ready reveals the first prompt"
                    + (f" ({waiting} capture(s) awaiting a home: dojo inbox)" if waiting else "")
                    + (f" ({len(stale)} unfinished task(s) from earlier — fulfill them too)" if stale else "")
                    + proposal_hint,
        }

    def why(self) -> dict[str, Any]:
        """Replays the scheduling decisions behind the current packet (I9) —
        and when no session is live, behind the MOST RECENT completed one:
        curiosity peaks right after finishing, and the interactive daily has
        already consumed the session by then (owner field report
        2026-07-09). Archived sessions keep their reasons, so `why` always
        has an answer once you've ever practiced."""
        session = self.store.sessions.get_active()
        status = "active"
        if session is None:
            archived = self.store.sessions.list_archived()
            if not archived:
                return {"session": None, "note": "no session yet — dojo daily starts one"}
            session = max(archived, key=lambda s: s.created_at)
            status = "completed"
        return {
            "session": session.id,
            "session_status": status,
            **({"note": "your most recent completed session"} if status == "completed" else {}),
            "items": [
                {"exercise_id": ex_id, "reason": session.packet_reasons.get(ex_id, "(built before reasons were recorded)")}
                for ex_id in session.exercise_ids
            ],
            "campaigns": session.campaign_reasons,
        }

    def _review_load_7d(self, now: datetime) -> tuple[int, int]:
        """(projected_due_7d, capacity_7d): the global review-debt projection
        behind the capacity channel's guard. Projected load counts every FSRS
        memory due inside the next 7 days — overdue included — across active
        campaigns: recall/skill exercises with `sr` state plus due skill
        TOPICS (each due topic demands one novel exercise). Never-practiced
        stock is acquisition, not review debt, so it does not count. Capacity
        is packet_size × 7 × `pacing.headroom` (default 0.8)."""
        from . import packet as packet_mod

        horizon = now + timedelta(days=7)
        projected = 0
        for camp in self.store.campaigns.list():
            # Maintenance reviews are review load too (ADR 005): they share
            # the same daily packets the guard is protecting.
            if camp.status not in ("active", "maintenance"):
                continue
            retired = packet_mod.retired_paths(camp)
            for ex in self.store.exercises.list(camp.id):
                if ex.quality in packet_mod.EXCLUDED_QUALITIES or not ex.sr:
                    continue
                if packet_mod._on_retired(ex.topic_path, retired):
                    continue  # retired dues never serve — not debt (ADR 017 §6)
                due = scheduling.due_at(ex.sr)
                if due is not None and due <= horizon:
                    projected += 1
            for topic in camp.topics or []:
                if topic.get("kind") != "skill" or not topic.get("sr") or topic.get("retired"):
                    continue
                due = scheduling.due_at(topic["sr"])
                if due is not None and due <= horizon:
                    projected += 1
        configured = int(self.store.configs.get_value(
            "daily.packet_size", packet_mod.DEFAULT_PACKET_SIZE))
        packet_size = max(1, min(configured, packet_mod.HARD_MAX_PACKET_SIZE))
        headroom = float(self.store.configs.get_value("pacing.headroom", 0.8))
        return projected, int(packet_size * 7 * headroom)

    def _weakest_topic(self) -> Optional[tuple[str, str]]:
        """(campaign_id, topic_path) with the lowest mean graded score —
        where one extension generation buys the most; None without scored
        evidence anywhere (generating hard content blind is how day-one
        bombardment happened)."""
        from . import packet as packet_mod

        means: dict[tuple[str, str], list[float]] = {}
        for camp in self.store.campaigns.list():
            if camp.status != "active":
                continue
            retired = packet_mod.retired_paths(camp)
            topic_of = {ex.id: ex.topic_path for ex in self.store.exercises.list(camp.id)}
            for a in self.store.attempts.list(camp.id):
                topic = topic_of.get(a.exercise_id)
                if (topic and not a.skip_reason
                        and a.grader not in (None, "exposure")
                        and not packet_mod._on_retired(topic, retired)):
                    means.setdefault((camp.id, topic), []).append(a.score)
        if not means:
            return None
        return min(means, key=lambda k: (sum(means[k]) / len(means[k]), k))

    def more(self, force: bool = False) -> dict[str, Any]:
        """The capacity channel (QUESTIONS 2026-07-09, STATE item 2) — answers
        an explicit request for more practice; nothing in the system ever
        OFFERS it. Retention is fixed by memory science, so this never serves
        today's completed reviews and never pulls tomorrow's forward: it
        grants up to `daily.extension_cap` (default 3) NEW items — unattempted
        stock, then candidates, then at most ONE generation task on the
        weakest topic — and only while the projected 7-day review load stays
        inside packet capacity × `pacing.headroom`. Refusal is an answer, not
        an error: the envelope carries the projection and the debt-free
        alternative. Once per calendar day. Extension attempts carry
        `origin: extension` so reflection can discount appetite-mode
        evidence. `force` overrides the debt guard (the projection is still
        reported first-class) but never the daily cap."""
        from . import packet as packet_mod
        from .tasks import flows

        now = datetime.now(timezone.utc)
        projected, capacity = self._review_load_7d(now)
        projection = {"projected_due_7d": projected, "capacity_7d": capacity}

        active = self.store.sessions.get_active()
        if active and active.status == "active":
            return {
                "extension_available": False, **projection,
                "reason": "a session is already open — finish it first",
                "alternative": "dojo ready continues the current session",
            }

        today = now.date().isoformat()
        if any(
            s.origin == "extension" and s.created_at[:10] == today
            for s in self.store.sessions.list_archived()
        ):
            return {
                "extension_available": False, **projection,
                "reason": "today's extension is already used — one per day keeps tomorrow's session doable",
                "alternative": "dojo daily tomorrow; dojo start --topic <path> re-drills existing material debt-free",
            }

        cap = max(1, int(self.store.configs.get_value("daily.extension_cap", 3)))
        headroom_left = capacity - projected
        if headroom_left < 1 and not force:
            return {
                "extension_available": False, **projection,
                "reason": (
                    f"{projected} reviews already land in the next 7 days against a "
                    f"capacity of {capacity} — new material now would become debt you'd meet on days 3/7/21"
                ),
                "alternative": "dojo start --topic <path> — targeted retrieval of existing material adds no review debt",
            }
        granted_cap = cap if force else min(cap, headroom_left)

        # Sourcing order (spec): unattempted stock → candidates → ONE generation.
        picks: list[tuple[str, str, str]] = []  # (campaign_id, exercise_id, reason)
        ranked = sorted(
            (c for c in self.store.campaigns.list() if c.status == "active"),
            key=lambda c: (-packet_mod.campaign_priority(self.store, c, now)[0], c.id),
        )
        for camp in ranked:
            if len(picks) >= granted_cap:
                break
            attempted = {a.exercise_id for a in self.store.attempts.list(camp.id)}
            fresh = sorted(
                (ex for ex in self.store.exercises.list(camp.id)
                 if ex.quality not in packet_mod.EXCLUDED_QUALITIES
                 and ex.id not in attempted and ex.sr is None),
                key=lambda e: e.id,
            )
            for ex in fresh[: granted_cap - len(picks)]:
                picks.append((camp.id, ex.id, "extension: unattempted stock, no new review debt beyond it"))
        for camp in ranked:
            if len(picks) >= granted_cap:
                break
            for cand in sorted(self.store.candidates.list(camp.id), key=lambda c: c.id):
                if len(picks) >= granted_cap:
                    break
                promoted = self.promote_candidate(cand.id)
                picks.append((camp.id, promoted["id"], "extension: promoted candidate (recorded auto-accept)"))

        tasks = []
        if len(picks) < granted_cap:
            weakest = self._weakest_topic()
            if weakest is not None:
                camp = self.store.campaigns.get(weakest[0])
                task = flows.request_generation(
                    self.store, camp,
                    topic_path=weakest[1],
                    n_items=min(granted_cap - len(picks), 3),
                    source_slice=flows.grounding_slice(self.store, camp, weakest[1]),
                    auto_promote=True,
                )
                tasks.append(flows.task_ref(task))

        if not picks:
            if tasks:
                return {
                    "extension_available": True, **projection, "session": None,
                    "tasks": tasks, "granted": 0,
                    "next": "no stock on hand — fulfill the generation task, then run dojo more again",
                }
            return {
                "extension_available": False, **projection,
                "reason": "no new material available and no graded evidence to target generation at",
                "alternative": "dojo start --topic <path> re-drills existing material debt-free",
            }

        session = PracticeSession(
            id=f"sess_{uuid.uuid4().hex[:8]}",
            origin="extension",
            exercise_ids=[ex_id for _, ex_id, _ in picks],
            packet_reasons={ex_id: reason for _, ex_id, reason in picks},
        )
        self.store.sessions.save_active(session)
        self.log.info(f"Extension granted: {len(picks)} items (asked, not offered)")
        out = {
            "extension_available": True, **projection,
            "session": session.model_dump(),
            "items": [
                {"exercise_id": ex_id, "campaign_id": camp_id, "reason": reason}
                for camp_id, ex_id, reason in picks
            ],
            "tasks": tasks, "granted": len(picks),
            "next": "dojo ready reveals the first prompt",
        }
        if force and headroom_left < len(picks):
            out["warning"] = (
                f"debt guard overridden: {projected} reviews already due within 7 days "
                f"against capacity {capacity}"
            )
        return out

    def stats(self, now: datetime | None = None) -> dict[str, Any]:
        """Observability surface (blueprint §11): retention/atrophy per campaign
        and token spend per task kind — computed, never guessed, and estimates
        are tagged as estimates (I10)."""
        from . import packet as packet_mod

        now = now or datetime.now(timezone.utc)
        campaigns_out = []
        for camp in self.store.campaigns.list():
            exercises = [
                ex for ex in self.store.exercises.list(camp.id)
                if ex.quality not in packet_mod.EXCLUDED_QUALITIES
            ]
            tracked = [ex for ex in exercises if ex.kind == "recall" and ex.sr]
            retention = (
                sum(scheduling.retrievability(ex.sr, now) for ex in tracked) / len(tracked)
                if tracked else None
            )
            due = sum(1 for ex in exercises if scheduling.is_due(ex.sr, now))
            attempts = self.store.attempts.list(camp.id)
            answered = [
                a for a in attempts[-20:]
                if not a.skip_reason and a.grader != "exposure"  # encodings aren't accuracy (ADR 017)
            ]
            accuracy = (
                sum(a.score for a in answered) / len(answered) if answered else None
            )
            last_touch = max((a.created_at for a in attempts), default=None)
            days_idle = (
                (now - datetime.fromisoformat(last_touch)).total_seconds() / 86400
                if last_touch else None
            )
            campaigns_out.append({
                "campaign_id": camp.id,
                "name": camp.name,
                "estimated_retention": None if retention is None else round(retention, 3),
                "retention_note": "mean recall odds over tracked fact memories (estimate)",
                "tracked_memories": len(tracked),
                "due_now": due,
                "active_exercises": len(exercises),
                "recent_accuracy": None if accuracy is None else round(accuracy, 3),
                "days_since_practice": None if days_idle is None else round(days_idle, 1),
                "active_insights": len(
                    self.store.insights.list(camp.id, filters={"status": "active"})
                ),
                # Care-exit honesty (ADR 017 §6): stopped reviews are a fact
                # the learner asked for, not a silent disappearance.
                "retired_topics": len(packet_mod.retired_paths(camp)),
            })

        by_kind: dict[str, dict[str, Any]] = {}
        for task in self.store.tasks.list():
            k = by_kind.setdefault(task.kind, {
                "tasks": 0, "fulfilled": 0, "failed": 0, "pending": 0,
                "prompt_bytes": 0, "response_bytes": 0,
            })
            k["tasks"] += 1
            k[task.status] = k.get(task.status, 0) + 1
            k["prompt_bytes"] += task.payload_bytes
            k["response_bytes"] += task.response_bytes
        for k in by_kind.values():
            k["approx_prompt_tokens"] = round(k.pop("prompt_bytes") / 4)
            k["approx_response_tokens"] = round(k.pop("response_bytes") / 4)

        waiting = sum(
            1 for c in self.store.captures.list() if c.status in ("unrouted", "proposed")
        )
        return {
            "campaigns": campaigns_out,
            "task_spend": dict(sorted(by_kind.items())),
            "inbox_waiting": waiting,
            "note": "retention figures are model estimates; scores and counts are records",
        }

    # ==========================================
    # Capture & Inbox (ADR 013)
    # ==========================================
    def capture(
        self, text: str, why: str | None = None, locator: str | None = None
    ) -> dict[str, Any]:
        """One utterance, durably saved BEFORE any AI runs; routing is a task.
        `locator` records where the material came from (URL/file) — the agent
        fetches and summarizes; dojo never touches the network."""
        from .schemas import Capture
        from .tasks import compiler, flows
        from .tasks import service as task_service

        cap = Capture(
            id=f"cap_{uuid.uuid4().hex[:8]}", text=text.strip(), why=why, locator=locator,
        )
        self.store.captures.save(cap)

        note = " · ".join(filter(None, [why, f"source: {locator}" if locator else None]))
        compiled = compiler.compile_route(
            self.store, capture_id=cap.id, capture_text=cap.text, learner_note=note,
        )
        task = task_service.emit(self.store, compiled)
        self.log.info(f"Captured {cap.id}; route task {task.id} emitted")
        return {
            "capture_id": cap.id,
            "tasks": [flows.task_ref(task)],
            "next": "fulfill the route task; the proposal then awaits confirmation "
                    "(dojo inbox confirm <capture-id>) unless capture.autofile is on",
        }

    def inbox(self) -> dict[str, Any]:
        """Lists captures still awaiting a home: unrouted (route task not yet
        fulfilled) or proposed (route landed, awaiting human confirmation).
        Text is truncated to the first line — the inbox is a triage view,
        not a reader."""
        captures = [c for c in self.store.captures.list() if c.status in ("unrouted", "proposed")]
        return {
            "captures": [
                {
                    "id": c.id,
                    "status": c.status,
                    "text": c.text.splitlines()[0][:80] if c.text else "",
                    "proposal": c.proposal,
                }
                for c in captures
            ],
            "next": "confirm/dismiss proposals: dojo inbox confirm|dismiss <capture-id>",
        }

    def inbox_confirm(self, capture_id: str) -> dict[str, Any]:
        """Accepts a capture's route proposal and files it (ADR 013): the
        capture becomes a Source attached to the proposed campaign/topic,
        ready to ground future generation.

        Raises:
            ValueError: unknown capture, or its route task hasn't produced a
                proposal yet.
        """
        from .filing import file_capture

        cap = self.store.captures.get(capture_id)
        if cap is None:
            raise ValueError(f"capture {capture_id} not found")
        if not cap.proposal:
            raise ValueError(f"capture {capture_id} has no route proposal yet — fulfill its route task first")
        filed = file_capture(self.store, cap, cap.proposal)
        self.log.info(f"Capture {capture_id} filed into {filed['campaign_id']}")
        return {**filed, "next": "the note is now a source; exercises can ground on it"}

    def inbox_dismiss(self, capture_id: str) -> dict[str, Any]:
        """Marks a capture dismissed. The file stays in the store (git is the
        archive) but leaves every inbox and routing view.

        Raises:
            ValueError: unknown capture id.
        """
        cap = self.store.captures.get(capture_id)
        if cap is None:
            raise ValueError(f"capture {capture_id} not found")
        cap.status = "dismissed"
        cap.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.captures.save(cap)
        return {"capture_id": capture_id, "status": "dismissed"}

    # ==========================================
    # Ownership: the learner model, inspectable / traceable / contestable
    # ==========================================
    def insights_list(self, campaign_id: str | None = None,
                      include_resolved: bool = False) -> dict[str, Any]:
        """The learner model, visible (ownership block, QUESTIONS 2026-07-09):
        every belief the system holds, in the model's recorded words, with
        age, evidence count and last update. Resolved insights appear under
        `include_resolved` — what you overcame is part of ownership. These
        are plain markdown files; editing them directly is first-class."""
        now = datetime.now(timezone.utc)
        campaigns = (
            [self.store.campaigns.get(campaign_id)] if campaign_id
            else self.store.campaigns.list()
        )
        if campaigns and campaigns[0] is None:
            raise ValueError(f"campaign {campaign_id} not found")
        out = []
        for camp in campaigns:
            rows = []
            for ins in self.store.insights.list(camp.id):
                if ins.status != "active" and not include_resolved:
                    continue
                rows.append({
                    "id": ins.id,
                    "key": ins.key,
                    "topic": ins.key.split(".")[0],
                    "description": (ins.description or "").splitlines()[0],
                    "status": ins.status,
                    "resolution": ins.resolution,
                    "age_days": round((now - datetime.fromisoformat(ins.created_at)).total_seconds() / 86400, 1),
                    "evidence_count": len(ins.sources),
                    "last_updated": ins.updated_at[:10],
                })
            rows.sort(key=lambda r: (r["topic"], r["key"]))
            out.append({"campaign_id": camp.id, "insights": rows})
        return {
            "campaigns": out,
            "note": "these are plain markdown files under campaigns/*/insights/ — editing them directly is first-class",
            "next": "receipts behind a belief: dojo insights show <id>; disagree: dojo insights resolve <id> --because \"...\"",
        }

    def _find_insight(self, insight_id: str):
        """(campaign_id, insight) for an insight id, scanning campaigns.

        Raises:
            ValueError: no campaign holds this insight id.
        """
        for camp in self.store.campaigns.list():
            ins = self.store.insights.get(camp.id, insight_id)
            if ins is not None:
                return camp.id, ins
        raise ValueError(f"insight {insight_id} not found")

    def insight_show(self, insight_id: str) -> dict[str, Any]:
        """The receipts card: every evidence attempt behind a belief — date,
        the prompt, the learner's VERBATIM answer, score, grader (I10) and
        error tag — plus its forward effect: how many exercises generation
        aimed at it. "We believe this because on these occasions you wrote
        this."

        Raises:
            ValueError: unknown insight id.
        """
        campaign_id, ins = self._find_insight(insight_id)
        receipts = []
        for att_id in ins.sources:
            att = self.store.attempts.get(campaign_id, att_id)
            if att is None:
                receipts.append({"attempt_id": att_id, "note": "attempt file no longer in the store"})
                continue
            receipts.append({
                "attempt_id": att_id,
                "date": att.created_at[:10],
                "prompt": att.prompt,
                "your_answer": att.user_answer,
                "score": att.score,
                "grader": att.grader,
                "error_tag": att.error_tag,
            })
        # Forward tracing: generation tasks stamp the insight keys they were
        # steered by; exercises carry their generation task id.
        targeting_tasks = {
            t.id for t in self.store.tasks.list()
            if t.kind == "exercise.generate"
            and t.campaign_id == campaign_id
            and ins.key in (t.context or {}).get("targeted_insights", [])
        }
        targeted = [
            ex for ex in self.store.exercises.list(campaign_id)
            if ex.generation_run in targeting_tasks
        ]
        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        return {
            "id": ins.id,
            "campaign_id": campaign_id,
            "key": ins.key,
            "status": ins.status,
            "description": ins.description,
            "resolution": ins.resolution,
            "receipts": receipts,
            # Full provenance chain: the reflection task that wrote this
            # belief keeps the model's verbatim submission in its trace.
            "generated_by": ins.generation_run,
            "effect": {
                "exercises_targeting": len(targeted),
                "last_7_days": sum(1 for ex in targeted if ex.created_at >= week_ago),
            },
            "next": (
                f"the model's own words behind it: dojo task show {ins.generation_run} --trace; "
                if ins.generation_run else ""
            ) + (
                "disagree? dojo insights resolve "
                f"{ins.id} --because \"<your words>\" — your reason outranks the evidence"
            ),
        }

    def insight_resolve(self, insight_id: str, because: str) -> dict[str, Any]:
        """Learner override — the highest authority in the system: resolves
        the belief and stores the reason VERBATIM; the next reflection reads
        it as learner-voice feedback (extract-never-enrich).

        Raises:
            ValueError: unknown insight, already resolved, or empty reason.
        """
        because = (because or "").strip()
        if not because:
            raise ValueError("give the reason in your own words: --because \"...\"")
        campaign_id, ins = self._find_insight(insight_id)
        if ins.status == "resolved":
            raise ValueError(f"insight {insight_id} is already resolved")
        ins.status = "resolved"
        ins.resolution = because
        ins.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.insights.save(campaign_id, ins)
        self.log.info(f"Insight {insight_id} resolved by the learner")
        return {
            "id": ins.id, "campaign_id": campaign_id, "status": "resolved",
            "resolution": because,
            "next": "your reason feeds the next reflection as its loudest feedback",
        }

    def campaign_list(self) -> dict[str, Any]:
        """Every campaign at a glance (ownership block): status, plan
        position, retention estimate (tagged estimate, I10), due count and
        idle days — the view that makes maintain/archive/extend decisions
        possible."""
        from . import packet as packet_mod

        now = datetime.now(timezone.utc)
        rows = []
        for camp in self.store.campaigns.list():
            exercises = [
                ex for ex in self.store.exercises.list(camp.id)
                if ex.quality not in packet_mod.EXCLUDED_QUALITIES
            ]
            tracked = [ex for ex in exercises if ex.kind == "recall" and ex.sr]
            retention = (
                sum(scheduling.retrievability(ex.sr, now) for ex in tracked) / len(tracked)
                if tracked else None
            )
            attempts = self.store.attempts.list(camp.id)
            last_touch = max((a.created_at for a in attempts), default=None)
            plan_len = len(camp.attack_plan)
            rows.append({
                "campaign_id": camp.id,
                "name": camp.name,
                "status": camp.status,
                "phase": f"{min(camp.active_phase_index + 1, plan_len)}/{plan_len}" if plan_len else "—",
                "complete": plan_len > 0 and camp.active_phase_index >= plan_len,
                "estimated_retention": None if retention is None else round(retention, 3),
                "due_now": sum(1 for ex in exercises if scheduling.is_due(ex.sr, now)),
                "days_idle": None if last_touch is None else round(
                    (now - datetime.fromisoformat(last_touch)).total_seconds() / 86400, 1),
            })
        return {
            "campaigns": rows,
            "next": "dojo campaign archive <id> leaves rotation (git keeps history); "
                    "extend one via dojo learn; retention figures are estimates",
        }

    def _find_topic(self, path: str, campaign_id: str | None) -> tuple[Campaign, dict[str, Any]]:
        """The (campaign, registry entry) for a topic path; campaign_id
        disambiguates when the same path exists in several campaigns."""
        hits = []
        for camp in self.store.campaigns.list():
            if campaign_id and camp.id != campaign_id:
                continue
            for t in camp.topics or []:
                if t.get("path") == path:
                    hits.append((camp, t))
        if not hits:
            raise ValueError(f"topic {path!r} is not registered"
                             + (f" in campaign {campaign_id!r}" if campaign_id else ""))
        if len(hits) > 1:
            raise ValueError(
                f"topic {path!r} exists in {len(hits)} campaigns — pass --campaign "
                f"({', '.join(c.id for c, _ in hits)})"
            )
        return hits[0]

    def topic_retire(self, path: str, because: str = "", campaign_id: str | None = None) -> dict[str, Any]:
        """The learner's care-exit (ADR 017 §6): reviews for this topic stop
        immediately — retention of what you no longer care about is noise,
        not diligence. Always reversible (`dojo topic revive`). Learner-
        initiated, so it applies without a gate and self-announces."""
        camp, entry = self._find_topic(path, campaign_id)
        if entry.get("retired"):
            return {"ok": True, "note": f"{path} is already retired", "campaign_id": camp.id}
        now = datetime.now(timezone.utc).isoformat()
        entry["retired"] = True
        entry["retired_reason"] = because or "learner request"
        entry["retired_at"] = now
        camp.pedagogical_journal.append({
            "timestamp": now,
            "action": "TOPIC_RETIRED",
            "trigger": "dojo topic retire (learner)",
            "hypothesis": f"{path}: {because or 'learner request'}",
            "topic_path": path,
            "status": "applied",
            "announced": True,  # the learner did it themselves — nothing to announce
        })
        camp.updated_at = now
        self.store.campaigns.save(camp)
        return {
            "ok": True, "campaign_id": camp.id, "topic_path": path,
            "next": f"reviews stopped; dojo topic revive {path} undoes this anytime",
        }

    def topic_revive(self, path: str, campaign_id: str | None = None) -> dict[str, Any]:
        """Reopens a retired topic: its memories resume their schedule where
        FSRS left them (overdue reviews surface honestly, debt-guarded as
        ever)."""
        camp, entry = self._find_topic(path, campaign_id)
        if not entry.get("retired"):
            return {"ok": True, "note": f"{path} is not retired", "campaign_id": camp.id}
        now = datetime.now(timezone.utc).isoformat()
        for key in ("retired", "retired_reason", "retired_at"):
            entry.pop(key, None)
        camp.pedagogical_journal.append({
            "timestamp": now,
            "action": "TOPIC_REVIVED",
            "trigger": "dojo topic revive (learner)",
            "hypothesis": f"{path}: reviews resume",
            "topic_path": path,
            "status": "applied",
            "announced": True,
        })
        camp.updated_at = now
        self.store.campaigns.save(camp)
        return {"ok": True, "campaign_id": camp.id, "topic_path": path,
                "next": "reviews resume on the honest schedule"}

    def campaign_archive(self, campaign_id: str) -> dict[str, Any]:
        """Archives a campaign — "I accept forgetting": it leaves every
        rotation; the files move to archive/ and git keeps the history.
        Always a human decision relayed as a command; reflection can only
        ever suggest it (authority grammar).

        Raises:
            ValueError: unknown campaign.
        """
        camp = self.store.campaigns.get(campaign_id)
        if camp is None:
            raise ValueError(f"campaign {campaign_id} not found")
        self.store.campaigns.archive(campaign_id)
        self.log.info(f"Campaign '{campaign_id}' archived by the learner")
        return {
            "campaign_id": campaign_id, "status": "archived",
            "next": "it is out of rotation; the files live under archive/campaigns/ and git remembers",
        }

    # ==========================================
    # Route-first learning entry (dojo learn)
    # ==========================================
    def learn(self, goal: str, new: bool = False) -> dict[str, Any]:
        """Route-first entry for a learning goal (QUESTIONS 2026-07-09): when
        campaigns exist, the goal routes against the registry FIRST — the
        cheapest task — so a near fit extends a campaign instead of spawning a
        semantic duplicate (the sibling of use-case audit A2's id collisions).
        `new=True` or an empty registry skips routing and emits the full
        campaign.plan task directly.

        Raises:
            ValueError: empty goal.
        """
        from .tasks import compiler, flows
        from .tasks import service as task_service

        goal = goal.strip()
        if not goal:
            raise ValueError("the goal is empty")
        # Maintenance campaigns stay routable — extending one is exactly the
        # lifecycle's "extend" door (it reopens execution).
        campaigns = [
            c for c in self.store.campaigns.list()
            if c.status in ("active", "maintenance")
        ]
        if new or not campaigns:
            task = flows.request_plan(
                self.store, goal=goal,
                existing_topics=flows.registry_topic_paths(self.store),
            )
            return {
                "mode": "plan",
                "tasks": [flows.task_ref(task)],
                "next": (
                    "fulfill the plan task; review the proposal and its "
                    "refinement_questions with the learner, then: "
                    f"dojo campaign create --from-task {task.id}"
                ),
            }
        compiled = compiler.compile_goal_route(self.store, goal=goal)
        task = task_service.emit(self.store, compiled)
        self.log.info(f"Goal routed against the registry; task {task.id} emitted")
        return {
            "mode": "route",
            "tasks": [flows.task_ref(task)],
            "next": (
                "fulfill the route task; its result either asks the learner "
                "extend-or-start-fresh (resolve with dojo learn extend|new "
                f"{task.id}) or hands off to a chained plan task"
            ),
        }

    def _fulfilled_goal_route(self, task_id: str) -> tuple[Any, dict[str, Any]]:
        """The (task, route proposal) behind a `dojo learn extend|new` verb.

        Raises:
            ValueError: unknown task, wrong kind, not fulfilled yet, or no
                route proposal on it.
        """
        task = self.store.tasks.get(task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        if task.kind != "goal.route":
            raise ValueError(f"{task_id} is a {task.kind} task, not goal.route")
        if task.status != "fulfilled":
            raise ValueError(f"task {task_id} is {task.status} — fulfill it first")
        route = ((task.context or {}).get("_applied") or {}).get("route")
        if not route:
            raise ValueError(f"task {task_id} carries no route proposal")
        return task, route

    def learn_extend(self, task_id: str) -> dict[str, Any]:
        """The learner's "extend" answer to a routed goal — deterministic, no
        AI: registers the topic if new and appends a focused phase, journaled
        as a minor additive plan change under change authority (PLAN_APPLIED
        with a pre-change snapshot: the next daily announces it once and
        `dojo plan revert` undoes it). Idempotent per task. When the current
        or a future phase already covers the topic, nothing changes
        (`already_covered`) — boosting, not restructuring, is the right tool.

        Raises:
            ValueError: bad/unfulfilled task, a propose_campaign route
                (nothing to extend), or the campaign vanished since routing.
        """
        from .tasks import authority

        task, route = self._fulfilled_goal_route(task_id)
        if route.get("action") not in ("attach", "new_topic"):
            raise ValueError(
                f"task {task_id} proposed {route.get('action')!r} — nothing to "
                "extend; its handoff plan task (or dojo learn new) covers it"
            )
        campaign = self.store.campaigns.get(route["campaign"])
        if campaign is None:
            raise ValueError(f"campaign {route['campaign']!r} no longer exists")
        topic_path = route["topic_path"]
        goal = task.context.get("goal", "")

        trigger = f"dojo learn extend (task {task_id})"
        if any(e.get("trigger") == trigger for e in campaign.pedagogical_journal):
            return {
                "campaign_id": campaign.id, "topic_path": topic_path,
                "already_applied": True,
                "next": "this extension was already applied — dojo daily practices it",
            }
        for i, phase in enumerate(campaign.attack_plan):
            if i >= campaign.active_phase_index and topic_path in phase.topics:
                return {
                    "campaign_id": campaign.id, "topic_path": topic_path,
                    "already_covered": True, "phase": phase.phase,
                    "next": (
                        f"already in the plan (phase {phase.phase}) — "
                        f"dojo campaign topic-boost {campaign.id} {topic_path} 2.0 "
                        "prioritizes it"
                    ),
                }

        now = datetime.now(timezone.utc).isoformat()
        if campaign.status == "maintenance":
            # The lifecycle's "extend" door: a new goal reopens execution.
            campaign.status = "active"
        if not any(t.get("path") == topic_path for t in campaign.topics):
            # A goal is an ability to build, not a fact to keep: skill lane.
            campaign.topics.append(
                {"path": topic_path, "kind": "skill", "summary": route.get("reason", "")}
            )
        snapshot = [p.model_dump() for p in campaign.attack_plan]
        next_phase = max((p.phase for p in campaign.attack_plan), default=0) + 1
        campaign.attack_plan.append(AttackPlanPhase(
            phase=next_phase,
            topics=[topic_path],
            criteria={"min_attempts": 3, "min_accuracy": 0.8},
            focus=f"learner goal: {goal}",
        ))
        campaign.pedagogical_journal.append({
            "timestamp": now,
            "action": authority.PLAN_APPLIED,
            "trigger": trigger,
            "hypothesis": f"extended with {topic_path} for the learner's goal: {goal}",
            "status": "applied",
            "plan_snapshot": snapshot,
            "announced": False,
        })
        campaign.updated_at = now
        self.store.campaigns.save(campaign)
        self.log.info(f"Campaign '{campaign.id}' extended with {topic_path} (learn)")
        return {
            "campaign_id": campaign.id, "topic_path": topic_path,
            "phase_appended": next_phase, "plan_change": "minor_additive",
            "undo": f"dojo plan revert --campaign {campaign.id}",
            "next": "dojo daily picks the new phase up; generation targets it as stock runs low",
        }

    def learn_new(self, task_id: str) -> dict[str, Any]:
        """The learner's "start fresh" answer to a routed goal: hands the goal
        to the full campaign.plan pipeline, telling the planner about the
        declined near fit so it scopes a SEPARATE campaign rather than a
        duplicate.

        Raises:
            ValueError: bad/unfulfilled task or no route proposal on it.
        """
        from .tasks import flows

        task, route = self._fulfilled_goal_route(task_id)
        if route.get("action") in ("attach", "new_topic"):
            notes = (
                f"the learner declined extending campaign {route['campaign']!r} — "
                "scope this as a separate campaign, not a duplicate of it"
            )
        else:
            notes = (
                f"router suggestion — name: {route.get('new_name')}; "
                f"mission: {route.get('new_mission')}"
            )
        plan_task = flows.request_plan(
            self.store, goal=task.context.get("goal", ""), context_notes=notes,
            existing_topics=flows.registry_topic_paths(self.store),
        )
        return {
            "mode": "plan",
            "tasks": [flows.task_ref(plan_task)],
            "next": (
                "fulfill the plan task; review the proposal and its "
                "refinement_questions with the learner, then: "
                f"dojo campaign create --from-task {plan_task.id}"
            ),
        }

    # ==========================================
    # Sources Operations
    # ==========================================
    def add_source(
        self,
        *,
        title: str,
        content: str,
        kind: str,
        path: str | None = None,
        mission: str | None = None,
        generate_candidates: bool = False,
        topic: str | None = None,
    ) -> dict[str, Any]:
        """Saves learning material as a Source; optionally starts generation.

        The save always succeeds standalone. With `generate_candidates`, the
        source must resolve to exactly ONE campaign — a `topic` prefix match,
        or an unambiguous single active campaign; anything else saves the
        source and returns a `note` asking for `--topic` rather than misfiling
        (use-case audit F1). On success the source is linked into the
        campaign's `sources_config` so it grounds ALL future generation for
        its topics (F2), and one grounded generation task is emitted.

        Args:
            title: Human name; also seeds the topic slug when none is given.
            content: The material itself (markdown/plain text, stored verbatim).
            kind: Freeform origin tag, e.g. "note", "article", "book".
            path: Optional original file path, recorded for provenance.
            mission: Optional statement of why this material matters.
            generate_candidates: Emit a generation task grounded on this source.
            topic: Dot-path that selects the target campaign and topic.

        Returns:
            `{source_id, title, kind, tasks, next|note}` — `tasks` non-empty
            only when generation was requested and a campaign resolved.
        """
        self.log.info(f"Adding source: '{title}' (kind={kind}, generate_candidates={generate_candidates})")
        source_id = f"src_{uuid.uuid4().hex[:8]}"

        source = Source(
            id=source_id,
            title=title,
            content=content,
            kind=kind,
            path=path,
            mission=mission,
        )
        self.store.sources.save(source)

        tasks = []
        if generate_candidates:
            from .tasks import flows
            from .tasks.grounding import resolve_source_context

            camps = [c for c in self.store.campaigns.list() if c.status == "active"]
            if not camps:
                return {
                    "source_id": source.id,
                    "title": source.title,
                    "kind": source.kind,
                    "tasks": [],
                    "note": "source saved; no campaign exists yet, so no generation was requested — "
                            "create a campaign first (dojo campaign plan \"<goal>\")",
                }
            # Deterministic resolution only — never guess a home for material
            # (use-case audit F1): a topic prefix match wins; a single campaign
            # is unambiguous; anything else asks instead of misfiling.
            if topic:
                matched = [
                    c for c in camps
                    if (c.topic_path and topic.startswith(c.topic_path))
                    or any(topic.startswith(t.get("path", "\x00")) for t in c.topics)
                ]
            else:
                matched = camps
            if len(matched) != 1:
                return {
                    "source_id": source.id,
                    "title": source.title,
                    "kind": source.kind,
                    "tasks": [],
                    "note": (
                        "source saved, but its campaign is ambiguous — re-run with "
                        "--topic <path> under one campaign's topics: "
                        + "; ".join(f"{c.id} ({c.topic_path or '?'})" for c in camps)
                    ),
                }
            campaign = matched[0]

            target_topic = topic or campaign.topic_path or slugify(title).replace("-", "_")

            # Link the source so it keeps grounding ALL future generation for
            # these topics (use-case audit F2) — trusted material must not be
            # used once on ingest day and forgotten.
            if not any(l.get("source_id") == source.id for l in campaign.sources_config):
                campaign.sources_config.append({
                    "source_id": source.id,
                    "purpose": "ingested material",
                    "topics": [target_topic],
                })
            if not any(t.get("path") == target_topic for t in campaign.topics):
                campaign.topics.append({"path": target_topic, "kind": "recall", "summary": ""})
            campaign.updated_at = datetime.now(timezone.utc).isoformat()
            self.store.campaigns.save(campaign)

            slice_text, _, _ = resolve_source_context(content, title, target_topic)
            task = flows.request_generation(
                self.store, campaign,
                topic_path=target_topic,
                n_items=3,
                source_slice=slice_text,
            )
            tasks.append(flows.task_ref(task))
            self.log.info(f"Emitted generation task {task.id} for source '{source_id}'")

        return {
            "source_id": source.id,
            "title": source.title,
            "kind": source.kind,
            "tasks": tasks,
            "next": (
                "fulfill the generation task, then review candidates (dojo source review)"
                if tasks else None
            ),
        }

    def list_sources(self) -> list[dict[str, Any]]:
        """All stored sources as dicts, including full content."""
        return [s.model_dump() for s in self.store.sources.list()]

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        """One source as a dict, or None if the id is unknown."""
        src = self.store.sources.get(source_id)
        return src.model_dump() if src else None

    def get_source_topics(self, source_id: str) -> list[dict[str, Any]]:
        """Candidate counts per topic path.

        Candidates don't record which source grounded them, so `source_id`
        cannot narrow the scan yet: counts cover ALL candidates across all
        campaigns. Honest limitation, not a filter.
        """
        topics: dict[str, int] = {}
        for camp in self.store.campaigns.list():
            for cand in self.store.candidates.list(camp.id):
                path = cand.topic_path
                topics[path] = topics.get(path, 0) + 1
        return [{"topic_path": k, "count": v} for k, v in topics.items()]

    def get_source_candidates(self, source_id: str, topic_path: str | None = None) -> list[dict[str, Any]]:
        """Candidates awaiting review, optionally filtered by exact topic path.

        Same limitation as `get_source_topics`: candidates carry no source
        provenance, so `source_id` does not narrow the result.
        """
        cands = []
        for camp in self.store.campaigns.list():
            for cand in self.store.candidates.list(camp.id):
                if topic_path and cand.topic_path != topic_path:
                    continue
                cands.append(cand.model_dump())
        return cands

    # ==========================================
    # Candidates & Exercises Operations
    # ==========================================
    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        """Finds a candidate by id across all campaigns, or None."""
        for camp in self.store.campaigns.list():
            cand = self.store.candidates.get(camp.id, candidate_id)
            if cand:
                return cand.model_dump()
        return None

    def save_candidate(
        self,
        candidate_id: str,
        prompt: str,
        topic_path: str,
        answer: str | None = None,
        rubric: str | None = None,
        difficulty: str = "intermediate",
    ) -> None:
        """Creates or overwrites a candidate by id, scoped to the FIRST
        campaign (or literal "default" when none exists). A manual-authoring
        escape hatch — the normal path is generation-task fulfillment via
        `task submit`."""
        # Default to the first campaign
        campaign_id = "default"
        camps = self.store.campaigns.list()
        if camps:
            campaign_id = camps[0].id

        cand = self.store.candidates.get(campaign_id, candidate_id)
        if not cand:
            cand = Candidate(
                id=candidate_id,
                prompt=prompt,
                topic_path=topic_path,
                answer=answer,
                rubric=rubric,
                difficulty=difficulty,
            )
        else:
            cand.prompt = prompt
            cand.topic_path = topic_path
            cand.answer = answer
            cand.rubric = rubric
            cand.difficulty = difficulty

        self.store.candidates.save(campaign_id, cand)

    def remove_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Deletes a candidate (rejection during review) and returns its last
        state.

        Raises:
            ValueError: no campaign holds a candidate with this id.
        """
        for camp in self.store.campaigns.list():
            cand = self.store.candidates.get(camp.id, candidate_id)
            if cand:
                self.store.candidates.delete(camp.id, candidate_id)
                return cand.model_dump()
        raise ValueError(f"Candidate {candidate_id} not found")

    def _enforce_queue_limit(self, campaign_id: str, limit: int = 30):
        """Keeps the LIVE queue at `limit` (OP #14): never-practiced stock
        retires first (oldest first); an exercise carrying FSRS memory is
        touched only when no unpracticed item is left — consolidation is
        never discarded to make room for fresh generation. Already-retired
        items don't count toward the limit (they used to, which re-archived
        live items on every promotion past 30 total files)."""
        from . import packet as packet_mod

        live = [
            ex for ex in self.store.exercises.list(campaign_id)
            if ex.quality not in packet_mod.RETIRED_QUALITIES
        ]
        if len(live) <= limit:
            return

        live.sort(key=lambda x: (x.sr is not None, x.created_at, x.id))
        for ex in live[: len(live) - limit]:
            ex.archived = True
            ex.quality = "archived"
            self.store.exercises.save(campaign_id, ex)
            self.log.info(f"Queue limit enforced: archived exercise '{ex.id}' in campaign '{campaign_id}'")

    def promote_candidate(self, candidate_id: str) -> dict[str, Any]:
        """Accepts a candidate into the practice rotation: it becomes an
        Exercise (same id, `candidate_id` kept for lineage), the candidate is
        deleted, and the campaign's queue limit is enforced (oldest exercises
        beyond 30 are archived).

        Raises:
            ValueError: no campaign holds a candidate with this id.
        """
        for camp in self.store.campaigns.list():
            cand = self.store.candidates.get(camp.id, candidate_id)
            if cand:
                # Promote to Exercise
                exercise = Exercise(
                    id=cand.id,
                    topic_path=cand.topic_path,
                    difficulty=cand.difficulty,
                    kind=cand.kind,
                    generation_run=cand.generation_run,
                    candidate_id=cand.id,
                    provenance=cand.provenance,
                    prompt=cand.prompt,
                    answer=cand.answer,
                    rubric=cand.rubric,
                    created_at=cand.created_at,
                )
                self.store.exercises.save(camp.id, exercise)
                self.store.candidates.delete(camp.id, candidate_id)
                self._enforce_queue_limit(camp.id)
                return exercise.model_dump()
        raise ValueError(f"Candidate {candidate_id} not found")

    def promote_source_topic(
        self, source_id: str, topic_path: str, limit: int | None = None
    ) -> dict[str, Any]:
        """Batch-promotes candidates matching an exact topic path, up to
        `limit`. Stops at the first campaign that yields any promotion
        (candidates carry no source provenance, so `source_id` does not
        narrow the scan). Returns `{promoted_count, exercises}`."""
        promoted = []
        for camp in self.store.campaigns.list():
            candidates = self.store.candidates.list(camp.id)
            count = 0
            for cand in candidates:
                if cand.topic_path == topic_path:
                    # Promote
                    ex = Exercise(
                        id=cand.id,
                        topic_path=cand.topic_path,
                        difficulty=cand.difficulty,
                        generation_run=cand.generation_run,
                        candidate_id=cand.id,
                        provenance=cand.provenance,
                        prompt=cand.prompt,
                        answer=cand.answer,
                        rubric=cand.rubric,
                        created_at=cand.created_at,
                    )
                    self.store.exercises.save(camp.id, ex)
                    self.store.candidates.delete(camp.id, cand.id)
                    promoted.append(ex.model_dump())
                    count += 1
                    if limit is not None and count >= limit:
                        break
            if promoted:
                self._enforce_queue_limit(camp.id)
                return {"promoted_count": len(promoted), "exercises": promoted}
        return {"promoted_count": 0, "exercises": []}

    # ==========================================
    # Practice Session Operations
    # ==========================================
    def start_practice_session(
        self,
        topic: str | None = None,
        limit: int = 5,
        reset: bool = False,
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        """Starts (or resumes) a manual practice session outside the daily
        packet — `dojo daily` is the preferred ritual; this is the targeted
        drill path.

        Resolution order for the campaign: explicit `campaign_id`, then
        topic-prefix match, then the first campaign. A reflection pass runs
        first so strategy/insights are current. An existing active session is
        returned as-is unless `reset` archives it. Exercises are drawn from
        the campaign's active phase topics, unattempted-first, oldest-first;
        when fewer than 3 are due, a replenishment generation task is emitted
        and the session proceeds with what exists (ADR 003b — never blocks
        on AI).

        Returns:
            `{is_new, session, tasks}`; `session` is None (with `next`) when
            nothing is due but generation is pending.

        Raises:
            ValueError: queue empty and no way to replenish (no campaign).
        """
        self.log.info(f"Starting practice session (topic={topic}, limit={limit}, reset={reset}, campaign_id={campaign_id})")

        # 1. Resolve matching campaign
        resolved_campaign = None
        if campaign_id:
            resolved_campaign = self.store.campaigns.get(campaign_id)
        elif topic:
            for c in self.store.campaigns.list():
                if c.topic_path == topic or (c.topic_path and topic.startswith(c.topic_path + ".")):
                    resolved_campaign = c
                    break
        if not resolved_campaign:
            camps = self.store.campaigns.list()
            if camps:
                resolved_campaign = camps[0]

        # 2. Trigger campaign reflection if appropriate
        if resolved_campaign:
            try:
                self.consolidate_learner_profile(campaign_id=resolved_campaign.id)
                # reload campaign details
                resolved_campaign = self.store.campaigns.get(resolved_campaign.id)
            except Exception as e:
                self.log.error(f"Error during consolidation: {e}")

        # 3. Handle active session lookup
        active_sess = self.store.sessions.get_active()
        if active_sess and not reset:
            return {
                "is_new": False,
                "session": active_sess.model_dump()
            }

        if active_sess and reset:
            active_sess.status = "completed"
            self.store.sessions.save_archived(active_sess)
            self.store.sessions.delete_active()

        # 4. Collect active topics & focus
        active_topics = []
        phase_focus = None
        if topic:
            active_topics = [topic]
        elif resolved_campaign:
            idx = resolved_campaign.active_phase_index
            plan = resolved_campaign.attack_plan
            if idx < len(plan):
                phase_def = plan[idx]
                active_topics = phase_def.topics
                phase_focus = phase_def.focus
            if not active_topics:
                active_topics = [resolved_campaign.topic_path] if resolved_campaign.topic_path else []
        else:
            active_topics = []

        target_topic = active_topics[0] if active_topics else "diagnostic"

        # 5. Check due count / retrieve exercises
        all_ex = []
        if resolved_campaign:
            all_ex = self.store.exercises.list(resolved_campaign.id)
        else:
            # Fallback scan all campaigns
            for c in self.store.campaigns.list():
                all_ex.extend(self.store.exercises.list(c.id))

        # Filter out archived / bad quality
        active_ex = [
            ex for ex in all_ex
            if ex.quality not in ("archived", "too_easy", "too_hard", "bad_quality")
        ]

        # Filter by active topics
        if active_topics:
            filtered = []
            for ex in active_ex:
                matches = False
                for t in active_topics:
                    if ex.topic_path == t or ex.topic_path.startswith(t + "."):
                        matches = True
                        break
                if matches:
                    filtered.append(ex)
        else:
            filtered = active_ex

        # Filter by unattempted (excluding non-forgot ones)
        attempts = []
        if resolved_campaign:
            attempts = self.store.attempts.list(resolved_campaign.id)
        else:
            for c in self.store.campaigns.list():
                attempts.extend(self.store.attempts.list(c.id))

        non_forgot_attempted_ids = {
            a.exercise_id for a in attempts if not a.skip_reason or a.skip_reason != "forgot"
        }

        # Resolve paths to stem names
        due_exercises = [
            ex for ex in filtered
            if ex.id not in non_forgot_attempted_ids
        ]

        # 6. Replenishment (ADR 003b via ADR 010): when the queue runs low,
        # emit a generation task and keep going — sessions never block on AI (I4).
        pending_tasks = []
        if len(due_exercises) < 3 and resolved_campaign:
            from .tasks import flows
            from .tasks.grounding import resolve_source_context

            strategy = resolved_campaign.strategy_profile
            is_diagnostic = (
                strategy.get("mode") == "diagnostic"
                or any(t.endswith(".diagnostic") for t in active_topics)
                # No evidence at all means calibrate first — the same
                # pedagogy-foundation rule the daily packet enforces
                # (needs_generation); a mode stamp can be missing, the
                # store's emptiness cannot.
                or (not all_ex and not attempts)
            )
            target_topic = (
                active_topics[0] if active_topics
                else (resolved_campaign.topic_path or "general")
            )
            if len(active_topics) > 1:
                # feed the thinnest topic first
                topic_counts = {
                    t: sum(1 for ex in all_ex if ex.topic_path == t or ex.topic_path.startswith(t + "."))
                    for t in active_topics
                }
                target_topic = min(active_topics, key=lambda t: topic_counts[t])

            source_slice = None
            if not is_diagnostic:
                for link in resolved_campaign.sources_config:
                    topics = link.get("topics") or []
                    if not topics or any(
                        target_topic == t or target_topic.startswith(t + ".") for t in topics
                    ):
                        full_source = self.store.sources.get(link["source_id"])
                        if full_source:
                            source_slice, _, _ = resolve_source_context(
                                full_source.content, full_source.title, target_topic or "", min_lines=100
                            )
                        break

            task = flows.request_generation(
                self.store, resolved_campaign,
                topic_path=target_topic,
                n_items=2 if is_diagnostic else 3,  # calibration stays short (pedagogy: 1-3)
                source_slice=source_slice, diagnostic=is_diagnostic,
                # Same recorded I2 auto-accept policy as daily replenishment
                # (J1): the learner asked to practice NOW — stock that lands
                # as candidates is invisible to the session builder and
                # starves the very session this task was emitted to feed
                # (owner field report 2026-07-17).
                auto_promote=not is_diagnostic,
            )
            pending_tasks.append(flows.task_ref(task))
            self.log.info(f"Queue low ({len(due_exercises)} due): emitted generation task {task.id}")

        due_exercises = sorted(due_exercises, key=lambda x: x.created_at)

        if not due_exercises:
            if pending_tasks:
                return {
                    "is_new": False,
                    "session": None,
                    "tasks": pending_tasks,
                    "next": "no exercises are due yet: fulfill the generation task(s), "
                            "then run start again",
                }
            raise ValueError("no active exercises in queue; ingest and queue sources first")

        selected = due_exercises[:limit]
        exercise_ids = [ex.id for ex in selected]

        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        ps = PracticeSession(
            id=session_id,
            status="active",
            exercise_ids=exercise_ids,
            current_index=0,
        )
        self.store.sessions.save_active(ps)

        return {
            "is_new": True,
            "session": ps.model_dump(),
            "tasks": pending_tasks,
        }

    def get_active_practice_session(self) -> dict[str, Any] | None:
        """The current active session as a dict, or None."""
        ps = self.store.sessions.get_active()
        return ps.model_dump() if ps else None

    def reveal_prompt(self, session_id: str | None = None) -> dict[str, Any]:
        """Reveals the current exercise's prompt and STARTS THE CLOCK:
        `started_at` is stamped on the session, and `submit_answer` measures
        latency from this moment (latency feeds FSRS calibration). Walking
        past the last exercise completes and archives the session.

        Args:
            session_id: Target a specific (possibly archived) session;
                default is the active one.

        Raises:
            ValueError: no session, session already completed, or the
                exercise file is missing from the store.
        """
        active = self.store.sessions.get_active()
        target_session = active
        if session_id:
            if active and active.id == session_id:
                target_session = active
            else:
                target_session = self.store.sessions.get_archived(session_id)

        if not target_session:
            raise ValueError("no active practice session; start one first")

        if target_session.status == "completed":
            raise ValueError(f"practice session {target_session.id} is already completed")

        idx = target_session.current_index
        exercise_ids = target_session.exercise_ids
        if idx >= len(exercise_ids):
            target_session.status = "completed"
            if target_session.id == active.id:
                self.store.sessions.save_archived(target_session)
                self.store.sessions.delete_active()
            else:
                self.store.sessions.save_archived(target_session)
            raise ValueError(f"practice session {target_session.id} is completed")

        exercise_id = exercise_ids[idx]
        # Scan campaigns to find where exercise exists
        ex = None
        for camp in self.store.campaigns.list():
            ex = self.store.exercises.get(camp.id, exercise_id)
            if ex:
                break

        if not ex:
            raise ValueError(f"error: exercise {exercise_id} not found in database")

        started_at = datetime.now(timezone.utc).isoformat()
        target_session.current_attempt_started_at = started_at
        if active and target_session.id == active.id:
            self.store.sessions.save_active(target_session)
        else:
            self.store.sessions.save_archived(target_session)

        out = {
            "session_id": target_session.id,
            "exercise_id": exercise_id,
            "index": idx,
            "total": len(exercise_ids),
            "prompt": ex.prompt,
            "topic_path": ex.topic_path,
            "difficulty": ex.difficulty,
            "started_at": started_at,
        }
        if ex.kind == "present":
            # A deliberate encoding event (ADR 017): the material IS the
            # answer — show it now; the learner confirms, nothing is graded.
            out["present"] = True
            out["material"] = ex.answer
            out["next"] = (
                "show the learner the prompt AND material together — this is "
                "study material, not a question; any acknowledgment submits it"
            )
        return out

    def submit_answer(self, user_answer: str, session_id: str | None = None) -> dict[str, Any]:
        """Records an attempt for the current exercise and advances the
        session.

        Scoring is a deterministic floor with AI as an emitted task, never a
        block (I4): diagnostic exercises auto-score 1.0 (calibration answers
        are information, not tests); an exact case-insensitive match on the
        stored answer scores 1.0; otherwise, if a rubric or answer exists,
        the score is PROVISIONAL 0.0 and a grade task is emitted — the real
        score lands via `task submit`, which also updates the FSRS schedule.
        Provisional scores never touch the schedule (a placeholder 0.0 would
        poison it). Latency runs from `reveal_prompt`.

        Returns:
            Result dict; when `pending_grade` is true, `tasks` holds the
            grade task the fulfiller must complete.

        Raises:
            ValueError: no session, completed session, missing exercise, or
                prompt not yet revealed.
        """
        self.log.info(f"Submitting answer (session_id={session_id}, user_answer_len={len(user_answer)})")
        active = self.store.sessions.get_active()
        target_session = active
        if session_id:
            if active and active.id == session_id:
                target_session = active
            else:
                target_session = self.store.sessions.get_archived(session_id)

        if not target_session:
            raise ValueError("no active practice session; start one first")

        if target_session.status == "completed":
            raise ValueError(f"practice session {target_session.id} is already completed")

        idx = target_session.current_index
        exercise_ids = target_session.exercise_ids
        if idx >= len(exercise_ids):
            target_session.status = "completed"
            if active and target_session.id == active.id:
                self.store.sessions.save_archived(target_session)
                self.store.sessions.delete_active()
            else:
                self.store.sessions.save_archived(target_session)
            raise ValueError(f"practice session {target_session.id} is completed")

        exercise_id = exercise_ids[idx]
        ex = None
        campaign_id = None
        for camp in self.store.campaigns.list():
            ex = self.store.exercises.get(camp.id, exercise_id)
            if ex:
                campaign_id = camp.id
                break

        if not ex or not campaign_id:
            raise ValueError(f"error: exercise {exercise_id} not found in database")

        started_at_str = target_session.current_attempt_started_at
        if not started_at_str:
            raise ValueError("prompt not revealed yet; run ready/reveal command first")

        started_at = datetime.fromisoformat(started_at_str)
        now = datetime.now(timezone.utc)
        latency = (now - started_at).total_seconds()
        if latency < 0:
            latency = 0.0

        user_ans = user_answer.strip()
        correct_ans = ex.answer

        # Deterministic scoring floor (I4); AI grading is an emitted task, never a block.
        pending_grade_task = None
        if ex.kind == "present":
            # Encoding confirmation (ADR 017): never graded, excluded from
            # accuracy (grader="exposure", pre-reflected), lands a fixed Good
            # on the topic memory, and the presentation is spent.
            score, grader = 1.0, "exposure"
        elif ex.quality == "diagnostic":
            score, grader = 1.0, "auto"  # calibration answers are information, not tests
        elif correct_ans and user_ans.lower() == correct_ans.strip().lower():
            score, grader = 1.0, "exact"
        elif ex.rubric or correct_ans:
            score, grader = 0.0, None  # provisional until the grade task lands
        else:
            score, grader = 1.0, "auto"  # nothing to grade against

        attempt_id = f"att_{uuid.uuid4().hex[:8]}"

        attempt = Attempt(
            id=attempt_id,
            session_id=target_session.id,
            exercise_id=exercise_id,
            campaign_id=campaign_id,
            score=score,
            grader=grader,
            reflected=(grader == "exposure"),  # information, never reflection evidence
            latency_seconds=latency,
            origin="extension" if target_session.origin == "extension" else None,
            user_answer=user_ans,
            prompt=ex.prompt,
        )
        self.store.attempts.save(campaign_id, attempt)

        if grader is None:
            from .tasks import flows

            campaign = self.store.campaigns.get(campaign_id)
            task = flows.request_grade(self.store, campaign, ex, attempt)
            pending_grade_task = flows.task_ref(task)
            self.log.info(f"Emitted grade task {task.id} for attempt {attempt_id}")
        elif grader == "exposure":
            # Presentation confirmed: initialize the topic memory (fixed
            # Good — never rate_for, which would read fast+1.0 as Easy and
            # overshoot the first retrieval), then spend the presentation.
            from .outcomes import land_exposure

            land_exposure(self.store, campaign_id, exercise_id)
            ex.quality = "spent"
            ex.updated_at = now.isoformat()
            self.store.exercises.save(campaign_id, ex)
        else:
            self._land_score(campaign_id, exercise_id, score=score, latency_seconds=latency)

        next_index = idx + 1
        is_completed = next_index >= len(exercise_ids)
        target_session.current_index = next_index
        target_session.current_attempt_started_at = ""
        target_session.status = "completed" if is_completed else "active"

        if active and target_session.id == active.id:
            if is_completed:
                self.store.sessions.save_archived(target_session)
                self.store.sessions.delete_active()
            else:
                self.store.sessions.save_active(target_session)
        else:
            self.store.sessions.save_archived(target_session)

        self.log.info(f"Answer submitted successfully: session_id={target_session.id}, exercise_id={exercise_id}, score={score}, latency={latency:.2f}s, status={target_session.status}")

        return {
            "session_id": target_session.id,
            "exercise_id": exercise_id,
            "campaign_id": campaign_id,
            "attempt_id": attempt_id,
            "score": score,
            "grader": grader,
            "pending_grade": pending_grade_task is not None,
            "tasks": [pending_grade_task] if pending_grade_task else [],
            "latency_seconds": latency,
            "user_answer": user_ans,
            "correct_answer": correct_ans,
            "is_session_completed": is_completed,
            "next_index": next_index,
            "total_exercises": len(exercise_ids),
        }

    def amend_previous_answer(
        self, user_answer: str, session_id: str | None = None, steps_back: int = 1,
        peek: bool = False,
    ) -> dict[str, Any]:
        """Replaces an earlier answer in the current session while its grade
        is still PENDING (owner-approved supersede semantics, 2026-07-13).
        The superseded answer is kept verbatim in `prior_answers` — both are
        the learner's words; provenance never deletes. The stale grade task
        is marked failed and a fresh one is emitted for the new answer.
        Landed scores refuse with the `dojo correct` door: FSRS is never
        double-fed. Repeated amendments of the same answer accumulate.
        `peek=True` validates and returns the target's prompt and current
        answer without changing anything (the human /back shows it before
        asking for the replacement).

        Returns:
            `{ok, attempt_id, prompt, superseded, tasks}` on success;
            `{ok, prompt, current_answer}` for a peek;
            `{ok: False, error, next?}` when the target can't be amended.
        """
        active = self.store.sessions.get_active()
        target_session = active
        if session_id and not (active and active.id == session_id):
            target_session = self.store.sessions.get_archived(session_id)
        if not target_session:
            # A session archives the instant its last answer lands, but its
            # grades are still pending in the end-of-session batch — that is
            # precisely when "wait, change my last answer" arrives. The most
            # recent completed session stays amendable (pending-grade checks
            # below still guard every target).
            archived = self.store.sessions.list_archived()
            if archived:
                target_session = max(archived, key=lambda s: s.created_at)
        if not target_session:
            return {"ok": False, "error": "no practice session to amend in"}
        if steps_back < 1:
            return {"ok": False, "error": "steps_back must be >= 1"}
        target_idx = target_session.current_index - steps_back
        if target_idx < 0:
            return {"ok": False, "error": "that's before this session started"}
        exercise_id = target_session.exercise_ids[target_idx]

        campaign_id, attempt = None, None
        for camp in self.store.campaigns.list():
            for a in reversed(self.store.attempts.list(camp.id)):
                if a.session_id == target_session.id and a.exercise_id == exercise_id:
                    campaign_id, attempt = camp.id, a
                    break
            if attempt:
                break
        if attempt is None:
            return {"ok": False, "error": f"no recorded answer for step -{steps_back} (was it skipped?)"}

        pending = attempt.grader is None and attempt.score == 0.0 and not attempt.skip_reason
        if not pending:
            hint = ("dojo correct adjusts a landed grade"
                    if attempt.grader in ("exact", "ai", "self", "auto")
                    else "study-card confirmations have nothing to amend")
            return {"ok": False, "error": "that answer's grade already landed", "next": hint}

        if peek:
            return {"ok": True, "prompt": attempt.prompt,
                    "current_answer": attempt.user_answer or ""}

        superseded = attempt.user_answer or ""
        attempt.prior_answers = [*attempt.prior_answers, superseded]
        attempt.user_answer = user_answer.strip()
        self.store.attempts.save(campaign_id, attempt)

        # Retire the stale grade task honestly; emit a fresh one for the new
        # answer. The old task's trace stays on disk (provenance).
        from .tasks import flows

        for t in self.store.tasks.list(filters={"status": "pending"}):
            if t.kind == "attempt.grade" and t.context.get("attempt_id") == attempt.id:
                t.status = "failed"
                t.error_history = [*t.error_history, "superseded: the learner amended this answer"]
                self.store.tasks.save(t)
        campaign = self.store.campaigns.get(campaign_id)
        exercise = self.store.exercises.get(campaign_id, exercise_id)
        task = flows.request_grade(self.store, campaign, exercise, attempt)
        self.log.info(f"Amended attempt {attempt.id} (step -{steps_back}); grade task {task.id} re-emitted")
        return {
            "ok": True,
            "attempt_id": attempt.id,
            "prompt": attempt.prompt,
            "superseded": superseded,
            "tasks": [flows.task_ref(task)],
            "next": "the new answer grades with the batch at session end",
        }

    # ==========================================
    # Progress & Metrics Operations
    # ==========================================
    def get_progress(self) -> dict[str, Any]:
        """Lifetime aggregates across all campaigns: attempt count, mean
        score, mean latency, and the 10 most recent attempts. For the richer
        per-campaign view (retention, due counts, token spend) use `stats`."""
        attempts = []
        for camp in self.store.campaigns.list():
            attempts.extend(self.store.attempts.list(camp.id))

        if not attempts:
            return {
                "total_attempts": 0,
                "average_score": 0.0,
                "average_latency_seconds": 0.0,
                "recent_attempts": []
            }

        total = len(attempts)
        avg_score = sum(a.score for a in attempts) / total
        avg_latency = sum(a.latency_seconds for a in attempts) / total

        # Return dict lists of attempts
        sorted_attempts = sorted(attempts, key=lambda x: x.created_at, reverse=True)
        return {
            "total_attempts": total,
            "average_score": avg_score,
            "average_latency_seconds": avg_latency,
            "recent_attempts": [a.model_dump() for a in sorted_attempts[:10]]
        }

    def get_due_count(self, topic: str | None = None) -> int:
        """Count of active exercises not yet meaningfully attempted (a
        `forgot` skip doesn't count as attempted), optionally under a topic
        prefix. This is the manual-session queue view, not FSRS due-ness —
        scheduled reviews are `packet`'s territory."""
        all_ex = []
        for c in self.store.campaigns.list():
            all_ex.extend(self.store.exercises.list(c.id))

        active_ex = [
            ex for ex in all_ex
            if ex.quality not in ("archived", "too_easy", "too_hard", "bad_quality")
        ]

        if topic:
            filtered = [
                ex for ex in active_ex
                if ex.topic_path == topic or ex.topic_path.startswith(topic + ".")
            ]
        else:
            filtered = active_ex

        attempts = []
        for c in self.store.campaigns.list():
            attempts.extend(self.store.attempts.list(c.id))

        non_forgot_attempted_ids = {
            a.exercise_id for a in attempts if not a.skip_reason or a.skip_reason != "forgot"
        }

        due_exercises = [
            ex for ex in filtered
            if ex.id not in non_forgot_attempted_ids
        ]
        return len(due_exercises)

    def get_learner_hypotheses(self, status: str = "active") -> list[dict[str, Any]]:
        """Insights (learner-model hypotheses, ADR 004) across all campaigns,
        filtered by status ("active" / "resolved" / …)."""
        insights = []
        for camp in self.store.campaigns.list():
            insights.extend(self.store.insights.list(camp.id, filters={"status": status}))
        return [ins.model_dump() for ins in insights]

    def save_learner_hypothesis(self, key: str, description: str, status: str = "active") -> dict[str, Any]:
        """Manually records an insight, scoped to the first campaign (or
        "default" when none exists). The normal path is reflection-task
        fulfillment; this is the escape hatch."""
        # Scoped to first campaign or default
        campaign_id = "default"
        camps = self.store.campaigns.list()
        if camps:
            campaign_id = camps[0].id

        insight_id = f"ins_{uuid.uuid4().hex[:8]}"
        insight = Insight(
            id=insight_id,
            key=key,
            description=description,
            status=status,
        )
        self.store.insights.save(campaign_id, insight)
        return insight.model_dump()

    def skip_active_exercise(self, reason: str, feedback: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        """Skips the current exercise, recording the reason as calibration
        evidence (ADR 014).

        `reason` drives two distinct updates: exercise QUALITY (`too_easy` /
        `too_hard` / `bad_quality` pull it from future rotation) and the FSRS
        MEMORY schedule — `too_easy` lands as an Easy review, `forgot` as
        Again (retrieval failed, so it comes back fast); archival reasons
        leave memory untouched. A 0-score attempt is always recorded.

        Raises:
            ValueError: no session, completed session, or missing exercise.
        """
        self.log.info(f"Skipping active exercise (session_id={session_id}, reason={reason})")
        active = self.store.sessions.get_active()
        target_session = active
        if session_id:
            if active and active.id == session_id:
                target_session = active
            else:
                target_session = self.store.sessions.get_archived(session_id)

        if not target_session:
            raise ValueError("no active practice session; start one first")

        if target_session.status == "completed":
            raise ValueError(f"practice session {target_session.id} is already completed")

        idx = target_session.current_index
        exercise_ids = target_session.exercise_ids
        if idx >= len(exercise_ids):
            target_session.status = "completed"
            if active and target_session.id == active.id:
                self.store.sessions.save_archived(target_session)
                self.store.sessions.delete_active()
            else:
                self.store.sessions.save_archived(target_session)
            raise ValueError(f"practice session {target_session.id} is completed")

        exercise_id = exercise_ids[idx]
        ex = None
        campaign_id = None
        for camp in self.store.campaigns.list():
            ex = self.store.exercises.get(camp.id, exercise_id)
            if ex:
                campaign_id = camp.id
                break

        if not ex or not campaign_id:
            raise ValueError(f"error: exercise {exercise_id} not found in database")

        started_at_str = target_session.current_attempt_started_at
        latency = 0.0
        if started_at_str:
            started_at = datetime.fromisoformat(started_at_str)
            now = datetime.now(timezone.utc)
            latency = (now - started_at).total_seconds()
            if latency < 0:
                latency = 0.0

        attempt_id = f"att_{uuid.uuid4().hex[:8]}"

        # If user skips, score matches the difficulty calibration signal: e.g. 0.0 score, marked as skipped
        attempt = Attempt(
            id=attempt_id,
            session_id=target_session.id,
            exercise_id=exercise_id,
            campaign_id=campaign_id,
            score=0.0,
            latency_seconds=latency,
            origin="extension" if target_session.origin == "extension" else None,
            skip_reason=reason,
            feedback=feedback,
            prompt=ex.prompt,
        )
        self.store.attempts.save(campaign_id, attempt)

        # Update exercise quality based on skip reason
        if reason == "too_easy":
            ex.quality = "too_easy"
        elif reason == "too_hard":
            ex.quality = "too_hard"
        elif reason == "bad_quality":
            ex.quality = "bad_quality"
        self.store.exercises.save(campaign_id, ex)

        # Skips are calibration evidence (ADR 014): too_easy → Easy review;
        # forgot → Again (retrieval failed, comes back fast). Archival reasons
        # (too_hard/bad_quality) leave rotation, so no memory update. Landed
        # after the quality save so the sr write is the last one (no stale
        #-copy clobber).
        if reason in ("too_easy", "forgot"):
            self._land_score(campaign_id, exercise_id, score=0.0, skip_reason=reason)

        next_index = idx + 1
        is_completed = next_index >= len(exercise_ids)
        target_session.current_index = next_index
        target_session.current_attempt_started_at = ""
        target_session.status = "completed" if is_completed else "active"

        if active and target_session.id == active.id:
            if is_completed:
                self.store.sessions.save_archived(target_session)
                self.store.sessions.delete_active()
            else:
                self.store.sessions.save_active(target_session)
        else:
            self.store.sessions.save_archived(target_session)

        return {
            "session_id": target_session.id,
            "exercise_id": exercise_id,
            "attempt_id": attempt_id,
            "score": 0.0,
            "latency_seconds": latency,
            "is_session_completed": is_completed,
            "next_index": next_index,
            "total_exercises": len(exercise_ids),
        }

    def correct_last_attempt(self, score: float, feedback: str | None = None) -> dict[str, Any]:
        """Human override of the most recent attempt's score — the highest
        grading authority (I10); `grader` becomes "self". The corrected score
        lands as an ADDITIONAL FSRS review (exact undo would need an sr
        snapshot per attempt — ledgered in OPEN-PROBLEMS #13).

        Raises:
            ValueError: no attempts exist anywhere.
        """
        # Resolve latest attempt across all campaigns
        all_attempts = []
        for camp in self.store.campaigns.list():
            all_attempts.extend(self.store.attempts.list(camp.id))

        if not all_attempts:
            raise ValueError("no recent attempts found to correct")

        # Sort chronologically to get the latest
        all_attempts = sorted(all_attempts, key=lambda x: x.created_at, reverse=True)
        latest_att = all_attempts[0]

        campaign_id = latest_att.campaign_id

        latest_att.score = score
        latest_att.grader = "self"  # human override is the highest authority (I10)
        if feedback is not None:
            latest_att.feedback = feedback
        self.store.attempts.save(campaign_id, latest_att)

        # The corrected score lands as an additional review. Exact undo of the
        # previous review would need an sr snapshot per attempt — ledgered in
        # OPEN-PROBLEMS; the extra review is monotone-safe and conservative.
        self._land_score(
            campaign_id, latest_att.exercise_id,
            score=score, latency_seconds=latest_att.latency_seconds,
        )

        return latest_att.model_dump()

    def add_learner_feedback(self, comment: str, campaign_id: str | None = None) -> dict[str, Any]:
        """Stores a freeform learner comment as a raw `feedback.user.*`
        insight (ADR 004 raw-to-refined): the next reflection distills it into
        strategy. The user's words are stored verbatim — extract, never
        enrich. Defaults to the first campaign."""
        self.log.info(f"Adding user feedback: '{comment}'")
        # Resolve target campaign
        resolved_id = campaign_id
        if not resolved_id:
            camps = self.store.campaigns.list()
            if camps:
                resolved_id = camps[0].id
            else:
                resolved_id = "default"

        camp = self.store.campaigns.get(resolved_id)
        topic_path = camp.topic_path if camp else None

        insight_id = f"ins_feedback_{uuid.uuid4().hex[:8]}"
        # Standard "Raw-to-Refined" feedback key as defined in ADR 004
        insight = Insight(
            id=insight_id,
            key=f"feedback.user.{uuid.uuid4().hex[:8]}",
            description=comment,
            status="active",
            topic_path=topic_path,
        )
        self.store.insights.save(resolved_id, insight)
        return insight.model_dump()

    # ==========================================
    # Reflection & Consolidation logic
    # ==========================================
    def reflect_campaign(self, campaign_id: str | None = None) -> dict[str, Any]:
        """Alias retained for the CLI verb `dojo reflect`."""
        return self.consolidate_learner_profile(campaign_id=campaign_id)

    def consolidate_learner_profile(self, campaign_id: str | None = None) -> dict[str, Any]:
        """Emits reflection tasks (ADR 010) for campaigns with unreflected
        evidence. Never blocks on AI: fulfillers apply results via task submit,
        where apply_reflect owns insight/strategy/plan mutation under rails."""
        from .tasks import flows

        if campaign_id:
            campaigns = [self.store.campaigns.get(campaign_id)]
            if campaigns[0] is None:
                raise ValueError(f"campaign {campaign_id} not found")
        else:
            campaigns = self.store.campaigns.list()

        tasks, skipped = [], []
        for camp in campaigns:
            task = flows.request_reflection(self.store, camp.id)
            if task:
                tasks.append(flows.task_ref(task))
            else:
                skipped.append({"campaign_id": camp.id, "reason": "no unreflected attempts"})
            self._evaluate_campaign_phase_advancement(camp)

        return {
            "status": "tasks_emitted" if tasks else "nothing_to_reflect",
            "tasks": tasks,
            "skipped": skipped,
            "next": (
                "fulfill each task: read its prompt (dojo task show <id> --prompt), "
                "produce the JSON it asks for, then submit it (dojo task submit <id>)"
            ) if tasks else None,
        }

    def _evaluate_campaign_phase_advancement(self, campaign: Campaign) -> None:
        attack_plan = campaign.attack_plan
        if not attack_plan:
            return

        advanced = False
        while campaign.active_phase_index < len(attack_plan):
            phase_idx = campaign.active_phase_index
            phase_def = attack_plan[phase_idx]

            criteria = phase_def.criteria
            phase_topics = phase_def.topics

            min_attempts = criteria.min_attempts
            min_accuracy = criteria.min_accuracy

            if not phase_topics:
                campaign.active_phase_index += 1
                advanced = True
                continue

            attempts = self.store.attempts.list(campaign.id)
            phase_attempts = []
            for a in attempts:
                if a.skip_reason and a.skip_reason != "forgot":
                    continue
                if a.grader is None and a.score == 0.0 and not a.skip_reason:
                    continue  # provisional (grade pending) — not evidence yet
                if a.grader == "exposure":
                    continue  # encoding event (ADR 017) — information, never mastery evidence
                # Load corresponding exercise
                ex = self.store.exercises.get(campaign.id, a.exercise_id)
                if ex:
                    for t in phase_topics:
                        if ex.topic_path == t or ex.topic_path.startswith(t + "."):
                            phase_attempts.append(a)
                            break

            attempts_count = len(phase_attempts)
            if attempts_count < min_attempts:
                break

            # Windowed criteria (owner question 2026-07-09, ADR 008 style):
            # accuracy is measured over the most recent 2×min_attempts phase
            # attempts, not the lifetime mean — a rough start ages out, so the
            # end state is reachable in time proportional to CURRENT ability.
            window = phase_attempts[-(2 * min_attempts):]
            average_score = sum(a.score for a in window) / len(window)

            if average_score < min_accuracy:
                break

            campaign.active_phase_index += 1
            advanced = True
            if phase_idx == 0 and campaign.strategy_profile.get("mode") == "diagnostic":
                # Calibration is over — nothing else ever clears the stamp
                # (reflect only writes difficulty/scaffolding), and a campaign
                # stuck in diagnostic mode replenishes diagnostics forever.
                campaign.strategy_profile["mode"] = "practice"
            self.log.info(f"Campaign '{campaign.id}' ('{campaign.name}') advanced to phase {campaign.active_phase_index} (mastered phase {phase_idx})")

            # Lean entry (ADR 018): the trigger line carries the numbers; no
            # surface ever read the plan/syllabus/hypotheses snapshots that
            # used to be embedded here — git history is the archive.
            campaign.pedagogical_journal.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_phase_index": phase_idx,
                "action": "PHASE_ADVANCE",
                "trigger": f"Passed Phase {phase_idx} criteria ({attempts_count} attempts, {average_score*100:.1f}% accuracy)",
                "hypothesis": f"User demonstrated mastery of topics: {', '.join(phase_topics)}",
                "status": "resolved",
            })

        # Completion is deterministic and must be OBSERVED (owner question
        # 2026-07-09: before this, a finished campaign silently kept
        # practicing/replenishing forever). Default door: maintenance
        # (ADR 005 — no new material, retention trickle only); daily
        # announces once with the other doors (archive / extend).
        completed = (
            campaign.active_phase_index >= len(attack_plan)
            and campaign.status == "active"
        )
        if completed:
            campaign.status = "maintenance"
            campaign.pedagogical_journal.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "CAMPAIGN_COMPLETE",
                "trigger": "all plan phases passed (deterministic: active_phase_index ≥ plan length)",
                "hypothesis": "campaign complete — maintenance by default (reviews keep coming, no new material); archive or extend are the other doors",
                "status": "applied",
                "announced": False,
            })
            self.log.info(f"Campaign '{campaign.id}' complete → maintenance")

        if advanced or completed:
            campaign.updated_at = datetime.now(timezone.utc).isoformat()
            self.store.campaigns.save(campaign)



    def save_config(self, key: str, value: str) -> dict[str, Any]:
        """Sets one config key (e.g. `daily.packet_size`, `capture.autofile`)
        in the store's config file. Values are strings; consumers coerce."""
        self.store.configs.set(key, value)
        return {"key": key, "value": value}

    def get_config(self, key: str) -> str | None:
        """One config value, or None when unset."""
        return self.store.configs.get(key)

    def list_configs(self) -> dict[str, str]:
        """Every stored config key/value, stringified."""
        config = self.store.configs._read_config()
        return {str(k): str(v) for k, v in config.items()}

    # ==========================================
    # System Metadata / Helper Operations
    # ==========================================
    def get_all_topic_paths(self) -> list[str]:
        """Every dot-path topic in use (campaign roots + exercise topics),
        sorted."""
        topics = set()
        for camp in self.store.campaigns.list():
            if camp.topic_path:
                topics.add(camp.topic_path)
            for ex in self.store.exercises.list(camp.id):
                topics.add(ex.topic_path)
        return sorted(list(topics))

    def format_topic_tree(self, flat_paths: list[str]) -> str:
        """Renders dot-paths ("git.rebase.interactive") as an indented
        markdown bullet tree for display."""
        tree = {}
        for path in flat_paths:
            parts = path.split(".")
            curr = tree
            for part in parts:
                curr = curr.setdefault(part, {})

        def _render(node, indent=0):
            lines = []
            for k, v in sorted(node.items()):
                lines.append(f"{'  ' * indent}- {k}")
                if v:
                    lines.extend(_render(v, indent + 1))
            return lines

        return "\n".join(_render(tree))

    # ==========================================
    # Plan change authority (QUESTIONS.md 2026-07-09): the plan is a contract
    # ==========================================
    def _resolve_plan_campaign(self, campaign_id: str | None, *, having) -> Campaign:
        """One campaign for a plan command: explicit id, or the single active
        campaign satisfying `having` (a predicate). Ambiguity is an error that
        lists the choices instead of guessing."""
        if campaign_id:
            camp = self.store.campaigns.get(campaign_id)
            if camp is None:
                raise ValueError(f"campaign {campaign_id} not found")
            return camp
        matches = [c for c in self.store.campaigns.list() if c.status == "active" and having(c)]
        if len(matches) != 1:
            raise ValueError(
                "specify --campaign: "
                + (", ".join(c.id for c in matches) if matches else "no campaign qualifies")
            )
        return matches[0]

    def plan_status(self, campaign_id: str | None = None) -> dict[str, Any]:
        """Each campaign's plan-authority state: the current plan, any pending
        AI-proposed restructure, and whether an applied change can still be
        reverted."""
        from .tasks import authority

        campaigns = (
            [self.store.campaigns.get(campaign_id)] if campaign_id
            else self.store.campaigns.list()
        )
        if campaigns and campaigns[0] is None:
            raise ValueError(f"campaign {campaign_id} not found")
        out = []
        for camp in campaigns:
            pending = authority.pending_proposal(camp)
            out.append({
                "campaign_id": camp.id,
                "current_plan": [p.model_dump() for p in camp.attack_plan],
                "pending_proposal": None if pending is None else {
                    "reason": pending.get("hypothesis"),
                    "proposed_phases": pending.get("proposed_phases"),
                    "since": pending.get("timestamp"),
                },
                "revertable": authority.last_revertable(camp) is not None,
            })
        return {"campaigns": out}

    def plan_confirm(self, campaign_id: str | None = None) -> dict[str, Any]:
        """Accepts the pending AI-proposed plan: the proposal becomes the
        attack plan AND the new confirmed baseline (anti-drip resets to the
        learner's latest explicit yes).

        Raises:
            ValueError: no/ambiguous campaign, or nothing is pending.
        """
        from .tasks import authority

        camp = self._resolve_plan_campaign(
            campaign_id, having=lambda c: authority.pending_proposal(c) is not None
        )
        pending = authority.pending_proposal(camp)
        if pending is None:
            raise ValueError(f"campaign {camp.id} has no pending plan proposal")
        now = datetime.now(timezone.utc).isoformat()
        pending["status"] = "accepted"
        camp.attack_plan = [AttackPlanPhase.model_validate(p) for p in pending["proposed_phases"]]
        # A confirmed restructure may schedule topics the registry has never
        # seen — register them (skill lane) or generation will never stock
        # them and the phase stalls as a ghost (owner audit 2026-07-09).
        from .tasks.service import register_phase_topics

        register_phase_topics(
            self.store, camp, camp.attack_plan,
            reason=str(pending.get("hypothesis") or "confirmed plan restructure"),
        )
        camp.pedagogical_journal.append({
            "timestamp": now,
            "action": authority.PLAN_CONFIRMED,
            "trigger": "dojo plan confirm",
            "hypothesis": pending.get("hypothesis"),
            "status": "applied",
            "plan_snapshot": [p.model_dump() for p in camp.attack_plan],
        })
        camp.updated_at = now
        self.store.campaigns.save(camp)
        self.log.info(f"Plan proposal accepted for campaign '{camp.id}'")
        return {"campaign_id": camp.id, "status": "confirmed",
                "plan": [p.model_dump() for p in camp.attack_plan]}

    def plan_reject(self, campaign_id: str | None = None) -> dict[str, Any]:
        """Declines the pending proposal; the plan and baseline stay exactly
        as they were. The rejection stays in the journal as evidence.

        Raises:
            ValueError: no/ambiguous campaign, or nothing is pending.
        """
        from .tasks import authority

        camp = self._resolve_plan_campaign(
            campaign_id, having=lambda c: authority.pending_proposal(c) is not None
        )
        pending = authority.pending_proposal(camp)
        if pending is None:
            raise ValueError(f"campaign {camp.id} has no pending plan proposal")
        pending["status"] = "rejected"
        camp.updated_at = datetime.now(timezone.utc).isoformat()
        self.store.campaigns.save(camp)
        return {"campaign_id": camp.id, "status": "rejected"}

    def plan_revert(self, campaign_id: str | None = None) -> dict[str, Any]:
        """Undoes the most recent auto-applied plan change (Tier 1): restores
        its pre-change snapshot, which also becomes the confirmed baseline.

        Raises:
            ValueError: no/ambiguous campaign, or nothing left to revert.
        """
        from .tasks import authority

        camp = self._resolve_plan_campaign(
            campaign_id, having=lambda c: authority.last_revertable(c) is not None
        )
        entry = authority.last_revertable(camp)
        if entry is None:
            raise ValueError(f"campaign {camp.id} has no revertable plan change")
        now = datetime.now(timezone.utc).isoformat()
        entry["status"] = "reverted"
        camp.attack_plan = [AttackPlanPhase.model_validate(p) for p in entry["plan_snapshot"]]
        camp.pedagogical_journal.append({
            "timestamp": now,
            "action": authority.PLAN_REVERTED,
            "trigger": "dojo plan revert",
            "hypothesis": f"learner reverted: {entry.get('hypothesis')}",
            "status": "applied",
            "plan_snapshot": [p.model_dump() for p in camp.attack_plan],
        })
        camp.updated_at = now
        self.store.campaigns.save(camp)
        return {"campaign_id": camp.id, "status": "reverted",
                "plan": [p.model_dump() for p in camp.attack_plan]}

    _TASK_ID_RE = re.compile(r"tsk_[0-9a-f]{8}")

    def _referenced_task_ids(self) -> set[str]:
        """Every task id some piece of learning state points at — these carry
        PROVENANCE (the model's words behind an insight, item, score, or plan
        change) and are never housekept away."""
        referenced: set[str] = set()
        for camp in self.store.campaigns.list():
            for ins in self.store.insights.list(camp.id):
                if ins.generation_run:
                    referenced.add(ins.generation_run)
            for ex in self.store.exercises.list(camp.id):
                if ex.generation_run:
                    referenced.add(ex.generation_run)
            for cand in self.store.candidates.list(camp.id):
                if cand.generation_run:
                    referenced.add(cand.generation_run)
            for att in self.store.attempts.list(camp.id):
                if att.grade_run:
                    referenced.add(att.grade_run)
            for entry in camp.pedagogical_journal:
                for field in ("trigger", "hypothesis"):
                    referenced.update(self._TASK_ID_RE.findall(str(entry.get(field, ""))))
        for cap in self.store.captures.list():
            if cap.proposal and cap.proposal.get("task_id"):
                referenced.add(cap.proposal["task_id"])
        return referenced

    def _task_housekeeping(self, now: datetime) -> int:
        """Deletes spent task files (delete-over-retain: git is the archive):
        fulfilled/failed tasks older than `tasks.retention_days` (default 14)
        that nothing references. Pending tasks and every provenance-bearing
        task (insight/exercise/grade/journal/capture pointers) are untouchable
        regardless of age, so `--trace` receipts keep working. Returns the
        number removed."""
        retention = float(self.store.configs.get_value("tasks.retention_days", 14))
        if retention <= 0:
            return 0
        cutoff = now - timedelta(days=retention)
        referenced = None  # computed lazily: most days there is nothing old
        removed = 0
        for task in self.store.tasks.list():
            if task.status == "pending":
                continue
            try:
                updated = datetime.fromisoformat(task.updated_at)
            except (TypeError, ValueError):
                continue
            if updated > cutoff:
                continue
            if referenced is None:
                referenced = self._referenced_task_ids()
            if task.id in referenced:
                continue
            self.store.tasks.delete(task.id)
            removed += 1
        if removed:
            self.log.info(f"Task housekeeping: {removed} spent task file(s) deleted (git keeps history)")
        return removed

    def _plan_notices(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """(pending proposals, unannounced applied changes) across active
        campaigns — daily's surfacing feed. Proposals repeat until resolved;
        applied changes announce exactly once (flag flipped here)."""
        from .tasks import authority

        proposals, changes = [], []
        for camp in self.store.campaigns.list():
            if camp.status != "active":
                continue
            pending = authority.pending_proposal(camp)
            if pending:
                proposals.append({
                    "campaign_id": camp.id,
                    "reason": pending.get("hypothesis"),
                    "phases": len(pending.get("proposed_phases") or []),
                    "next": f"dojo plan show --campaign {camp.id}, then dojo plan confirm|reject",
                })
            dirty = False
            for e in camp.pedagogical_journal:
                if e.get("action") == authority.PLAN_APPLIED and not e.get("announced", True):
                    changes.append({
                        "campaign_id": camp.id,
                        "reason": e.get("hypothesis"),
                        "undo": f"dojo plan revert --campaign {camp.id}",
                    })
                    e["announced"] = True
                    dirty = True
            if dirty:
                camp.updated_at = datetime.now(timezone.utc).isoformat()
                self.store.campaigns.save(camp)
        return proposals, changes

    def _ownership_notices(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """(insight notices, campaign completions) — announce-once feeds for
        daily (ownership block): Tier-0 insight changes apply silently but
        never invisibly, and a finished campaign's three doors (maintain /
        archive / extend) are stated exactly once."""
        insight_notes, completions = [], []
        for camp in self.store.campaigns.list():
            dirty = False
            for e in camp.pedagogical_journal:
                if e.get("announced", True):
                    continue
                if e.get("action") == "REFLECT" and e.get("insights_changed"):
                    ch = e["insights_changed"]
                    insight_notes.append({
                        "campaign_id": camp.id,
                        **ch,
                        "next": "reflection updated beliefs about you — dojo insights shows them, with receipts",
                    })
                    e["announced"] = True
                    dirty = True
                elif e.get("action") == "TOPIC_RETIRED":
                    insight_notes.append({
                        "campaign_id": camp.id,
                        "topic_retired": e.get("topic_path"),
                        "reason": e.get("hypothesis"),
                        "next": (
                            f"reviews for {e.get('topic_path')} stopped — "
                            f"dojo topic revive {e.get('topic_path')} brings them back"
                        ),
                    })
                    e["announced"] = True
                    dirty = True
                elif e.get("action") == "CAMPAIGN_COMPLETE":
                    completions.append({
                        "campaign_id": camp.id,
                        "status": camp.status,
                        "next": (
                            f"{camp.name} is complete — it is now in maintenance "
                            "(reviews continue, no new material). Other doors: "
                            f"dojo campaign archive {camp.id} (accept forgetting) "
                            "or extend it with a new goal via dojo learn"
                        ),
                    })
                    e["announced"] = True
                    dirty = True
            if dirty:
                camp.updated_at = datetime.now(timezone.utc).isoformat()
                self.store.campaigns.save(camp)
        return insight_notes, completions

    def _idle_campaigns(self, now: datetime) -> list[dict[str, Any]]:
        """Active campaigns with practice history that have sat untouched
        past `campaign.idle_days` (default 14) — a neutral observation with
        doors, never guilt: no counters, no streaks, just the fact and the
        two honest exits."""
        from . import packet as packet_mod

        threshold = float(self.store.configs.get_value("campaign.idle_days", 14))
        idle = []
        for camp in self.store.campaigns.list():
            if camp.status != "active":
                continue
            attempts = self.store.attempts.list(camp.id)
            if not attempts:
                continue  # never practiced is "new", not "idle"
            days = packet_mod._days_since_touch(camp.id, self.store, now)
            if days >= threshold:
                idle.append({
                    "campaign_id": camp.id,
                    "days_idle": round(days, 1),
                    "next": f"still relevant? dojo learn extends it; done with it? dojo campaign archive {camp.id}",
                })
        return idle

    # ==========================================
    # Campaign Management Operations
    # ==========================================
    def create_campaign(
        self,
        *,
        name: str,
        topic_path: str,
        mission: str,
        source_id: str | None = None,
        syllabus_markdown: str | None = None,
    ) -> dict[str, Any]:
        """Creates a campaign — the pedagogical director for a learning goal
        (ADR 002).

        The id comes from the NAME, suffixed `-2`, `-3`… on collision so an
        existing campaign is never silently overwritten (use-case audit A2).
        Ships with a one-phase calibration attack plan (3 attempts @ 80%),
        a default practice strategy, an initial journal entry, and a stub
        syllabus unless `syllabus_markdown` is given.

        Args:
            name: Human title; source of the id slug.
            topic_path: Root dot-path this campaign owns.
            mission: Why the learner cares — grounds generation and reflection.
            source_id: Optional source to link as syllabus reference.
            syllabus_markdown: Optional full syllabus; a stub is written otherwise.
        """
        self.log.info(f"Creating campaign: '{name}' (topic_path={topic_path})")
        # Id from the NAME (distinctive), never silently overwriting an existing
        # campaign (use-case audit A2: topic-root ids collided — a second
        # git-adjacent campaign would have destroyed the first). Archived ids
        # count as taken too (owner 2026-07-15): re-archiving a reused id
        # would clobber the earlier archive's history. When the id suffixes,
        # the display name follows ("French (2)") so two campaigns never
        # read identically in any list.
        def _id_taken(cid: str) -> bool:
            if self.store.campaigns.get(cid) is not None:
                return True
            return (self.store.dojo_dir / "archive" / "campaigns" / f"camp_{cid}").exists()

        campaign_id = slugify(name) or slugify(topic_path)
        if _id_taken(campaign_id):
            suffix = 2
            while _id_taken(f"{campaign_id}-{suffix}"):
                suffix += 1
            campaign_id = f"{campaign_id}-{suffix}"
            name = f"{name} ({suffix})"

        # Default attack plan
        plan = [
            AttackPlanPhase(
                phase=1,
                topics=[topic_path],
                criteria={"min_attempts": 3, "min_accuracy": 0.8},
                focus="Initial Calibration Phase"
            )
        ]

        # Default strategy profile
        strategy = {"mode": "practice", "difficulty": "intermediate", "scaffolding": "medium"}

        sources_config = []
        if source_id:
            sources_config = [{"source_id": source_id, "purpose": "Standalone syllabus reference", "topics": []}]

        campaign = Campaign(
            id=campaign_id,
            name=name,
            source_id=source_id,
            topic_path=topic_path,
            mission=mission,
            active_phase_index=0, # starts at phase 0
            strategy_profile=strategy,
            sources_config=sources_config,
            attack_plan=plan,
            pedagogical_journal=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_phase_index": 0,
                "action": "CREATE",
                "trigger": "Campaign creation command",
                "hypothesis": f"Initialized study plan for goal: {mission}",
                "status": "resolved",
                # plan_snapshot stays: CREATE is a change-authority baseline
                # action (ADR 018 — the only functional snapshot family).
                "plan_snapshot": [p.model_dump() for p in plan],
            }],
            syllabus_markdown=syllabus_markdown or f"# {name}\n\nInitialized study program for {topic_path}.",
        )
        self.store.campaigns.save(campaign)
        return campaign.model_dump()

    def attach_source_to_campaign(
        self, campaign_id: str, source_id: str, purpose: str = "Reference materials"
    ) -> dict[str, Any]:
        """Links a source into a campaign's `sources_config` (idempotent —
        re-attaching updates the purpose). Linked sources ground the
        campaign's future generation tasks.

        Raises:
            ValueError: unknown campaign.
        """
        campaign = self.store.campaigns.get(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        # Check if already linked
        linked = False
        for link in campaign.sources_config:
            if link.get("source_id") == source_id:
                link["purpose"] = purpose
                linked = True
                break

        if not linked:
            campaign.sources_config.append({"source_id": source_id, "purpose": purpose, "topics": []})

        self.store.campaigns.save(campaign)
        return campaign.model_dump()

    def get_campaign_history(self, campaign_id: str | None = None) -> dict[str, Any]:
        """The pedagogical journal (creation, phase advances, reflection
        interventions), newest first, for one campaign or all."""
        # Return history of pedagogical changes
        campaigns = []
        if campaign_id:
            c = self.store.campaigns.get(campaign_id)
            if c:
                campaigns.append(c)
        else:
            campaigns = self.store.campaigns.list()

        history = []
        for c in campaigns:
            for entry in c.pedagogical_journal:
                history.append({
                    "campaign_id": c.id,
                    "campaign_name": c.name,
                    "timestamp": entry.get("timestamp"),
                    "action": entry.get("action"),
                    "trigger": entry.get("trigger"),
                    "hypothesis": entry.get("hypothesis"),
                    "status": entry.get("status"),
                })
        # Sort history desc
        history = sorted(history, key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"history": history}

    def export_campaign_syllabus(
        self, campaign_id: str, format: str = "pdf", output_path: str | Path | None = None
    ) -> dict[str, Any]:
        """Writes the campaign syllabus to disk as PDF or markdown
        (default path: inside the dojo directory).

        Raises:
            ValueError: unknown campaign, or PDF requested without the
                optional `dojo[pdf]` extra installed.
        """
        campaign = self.store.campaigns.get(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        syllabus = campaign.syllabus_markdown or f"# {campaign.name}\n\nSyllabus is empty."
        if format.lower() == "pdf":
            try:
                from .pdf_generator import render_markdown_to_pdf
            except ImportError as exc:
                raise ValueError(
                    "PDF export requires the optional 'pdf' extra: pip install 'dojo[pdf]'. "
                    "Alternatively use --format markdown."
                ) from exc
            out = output_path or (self.store.dojo_dir / f"camp_{campaign_id}_syllabus.pdf")
            render_markdown_to_pdf(syllabus, out)
            return {"format": "pdf", "path": str(out), "syllabus": syllabus}
        else:
            out = output_path or (self.store.dojo_dir / f"camp_{campaign_id}_syllabus.md")
            Path(out).write_text(syllabus, encoding="utf-8")
            return {"format": "markdown", "path": str(out), "syllabus": syllabus}

