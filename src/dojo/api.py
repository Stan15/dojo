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

            campaign = None
            camps = self.store.campaigns.list()
            if campaign_hint := (topic and next(
                (c for c in camps if c.topic_path and topic.startswith(c.topic_path)), None
            )):
                campaign = campaign_hint
            elif camps:
                campaign = camps[0]
            if campaign is None:
                return {
                    "source_id": source.id,
                    "title": source.title,
                    "kind": source.kind,
                    "tasks": [],
                    "note": "source saved; no campaign exists yet, so no generation was requested — "
                            "create a campaign first (dojo campaign plan \"<goal>\")",
                }

            target_topic = topic or campaign.topic_path or slugify(title).replace("-", "_")
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
        return [s.model_dump() for s in self.store.sources.list()]

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        src = self.store.sources.get(source_id)
        return src.model_dump() if src else None

    def get_source_topics(self, source_id: str) -> list[dict[str, Any]]:
        # In Markdown-native JIT, candidates belong to campaigns. We scan active campaign candidates.
        topics = {}
        for camp in self.store.campaigns.list():
            for cand in self.store.candidates.list(camp.id):
                # Check if candidate is associated with this source
                # Sources references are parsed in candidate prompt/frontmatter
                # For simplicity, if source_id matches
                pass
        # Fallback to scanning all candidates across campaigns
        for camp in self.store.campaigns.list():
            for cand in self.store.candidates.list(camp.id):
                # Parse topic hierarchy
                path = cand.topic_path
                topics[path] = topics.get(path, 0) + 1
        return [{"topic_path": k, "count": v} for k, v in topics.items()]

    def get_source_candidates(self, source_id: str, topic_path: str | None = None) -> list[dict[str, Any]]:
        # Collect candidates across active campaigns matching the source_id and topic_path
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
        ps = self.store.sessions.get_active()
        return ps.model_dump() if ps else None

    def reveal_prompt(self, session_id: str | None = None) -> dict[str, Any]:
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
        # Map to insights
        insights = []
        for camp in self.store.campaigns.list():
            insights.extend(self.store.insights.list(camp.id, filters={"status": status}))
        return [ins.model_dump() for ins in insights]

    def save_learner_hypothesis(self, key: str, description: str, status: str = "active") -> dict[str, Any]:
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
        self.store.configs.set(key, value)
        return {"key": key, "value": value}

    def get_config(self, key: str) -> str | None:
        return self.store.configs.get(key)

    def list_configs(self) -> dict[str, str]:
        config = self.store.configs._read_config()
        return {str(k): str(v) for k, v in config.items()}

    # ==========================================
    # System Metadata / Helper Operations
    # ==========================================
    def get_all_topic_paths(self) -> list[str]:
        topics = set()
        for camp in self.store.campaigns.list():
            if camp.topic_path:
                topics.add(camp.topic_path)
            for ex in self.store.exercises.list(camp.id):
                topics.add(ex.topic_path)
        return sorted(list(topics))

    def format_topic_tree(self, flat_paths: list[str]) -> str:
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
        self.log.info(f"Creating campaign: '{name}' (topic_path={topic_path})")
        # Folder is camp_{slugified_topic}
        campaign_id = f"{slugify(topic_path)}"

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

