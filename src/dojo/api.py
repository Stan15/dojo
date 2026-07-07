from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import connectors
from . import generate
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
    ProfileConsolidateResponse,
)
from .store import DojoStore, slugify
from .prompts import load_prompt


class DojoAPI:
    def __init__(self, dojo_dir: str | Path | None = None):
        if dojo_dir is not None:
            path = Path(dojo_dir)
            if path.suffix:
                dojo_dir = path.parent
        self.store = DojoStore(dojo_dir)
        self.log = get_logger(self.store.dojo_dir, "api")

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

        candidates_count = 0
        diagnostics = []
        run_path = None

        if generate_candidates:
            # Collect existing topics from all campaigns & exercises
            existing_topics = self.get_all_topic_paths()

            content_lines = content.splitlines()
            source_refs = [{
                "source_id": source_id,
                "span": {
                    "start_line": 1,
                    "end_line": len(content_lines) or 1,
                    "anchor_text": title,
                }
            }]

            request = generate.ExerciseGenerateRequest(
                source_id=source_id,
                source_title=title,
                source_refs=source_refs,
                topic=topic,
                mission=mission,
                existing_topics=existing_topics,
                source_content=content,
            )

            result = connectors.invoke_command_connector(self.store, request.to_task_request())

            if result.status == "ok":
                val = generate.validate_exercise_generate_output(
                    result.parsed_stdout or result.raw_stdout, default_topic=topic
                )
                if val["candidates"]:
                    # Create a temporary dummy campaign ID or try to resolve matching active campaigns
                    campaign_id = "default"
                    active_camps = self.store.campaigns.list()
                    if active_camps:
                        campaign_id = active_camps[0].id

                    for cand_data in val["candidates"]:
                        cand_id = f"cand_{uuid.uuid4().hex[:8]}"
                        candidate = Candidate(
                            id=cand_id,
                            topic_path=cand_data["topic_path"],
                            difficulty=cand_data.get("difficulty") or "intermediate",
                            generation_run=None,
                            prompt=cand_data["prompt"],
                            answer=cand_data.get("answer"),
                            rubric=cand_data.get("rubric"),
                        )
                        self.store.candidates.save(campaign_id, candidate)
                        candidates_count += 1
                    if not val["ok"]:
                        diagnostics = val["diagnostics"]
                else:
                    diagnostics = val["diagnostics"] or ["no valid candidates generated"]
            else:
                diagnostics = [result.error or "connector execution failed"]

            run_path = self.record_generation_run(
                task="exercise.generate",
                request=request.to_task_request(),
                raw_output=result.raw_stdout,
                status=result.status,
                diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
            )

            if run_path and candidates_count > 0:
                # Update candidates with their generation run path
                campaign_id = active_camps[0].id if active_camps else "default"
                candidates = self.store.candidates.list(campaign_id)
                for cand in candidates:
                    if not cand.generation_run:
                        cand.generation_run = run_path
                        self.store.candidates.save(campaign_id, cand)

            self.log.info(f"Candidate generation completed: source='{source_id}', candidates={candidates_count}, run_path={run_path}, errors={bool(diagnostics)}")

        output = {
            "source_id": source.id,
            "title": source.title,
            "kind": source.kind,
            "candidates_count": candidates_count,
        }
        if run_path:
            # Backwards compatibility: CLI expects integer or string run_id. Path works.
            output["generation_run_id"] = run_path
        if diagnostics:
            output["diagnostics"] = diagnostics

        return output

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

        # 6. Trigger JIT generation if queue is low
        if len(due_exercises) < 3 and resolved_campaign:
            strategy = resolved_campaign.strategy_profile
            is_diagnostic = (
                strategy.get("mode") == "diagnostic" or
                any(t.endswith(".diagnostic") for t in active_topics)
            )

            if is_diagnostic:
                # Onboarding / Diagnostic generation
                request = {
                    "task": "exercise.generate",
                    "version": 1,
                    "instructions": (
                        "You are in onboarding/diagnostic mode. "
                        f"The user's goal is: '{resolved_campaign.name}'. "
                        "Based on this goal, you must return a JSON object containing:\n"
                        "1. 'title': A suggested campaign title.\n"
                        "2. 'base_topic': A clean, dot-separated topic path namespace (e.g. 'math.quaternions' or 'devops.docker').\n"
                        "3. 'diagnostic_questions': A list of 2-3 targeted diagnostic questions to assess their level and success definition."
                    ),
                    "source": {
                        "id": None,
                        "title": resolved_campaign.name,
                        "refs": [],
                        "content": ""
                    },
                    "topic_hint": target_topic or "diagnostic",
                    "max_candidates": 3,
                    "expected_artifacts": ["diagnostic_questions"]
                }

                result = connectors.invoke_command_connector(self.store, request)
                diagnostics = []
                if result.status == "ok":
                    data = result.parsed_stdout or {}
                    title = data.get("title") or resolved_campaign.name
                    base_topic = data.get("base_topic") or resolved_campaign.topic_path or "topic"
                    diagnostic_questions = data.get("diagnostic_questions") or [
                        "What is your background?",
                        "What is your main goal?"
                    ]

                    # Update Campaign details
                    resolved_campaign.name = title
                    resolved_campaign.topic_path = base_topic
                    resolved_campaign.attack_plan = [
                        AttackPlanPhase(
                            phase=0,
                            topics=[f"{base_topic}.diagnostic"],
                            criteria={"min_attempts": len(diagnostic_questions), "min_accuracy": 0.0}
                        )
                    ]
                    self.store.campaigns.save(resolved_campaign)

                    target_topic = f"{base_topic}.diagnostic"
                    active_topics = [f"{base_topic}.diagnostic"]

                    for q in diagnostic_questions:
                        cand_id = f"cand_{uuid.uuid4().hex[:8]}"
                        candidate = Candidate(
                            id=cand_id,
                            prompt=q,
                            topic_path=f"{base_topic}.diagnostic",
                            difficulty="intermediate",
                            quality="diagnostic",
                        )
                        self.store.candidates.save(resolved_campaign.id, candidate)
                        # Auto-promote diagnostic questions
                        self.promote_candidate(cand_id)
                else:
                    diagnostics = [result.error or "connector execution failed"]

                self.record_generation_run(
                    task="exercise.generate.diagnostic",
                    request=request,
                    raw_output=result.raw_stdout,
                    status=result.status,
                    diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
                )
            else:
                # Regular JIT generation
                target_topic = active_topics[0] if active_topics else resolved_campaign.topic_path
                # Balance topics if multiple
                if len(active_topics) > 1:
                    topic_counts = {}
                    for t in active_topics:
                        count = sum(1 for ex in all_ex if ex.topic_path == t or ex.topic_path.startswith(t + "."))
                        topic_counts[t] = count
                    target_topic = min(active_topics, key=lambda t: topic_counts[t])

                # Locate linked source
                sources_config = resolved_campaign.sources_config
                active_source_id = None
                active_purpose = "Primary study material"
                for link in sources_config:
                    sid = link["source_id"]
                    topics = link.get("topics") or []
                    if not topics or any(target_topic == t or target_topic.startswith(t + ".") for t in topics):
                        active_source_id = sid
                        active_purpose = link.get("purpose", "Primary study material")
                        break

                source_refs = []
                source_content = ""
                source_title = resolved_campaign.name

                if active_source_id:
                    full_source = self.store.sources.get(active_source_id)
                    if full_source:
                        source_title = full_source.title
                        source_content, start_line, end_line = generate.resolve_source_context(
                            full_source.content,
                            source_title,
                            target_topic or "",
                            min_lines=100
                        )
                        source_refs = [{
                            "source_id": active_source_id,
                            "span": {
                                "start_line": start_line,
                                "end_line": end_line,
                                "anchor_text": source_title,
                            }
                        }]

                # Collect active insights matching topic
                active_insights = self.store.insights.list(resolved_campaign.id, filters={"status": "active"})
                insight_descs = []
                for ins in active_insights:
                    if target_topic and (ins.topic_path == target_topic or (ins.topic_path and target_topic.startswith(ins.topic_path + "."))):
                        insight_descs.append(ins.description)

                custom_instructions = self.store.configs.get("prompt.exercise_generate_instructions")
                existing_topics = self.get_all_topic_paths()

                req = generate.ExerciseGenerateRequest(
                    source_id=active_source_id or "",
                    source_title=source_title,
                    source_refs=source_refs,
                    topic=target_topic,
                    mission=resolved_campaign.mission,
                    existing_topics=existing_topics,
                    learner_hypotheses=insight_descs if insight_descs else None,
                    instructions=custom_instructions,
                    source_content=source_content,
                    strategy=strategy if strategy else None,
                    active_topics=active_topics,
                    phase_focus=phase_focus,
                )

                result = connectors.invoke_command_connector(self.store, req.to_task_request())
                diagnostics = []
                if result.status == "ok":
                    val = generate.validate_exercise_generate_output(
                        result.parsed_stdout or result.raw_stdout, default_topic=target_topic
                    )
                    if val["candidates"]:
                        for cand_data in val["candidates"]:
                            cand_id = f"cand_{uuid.uuid4().hex[:8]}"
                            candidate = Candidate(
                                id=cand_id,
                                topic_path=cand_data["topic_path"],
                                difficulty=cand_data.get("difficulty") or "intermediate",
                                prompt=cand_data["prompt"],
                                answer=cand_data.get("answer"),
                                rubric=cand_data.get("rubric"),
                            )
                            self.store.candidates.save(resolved_campaign.id, candidate)
                            self.promote_candidate(cand_id)
                        if not val["ok"]:
                            diagnostics = val.get("diagnostics") or []
                    else:
                        diagnostics = val.get("diagnostics") or ["no valid candidates generated"]
                else:
                    diagnostics = [result.error or "connector execution failed"]

                self.record_generation_run(
                    task="exercise.generate.jit",
                    request=req.to_task_request(),
                    raw_output=result.raw_stdout,
                    status=result.status,
                    diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
                )

            # Re-query due list
            if resolved_campaign:
                all_ex = self.store.exercises.list(resolved_campaign.id)
            due_exercises = [
                ex for ex in all_ex
                if ex.quality not in ("archived", "too_easy", "too_hard", "bad_quality")
                and ex.id not in non_forgot_attempted_ids
            ]
            if active_topics:
                due_exercises = [
                    ex for ex in due_exercises
                    if any(ex.topic_path == t or ex.topic_path.startswith(t + ".") for t in active_topics)
                ]

        due_exercises = sorted(due_exercises, key=lambda x: x.created_at)

        if not due_exercises:
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
            "session": ps.model_dump()
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
        if correct_ans:
            score = 1.0 if user_ans.lower() == correct_ans.strip().lower() else 0.0
        else:
            score = 1.0

        attempt_id = f"att_{uuid.uuid4().hex[:8]}"

        attempt = Attempt(
            id=attempt_id,
            session_id=target_session.id,
            exercise_id=exercise_id,
            campaign_id=campaign_id,
            score=score,
            latency_seconds=latency,
            user_answer=user_ans,
            prompt=ex.prompt,
        )
        self.store.attempts.save(campaign_id, attempt)

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
        if feedback is not None:
            latest_att.feedback = feedback
        self.store.attempts.save(campaign_id, latest_att)

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
        """Convenience method wrapper to call consolidate_learner_profile."""
        return self.consolidate_learner_profile(campaign_id=campaign_id)

    def consolidate_learner_profile(self, campaign_id: str | None = None) -> dict[str, Any]:
        if campaign_id is None:
            campaigns = self.store.campaigns.list()
            if not campaigns:
                return self._consolidate_global_fallback()
            results = []
            all_insights = []
            all_diagnostics = []
            for c in campaigns:
                res = self._consolidate_single_campaign(c.id)
                results.append(res)
                all_insights.extend(res.get("insights") or [])
                all_diagnostics.extend(res.get("diagnostics") or [])
            return {
                "status": "ok",
                "campaigns": results,
                "insights": all_insights,
                "diagnostics": all_diagnostics
            }
        else:
            return self._consolidate_single_campaign(campaign_id)

    def _consolidate_global_fallback(self) -> dict[str, Any]:
        # Collect recent attempts across all campaigns
        attempts = []
        for camp in self.store.campaigns.list():
            attempts.extend(self.store.attempts.list(camp.id))

        attempts = sorted(attempts, key=lambda x: x.created_at, reverse=True)[:20]

        # Scan active insights
        active_insights = []
        for camp in self.store.campaigns.list():
            active_insights.extend(self.store.insights.list(camp.id, filters={"status": "active"}))

        formatted_attempts = []
        for a in attempts:
            formatted_attempts.append({
                "exercise_id": a.exercise_id,
                "prompt": a.prompt,
                "user_answer": a.user_answer,
                "score": a.score,
                "skip_reason": a.skip_reason,
                "feedback": a.feedback,
                "created_at": a.created_at,
            })

        custom_consolidate_instructions = self.store.configs.get("prompt.profile_consolidate_instructions")
        default_instructions = (
            "Analyze the learner's recent practice attempts, skip reasons, and feedback. "
            "Pay close attention to user responses to diagnostic/pedagogical questions (indicated by free-form answers targeting learning style/goals) to extract goals, preferences, prior knowledge, or misconceptions. "
            "Synthesize stable learner hypotheses (misconceptions, pattern strengths/weaknesses, scaffolding rules, learning style/goals). "
            "Return a JSON list/object of hypotheses under 'hypotheses'. "
            "Each hypothesis must have a machine-readable 'key' (like 'misconception.lists_vs_tuples' or 'preference.practical_code') "
            "and a human-readable 'description'."
        )

        request = {
            "task": "profile.consolidate",
            "version": 1,
            "instructions": custom_consolidate_instructions or default_instructions,
            "attempts": formatted_attempts,
            "active_hypotheses": [h.description for h in active_insights],
        }

        result = connectors.invoke_command_connector(self.store, request)
        diagnostics = []
        saved_insights = []

        if result.status == "ok":
            raw_data = result.parsed_stdout
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception as exc:
                    diagnostics.append(f"Failed to parse raw output as JSON: {exc}")

            insights_to_save = []
            if isinstance(raw_data, dict):
                insights_to_save = raw_data.get("hypotheses") or []
            elif isinstance(raw_data, list):
                insights_to_save = raw_data

            consolidated_keys = {ins.get("key") for ins in insights_to_save if ins.get("key")}

            # Resolve active insights no longer reported
            campaign_id = "default"
            camps = self.store.campaigns.list()
            if camps:
                campaign_id = camps[0].id

            for existing_ins in active_insights:
                if existing_ins.key not in consolidated_keys:
                    existing_ins.status = "resolved"
                    existing_ins.updated_at = datetime.now(timezone.utc).isoformat()
                    # Resolve physically in store
                    self.store.insights.save(campaign_id, existing_ins)

            for idx, ins_data in enumerate(insights_to_save):
                if not isinstance(ins_data, dict):
                    diagnostics.append(f"Insight at index {idx} is not a dict")
                    continue
                key = ins_data.get("key")
                description = ins_data.get("description")
                if not key or not description:
                    diagnostics.append(f"Insight at index {idx} missing key or description")
                    continue

                # Deduplicate by key matching filename
                existing_ins = None
                for ins in active_insights:
                    if ins.key == key:
                        existing_ins = ins
                        break

                if existing_ins:
                    # Deduplication / Merge: append sources and update description
                    existing_ins.description = description
                    existing_ins.updated_at = datetime.now(timezone.utc).isoformat()
                    self.store.insights.save(campaign_id, existing_ins)
                    saved_insights.append(existing_ins)
                else:
                    insight_id = f"ins_{uuid.uuid4().hex[:8]}"
                    new_ins = Insight(
                        id=insight_id,
                        key=key,
                        description=description,
                        status="active"
                    )
                    self.store.insights.save(campaign_id, new_ins)
                    saved_insights.append(new_ins)

            # Mark processed attempts as reflected
            for a in attempts:
                a.reflected = True
                self.store.attempts.save(campaign_id, a)

        else:
            diagnostics.append(result.error or "connector execution failed")

        self.record_generation_run(
            task="profile.consolidate",
            request=request,
            raw_output=result.raw_stdout,
            status=result.status,
            diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
        )

        if result.status != "ok":
            raise ValueError(f"Profile consolidation failed: {result.error or 'connector execution failed'}")

        return {
            "status": result.status,
            "insights": [i.model_dump() for i in saved_insights],
            "diagnostics": diagnostics,
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

    def _consolidate_single_campaign(self, campaign_id: str) -> dict[str, Any]:
        campaign = self.store.campaigns.get(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        self.log.info(f"Consolidating campaign '{campaign_id}' ('{campaign.name}')")
        if campaign.active_phase_index > 0:
            self._evaluate_campaign_phase_advancement(campaign)

        topic_path = campaign.topic_path

        # 1. Query unreflected attempts (Short-term working context)
        all_attempts = self.store.attempts.list(campaign_id)
        unreflected_attempts = [a for a in all_attempts if not a.reflected]

        # 2. Query active user feedback insights
        feedback_insights = self.store.insights.list(campaign_id, filters={"status": "active"})
        user_feedback_insights = [i for i in feedback_insights if i.key.startswith("feedback.user.")]

        has_unmapped_source = any(not link.get("topics") for link in campaign.sources_config)

        if not unreflected_attempts and not user_feedback_insights and not has_unmapped_source:
            self.log.info(f"Consolidation skipped for campaign '{campaign_id}': no new attempts, active feedback, or unmapped sources")
            return {
                "status": "skipped",
                "campaign_id": campaign_id,
                "diagnostics": ["No new attempts, active feedback, or unmapped sources since last consolidation"]
            }

        # 3. Two-Tiered Memory Model: unreflected + sliding window of last 15 attempts (reflected and unreflected)
        sliding_window = all_attempts[-15:]
        # Deduplicate attempts in payload: combine both sets uniquely preserving order
        payload_attempts = []
        seen_ids = set()
        for a in unreflected_attempts + sliding_window:
            if a.id not in seen_ids:
                payload_attempts.append(a)
                seen_ids.add(a.id)

        formatted_attempts = []
        for a in payload_attempts:
            formatted_attempts.append({
                "exercise_id": a.exercise_id,
                "prompt": a.prompt,
                "user_answer": a.user_answer,
                "score": a.score,
                "skip_reason": a.skip_reason,
                "feedback": a.feedback,
                "created_at": a.created_at,
            })

        # Get active insights
        active_insights = self.store.insights.list(campaign_id, filters={"status": "active"})
        insight_descriptions = []
        for h in active_insights:
            desc = h.description
            # Attach source context
            if h.sources:
                desc += f" (Evidence links: {', '.join(h.sources)})"
            insight_descriptions.append(desc)

        latest_baseline_plan = []
        for entry in reversed(campaign.pedagogical_journal):
            if entry.get("action") in ("CREATE", "PIVOT"):
                latest_baseline_plan = entry.get("plan_snapshot") or []
                break

        # Token Optimization: Clean resolved journal entries
        prompt_journal = []
        for entry in campaign.pedagogical_journal:
            cleaned = entry.copy()
            if cleaned.get("status") != "active":
                cleaned.pop("plan_snapshot", None)
                cleaned.pop("performance_snapshot", None)
            prompt_journal.append(cleaned)

        # Token Optimization: Prune completed phases from current plan
        active_idx = campaign.active_phase_index
        prompt_current_plan = []
        for idx, phase in enumerate(campaign.attack_plan):
            if idx < active_idx:
                prompt_current_plan.append({
                    "phase": idx,
                    "status": "completed",
                    "topics": phase.topics,
                })
            else:
                prompt_current_plan.append(phase.model_dump())

        # Collect linked sources information
        linked_sources = []
        for link in campaign.sources_config:
            sid = link["source_id"]
            src_rec = self.store.sources.get(sid)
            if src_rec:
                headings = generate.parse_markdown_headings(src_rec.content)
                outline = [f"{'#' * h['level']} {h['title']}" for h in headings]
                linked_sources.append({
                    "source_id": sid,
                    "title": src_rec.title,
                    "purpose": link.get("purpose", ""),
                    "content_preview": src_rec.content[:1500],
                    "outline": outline[:100],
                })

        # Load consolidation prompts
        custom_consolidate_instructions = self.store.configs.get("prompt.profile_consolidate_instructions")
        from .schemas import get_schema_instruction, ProfileConsolidateResponse
        schema_instruction = get_schema_instruction("profile.consolidate")

        if custom_consolidate_instructions:
            instructions = custom_consolidate_instructions + schema_instruction
        else:
            instructions = load_prompt("legacy_profile_consolidate.md", {"schema_instructions": schema_instruction})

        request = {
            "task": "profile.consolidate",
            "version": 1,
            "instructions": instructions,
            "attempts": formatted_attempts,
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "mission": campaign.mission,
                "syllabus_markdown": campaign.syllabus_markdown,
                "active_phase_index": active_idx,
                "current_attack_plan": prompt_current_plan,
                "latest_baseline_plan": latest_baseline_plan,
                "pedagogical_journal": prompt_journal,
                "strategy_profile": campaign.strategy_profile,
                "linked_sources": linked_sources,
            },
            "active_hypotheses": insight_descriptions,
        }

        result = connectors.invoke_command_connector(self.store, request)
        diagnostics = []
        saved_insights = []

        if result.status == "ok":
            raw_data = result.parsed_stdout
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception as exc:
                    diagnostics.append(f"Failed to parse raw output as JSON: {exc}")

            if isinstance(raw_data, dict):
                try:
                    ProfileConsolidateResponse.model_validate(raw_data)
                except Exception as exc:
                    diagnostics.append(f"Response validation warning: {exc}")
            else:
                raw_data = {}

            # Update Campaign parameters
            refined_mission = raw_data.get("refined_mission")
            if refined_mission:
                campaign.mission = refined_mission

            calibrated_strategy = raw_data.get("calibrated_strategy")
            if calibrated_strategy:
                campaign.strategy_profile = calibrated_strategy

            revised_attack_plan = raw_data.get("revised_attack_plan")
            if revised_attack_plan:
                campaign.attack_plan = [AttackPlanPhase.model_validate(p) for p in revised_attack_plan]

            syllabus_markdown = raw_data.get("syllabus_markdown")
            if syllabus_markdown:
                campaign.syllabus_markdown = syllabus_markdown

            source_topic_mappings = raw_data.get("source_topic_mappings") or {}
            updated_sources_config = []
            for link in campaign.sources_config:
                sid = link.get("source_id")
                if sid in source_topic_mappings:
                    link["topics"] = source_topic_mappings[sid]
                updated_sources_config.append(link)
            campaign.sources_config = updated_sources_config

            new_journal_entry = raw_data.get("journal_entry")
            if new_journal_entry:
                # Fetch performance snapshot
                try:
                    curr_plan = revised_attack_plan or [p.model_dump() for p in campaign.attack_plan]
                    phase_def = curr_plan[campaign.active_phase_index]
                    phase_topics = phase_def.get("topics", [])
                except Exception:
                    phase_topics = []

                phase_attempts = []
                for a in all_attempts:
                    if a.skip_reason and a.skip_reason != "forgot":
                        continue
                    ex = self.store.exercises.get(campaign.id, a.exercise_id)
                    if ex:
                        for t in phase_topics:
                            if ex.topic_path == t or ex.topic_path.startswith(t + "."):
                                phase_attempts.append(a)
                                break

                attempts_count = len(phase_attempts)
                average_score = sum(a.score for a in phase_attempts) / attempts_count if attempts_count > 0 else 0.0

                perf_snapshot = {
                    "attempts": attempts_count,
                    "accuracy": average_score,
                    "average_latency_seconds": sum(a.latency_seconds for a in phase_attempts) / attempts_count if attempts_count > 0 else 0.0
                }

                current_insights = self.store.insights.list(campaign.id, filters={"status": "active"})
                insights_snapshot = [{"key": i.key, "description": i.description} for i in current_insights]

                entry_to_save = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "active_phase_index": campaign.active_phase_index,
                    "action": new_journal_entry.get("action", "CALIBRATE_STRATEGY"),
                    "trigger": new_journal_entry.get("trigger", "Profile consolidation"),
                    "hypothesis": new_journal_entry.get("hypothesis", ""),
                    "status": new_journal_entry.get("status", "resolved"),
                    "performance_snapshot": perf_snapshot,
                    "plan_snapshot": revised_attack_plan or [p.model_dump() for p in campaign.attack_plan],
                    "syllabus_snapshot": campaign.syllabus_markdown,
                    "hypotheses_snapshot": insights_snapshot
                }
                campaign.pedagogical_journal.append(entry_to_save)

            # Process returned insights / hypotheses
            insights_to_save = raw_data.get("hypotheses") or []
            consolidated_keys = {ins.get("key") for ins in insights_to_save if ins.get("key")}

            # Resolve active insights no longer reported
            for existing_ins in active_insights:
                if existing_ins.key not in consolidated_keys:
                    existing_ins.status = "resolved"
                    existing_ins.updated_at = datetime.now(timezone.utc).isoformat()
                    self.store.insights.save(campaign_id, existing_ins)

            # Merge & Append new evidence paths to existing active insights
            for idx, ins_data in enumerate(insights_to_save):
                if not isinstance(ins_data, dict):
                    continue
                key = ins_data.get("key")
                description = ins_data.get("description")
                if not key or not description:
                    continue

                # Find matched insight by key (filename)
                existing_ins = None
                for ins in active_insights:
                    if ins.key == key:
                        existing_ins = ins
                        break

                new_source_paths = []
                for a in unreflected_attempts:
                    matching_path = None
                    prefix = f"campaigns/camp_{campaign_id}/attempts"
                    for rel_path, file_info in self.store.index["files"].items():
                        if file_info.get("type") == "attempt" and rel_path.startswith(prefix):
                            if file_info.get("data", {}).get("id") == a.id:
                                matching_path = rel_path
                                break
                    if matching_path:
                        new_source_paths.append(matching_path)
                    else:
                        new_source_paths.append(f"campaigns/camp_{campaign_id}/attempts/att_{a.id}.md")

                if existing_ins:
                    # Append new source attempt links uniquely
                    merged_sources = list(set(existing_ins.sources + new_source_paths))
                    existing_ins.sources = merged_sources
                    existing_ins.description = description
                    existing_ins.updated_at = datetime.now(timezone.utc).isoformat()
                    self.store.insights.save(campaign_id, existing_ins)
                    saved_insights.append(existing_ins)
                else:
                    insight_id = f"ins_{uuid.uuid4().hex[:8]}"
                    new_ins = Insight(
                        id=insight_id,
                        key=key,
                        sources=new_source_paths,
                        description=description,
                        status="active"
                    )
                    self.store.insights.save(campaign_id, new_ins)
                    saved_insights.append(new_ins)

            # Mark processed attempts as reflected
            for a in unreflected_attempts:
                a.reflected = True
                self.store.attempts.save(campaign_id, a)

            self.store.campaigns.save(campaign)
        else:
            diagnostics.append(result.error or "connector execution failed")

        run_path = self.record_generation_run(
            task="profile.consolidate",
            request=request,
            raw_output=result.raw_stdout,
            status=result.status,
            diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
        )

        # Link insight to run
        if run_path and saved_insights:
            for ins in saved_insights:
                ins.generation_run = run_path
                self.store.insights.save(campaign_id, ins)

        if result.status != "ok":
            raise ValueError(f"Profile consolidation failed: {result.error or 'connector execution failed'}")

        return {
            "status": result.status,
            "insights": [i.model_dump() for i in saved_insights],
            "diagnostics": diagnostics,
        }

    def record_generation_run(
        self,
        task: str,
        request: dict[str, Any],
        raw_output: str,
        status: str,
        diagnostics: dict[str, Any],
    ) -> str:
        """Saves a developer LLM trace file under runs/YYYY-MM-DD/HHMMSS_task.json and returns rel path."""
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        task_slug = task.replace(".", "_")
        rel_path = f"runs/{date_str}/{time_str}_{task_slug}.json"

        run_payload = {
            "task": task,
            "status": status,
            "created_at": now.isoformat(),
            "request": request,
            "diagnostics": diagnostics,
            "raw_output": raw_output,
        }

        # Save run trace (which does not lock/require commit logs)
        self.store.write_text(rel_path, json.dumps(run_payload, indent=2))
        return rel_path

    # ==========================================
    # Config Values Operations
    # ==========================================
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

    def get_generation_run(self, run_id: str) -> dict[str, Any] | None:
        """Reads trace payload from rel path string run_id."""
        filepath = self.store.dojo_dir / run_id
        if not filepath.exists():
            return None
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except Exception:
            return None
