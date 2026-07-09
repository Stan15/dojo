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
import uuid
from datetime import datetime, timezone
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

        active = self.store.sessions.get_active()
        if active and active.status == "active" and not reset:
            return {
                "is_new": False,
                "session": active.model_dump(),
                "why": active.packet_reasons,
                "next": "resume: dojo ready reveals the next prompt (dojo daily --reset to rebuild)",
            }

        now = datetime.now(timezone.utc)

        # daily is the ritual's HEARTBEAT (use-case audit 2026-07-08): every
        # step the learning loop depends on either happens here deterministically
        # or is re-surfaced here — never parked in commands nobody must run.

        # 1. Phase advancement is pure math; it must not wait for a reflect call.
        for campaign in self.store.campaigns.list():
            if campaign.status == "active":
                self._evaluate_campaign_phase_advancement(campaign)

        pkt = packet_mod.build_packet(self.store, now, size=size)

        # 2. Token frugality: at most 2 generation tasks per daily run; the rest
        # wait and are counted honestly (E2E finding: a fresh plan emitted 5 at once).
        MAX_DAILY_TASKS = 2
        tasks = []
        for need in pkt.needs_generation[:MAX_DAILY_TASKS]:
            campaign = self.store.campaigns.get(need["campaign_id"])
            if campaign is None:
                continue
            task = flows.request_generation(
                self.store, campaign,
                topic_path=need["topic_path"], n_items=2,
                source_slice=flows.grounding_slice(self.store, campaign, need["topic_path"]),
                diagnostic=bool(need.get("diagnostic")),
                auto_promote=not bool(need.get("diagnostic")),
            )
            tasks.append(flows.task_ref(task))
        deferred = len(pkt.needs_generation) - min(len(pkt.needs_generation), MAX_DAILY_TASKS)
        if deferred:
            pkt.skipped["generation_deferred"] = deferred

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
            reflect_task = flows.request_reflection(self.store, campaign_id)
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
            return {
                "is_new": False,
                "session": None,
                "tasks": tasks,
                "stale_tasks": stale,
                "skipped": pkt.skipped,
                "campaign_reasons": pkt.campaign_reasons,
                "next": (
                    "nothing is due right now"
                    + ("; fulfill the generation task(s) then re-run dojo daily" if tasks else
                       (" — but finish the pending task(s) below first" if stale else
                        " — enjoy the day off, the schedule is honest"))
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
            "next": "dojo ready reveals the first prompt"
                    + (f" ({waiting} capture(s) awaiting a home: dojo inbox)" if waiting else "")
                    + (f" ({len(stale)} unfinished task(s) from earlier — fulfill them too)" if stale else ""),
        }

    def why(self) -> dict[str, Any]:
        """Replays the scheduling decisions behind the current packet (I9)."""
        session = self.store.sessions.get_active()
        if session is None:
            return {"session": None, "note": "no active session — run dojo daily first"}
        return {
            "session": session.id,
            "items": [
                {"exercise_id": ex_id, "reason": session.packet_reasons.get(ex_id, "(built before reasons were recorded)")}
                for ex_id in session.exercise_ids
            ],
            "campaigns": session.campaign_reasons,
        }

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
            answered = [a for a in attempts[-20:] if not a.skip_reason]
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
        """Archives excess reviews above limit based on oldest attempt/creation timestamp."""
        exercises = self.store.exercises.list(campaign_id)
        if len(exercises) <= limit:
            return

        # Sort exercises by created_at asc (oldest first)
        exercises = sorted(exercises, key=lambda x: x.created_at)
        excess_count = len(exercises) - limit
        for i in range(excess_count):
            ex = exercises[i]
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

        return {
            "session_id": target_session.id,
            "exercise_id": exercise_id,
            "index": idx,
            "total": len(exercise_ids),
            "prompt": ex.prompt,
            "topic_path": ex.topic_path,
            "difficulty": ex.difficulty,
            "started_at": started_at,
        }

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
        if ex.quality == "diagnostic":
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
            latency_seconds=latency,
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

            total_score = sum(a.score for a in phase_attempts)
            average_score = total_score / attempts_count if attempts_count > 0 else 0.0

            if average_score < min_accuracy:
                break

            campaign.active_phase_index += 1
            advanced = True
            self.log.info(f"Campaign '{campaign.id}' ('{campaign.name}') advanced to phase {campaign.active_phase_index} (mastered phase {phase_idx})")

            performance_snapshot = {
                "attempts": attempts_count,
                "accuracy": average_score,
                "average_latency_seconds": sum(a.latency_seconds for a in phase_attempts) / attempts_count if attempts_count > 0 else 0.0
            }

            active_insights = self.store.insights.list(campaign.id, filters={"status": "active"})
            insights_snapshot = [{"key": i.key, "description": i.description} for i in active_insights]

            journal_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_phase_index": phase_idx,
                "action": "PHASE_ADVANCE",
                "trigger": f"Passed Phase {phase_idx} criteria ({attempts_count} attempts, {average_score*100:.1f}% accuracy)",
                "hypothesis": f"User demonstrated mastery of topics: {', '.join(phase_topics)}",
                "status": "resolved",
                "performance_snapshot": performance_snapshot,
                "plan_snapshot": [p.model_dump() for p in attack_plan],
                "syllabus_snapshot": campaign.syllabus_markdown,
                "hypotheses_snapshot": insights_snapshot
            }
            campaign.pedagogical_journal.append(journal_entry)

        if advanced:
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
        # git-adjacent campaign would have destroyed the first).
        campaign_id = slugify(name) or slugify(topic_path)
        if self.store.campaigns.get(campaign_id) is not None:
            suffix = 2
            while self.store.campaigns.get(f"{campaign_id}-{suffix}") is not None:
                suffix += 1
            campaign_id = f"{campaign_id}-{suffix}"

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
                "plan_snapshot": [p.model_dump() for p in plan],
                "syllabus_snapshot": syllabus_markdown,
                "hypotheses_snapshot": []
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

