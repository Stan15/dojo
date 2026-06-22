from __future__ import annotations

import uuid
import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime, timezone
from sqlmodel import select

from . import db
from . import generate
from . import connectors
from . import logger
from .db import Exercise, Campaign, Candidate

class DojoAPI:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        db.init_db(self.db_path)
        self.log = logger.get_logger(self.db_path, "api")

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

        with db.connect(self.db_path) as session:
            source = db.save_source(
                session,
                id=source_id,
                title=title,
                content=content,
                kind=kind,
                path=path,
                mission=mission,
            )

            candidates_count = 0
            diagnostics = []
            run_id = None

            if generate_candidates:
                topics_set = set()
                for ex in session.exec(select(Exercise)).all():
                    topics_set.add(ex.topic_path)
                for camp in session.exec(select(Campaign)).all():
                    topics_set.add(camp.topic_path)
                existing_topics = sorted(list(topics_set))

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

                result = connectors.invoke_command_connector(self.db_path, request.to_task_request())

                if result.status == "ok":
                    val = generate.validate_exercise_generate_output(result.parsed_stdout or result.raw_stdout, default_topic=topic)
                    if val["candidates"]:
                        for cand in val["candidates"]:
                            cand_id = f"cand_{uuid.uuid4().hex[:8]}"
                            db.save_candidate(
                                session,
                                id=cand_id,
                                source_id=source_id,
                                prompt=cand["prompt"],
                                answer=cand.get("answer"),
                                rubric=cand.get("rubric"),
                                topic_path=cand["topic_path"],
                                source_refs=cand["source_refs"],
                                difficulty=cand.get("difficulty"),
                                generation_run_id=None,
                            )
                            candidates_count += 1
                        if not val["ok"]:
                            diagnostics = val["diagnostics"]
                    else:
                        diagnostics = val["diagnostics"] or ["no valid candidates generated"]
                else:
                    diagnostics = [result.error or "connector execution failed"]

                run_id = db.record_generation_run(
                    session,
                    task="exercise.generate",
                    request=request.to_task_request(),
                    raw_output=result.raw_stdout,
                    status=result.status,
                    diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
                )

                if run_id and candidates_count > 0:
                    session.execute(
                        db.SQLModel.metadata.tables["candidates"]
                        .update()
                        .where(db.SQLModel.metadata.tables["candidates"].c.source_id == source_id)
                        .values(generation_run_id=run_id)
                    )
                    session.commit()
                self.log.info(f"Candidate generation completed: source='{source_id}', candidates={candidates_count}, run_id={run_id}, errors={bool(diagnostics)}")

            output = {
                "source_id": source["id"],
                "title": source["title"],
                "kind": source["kind"],
                "candidates_count": candidates_count,
            }
            if run_id:
                output["generation_run_id"] = run_id
            if diagnostics:
                output["diagnostics"] = diagnostics

            return output

    def list_sources(self) -> list[dict[str, Any]]:
        with db.connect(self.db_path) as session:
            sources = db.list_sources(session)
            output_sources = []
            for src in sources:
                candidates = db.list_candidates(session, src["id"])
                output_sources.append({
                    "id": src["id"],
                    "title": src["title"],
                    "kind": src["kind"],
                    "path": src["path"],
                    "mission": src["mission"],
                    "candidates_count": len(candidates),
                    "created_at": src["created_at"],
                })
            return output_sources

    def get_source(
        self,
        source_id: str,
        start_line: int | None = None,
        end_line: int | None = None
    ) -> dict[str, Any] | None:
        with db.connect(self.db_path) as session:
            source = db.get_source(session, source_id)
            if not source:
                return None

            content = source["content"]
            if start_line is not None or end_line is not None:
                lines = content.splitlines()
                s = start_line if start_line is not None else 1
                e = end_line if end_line is not None else len(lines)
                if lines:
                    s = max(1, min(s, len(lines)))
                    e = max(s, min(e, len(lines)))
                    content = "\n".join(lines[s - 1 : e])
                else:
                    content = ""

            candidates = db.list_candidates(session, source["id"])
            return {
                "id": source["id"],
                "title": source["title"],
                "kind": source["kind"],
                "path": source["path"],
                "mission": source["mission"],
                "content": content,
                "candidates_count": len(candidates),
                "created_at": source["created_at"],
            }

    def get_source_topics(self, source_id: str) -> list[dict[str, Any]]:
        with db.connect(self.db_path) as session:
            source = db.get_source(session, source_id)
            if not source:
                raise ValueError(f"unknown source: {source_id}")
            candidates = db.list_candidates(session, source["id"])
            topics_count = {}
            for c in candidates:
                topics_count[c["topic_path"]] = topics_count.get(c["topic_path"], 0) + 1

            output_data = []
            for t_path, count in sorted(topics_count.items()):
                output_data.append({"topic_path": t_path, "candidates_count": count})
            return output_data

    def get_source_candidates(self, source_id: str, topic_path: str | None = None) -> list[dict[str, Any]]:
        with db.connect(self.db_path) as session:
            source = db.get_source(session, source_id)
            if not source:
                raise ValueError(f"unknown source: {source_id}")
            candidates = db.list_candidates(session, source["id"], topic_path=topic_path)
            output_data = []
            for c in candidates:
                output_data.append({
                    "id": c["id"],
                    "prompt": c["prompt"],
                    "answer": c["answer"],
                    "rubric": c["rubric"],
                    "topic_path": c["topic_path"],
                    "difficulty": c["difficulty"],
                    "quality": c["quality"],
                })
            return output_data

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with db.connect(self.db_path) as session:
            return db.get_candidate(session, candidate_id)

    def save_candidate(
        self,
        *,
        id: str,
        source_id: str,
        prompt: str,
        answer: str | None = None,
        rubric: dict[str, Any] | None = None,
        topic_path: str,
        source_refs: dict[str, Any],
        difficulty: str | None = None,
        quality: str = "candidate",
        generation_run_id: int | None = None,
    ) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            return db.save_candidate(
                session,
                id=id,
                source_id=source_id,
                prompt=prompt,
                answer=answer,
                rubric=rubric,
                topic_path=topic_path,
                source_refs=source_refs,
                difficulty=difficulty,
                quality=quality,
                generation_run_id=generation_run_id,
            )

    def remove_candidate(self, candidate_id: str) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            return db.remove_candidate(session, candidate_id)

    def _enforce_queue_limit(self, session):
        stmt = select(db.Attempt.exercise_id).where(
            (db.Attempt.skip_reason == None) | (db.Attempt.skip_reason != "forgot")
        )
        non_forgot_attempted_ids = set(session.exec(stmt).all())
        statement = select(db.Exercise).where(
            db.Exercise.quality != "archived",
            db.Exercise.quality != "too_easy",
            db.Exercise.quality != "too_hard",
            db.Exercise.quality != "bad_quality"
        )
        all_ex = session.exec(statement).all()
        due_count = len([ex for ex in all_ex if ex.id not in non_forgot_attempted_ids])
        if due_count >= 20:
            raise ValueError("Active queue is full (limit: 20). Practice due exercises first before queueing more.")

    def promote_candidate(self, candidate_id: str) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            self._enforce_queue_limit(session)
            return db.promote_candidate(session, candidate_id)

    def promote_source_topic(
        self,
        source_id: str,
        topic_path: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with db.connect(self.db_path) as session:
            candidates = db.list_candidates(session, source_id, topic_path=topic_path)
            promoted_exercises = []
            count_limit = limit if limit is not None else len(candidates)
            for c in candidates[:count_limit]:
                self._enforce_queue_limit(session)
                ex = db.promote_candidate(session, c["id"])
                promoted_exercises.append(ex)
            return promoted_exercises

    def start_practice_session(
        self,
        topic: str | None = None,
        limit: int = 5,
        reset: bool = False,
        campaign_id: str | None = None,
    ) -> dict[str, Any]:
        self.log.info(f"Starting practice session (topic={topic}, limit={limit}, reset={reset}, campaign_id={campaign_id})")
        # Resolve matching campaign for auto-consolidation
        resolved_campaign_id = campaign_id
        if not resolved_campaign_id and topic:
            try:
                with db.connect(self.db_path) as session:
                    campaign = session.exec(
                        select(db.Campaign).where(
                            (db.Campaign.topic_path == topic) |
                            (db.Campaign.topic_path.like(topic + ".%"))
                        )
                    ).first()
                    if campaign:
                        resolved_campaign_id = campaign.id
            except Exception:
                pass

        # Trigger transparent consolidation
        try:
            if resolved_campaign_id:
                self.consolidate_learner_profile(campaign_id=resolved_campaign_id)
        except Exception:
            pass

        with db.connect(self.db_path) as session:
            active_session = db.get_active_practice_session(session)
            if active_session and not reset:
                return {
                    "is_new": False,
                    "session": active_session
                }

            if active_session and reset:
                db.update_practice_session(session, active_session["id"], status="completed")

            # Get Campaign details
            campaign = None
            if resolved_campaign_id:
                campaign = session.get(db.Campaign, resolved_campaign_id)
            if not campaign:
                if topic:
                    campaign = session.exec(
                        select(db.Campaign).where(
                            (db.Campaign.topic_path == topic) |
                            (db.Campaign.topic_path.like(topic + ".%"))
                        )
                    ).first()
                if not campaign:
                    campaign = session.exec(select(db.Campaign)).first()
            if not campaign:
                # If no campaign exists, check if we have sources in the database
                sources = db.list_sources(session)
                if sources:
                    sources = sorted(sources, key=lambda x: x["created_at"], reverse=True)
                    target_source = sources[0]
                    campaign = session.exec(select(db.Campaign).where(db.Campaign.source_id == target_source["id"])).first()
                    if not campaign:
                        import uuid
                        camp_id = f"camp_{uuid.uuid4().hex[:8]}"
                        clean_title_slug = "".join(c for c in target_source["title"].lower() if c.isalnum() or c == " ").strip().replace(" ", ".")[:25]
                        if not clean_title_slug:
                            clean_title_slug = f"topic_{uuid.uuid4().hex[:8]}"

                        campaign = db.Campaign(
                            id=camp_id,
                            name=target_source["title"],
                            source_id=target_source["id"],
                            topic_path=clean_title_slug,
                            mission=target_source["mission"] or f"Practice from {target_source['title']}",
                            attack_plan_json=json.dumps([{
                                "phase": 1,
                                "topics": [clean_title_slug],
                                "criteria": {"min_attempts": 3, "min_accuracy": 0.8}
                            }]),
                            strategy_profile_json=json.dumps({"mode": "practice", "difficulty": "intermediate", "scaffolding": "medium"}),
                            syllabus_markdown=None,
                            sources_config_json=json.dumps([{
                                "source_id": target_source["id"],
                                "purpose": "Standalone study material",
                                "topics": []
                            }]),
                            active_phase_index=1,
                        )
                        session.add(campaign)
                        session.commit()
                        session.refresh(campaign)

            active_topics = []
            phase_focus = None
            if topic:
                active_topics = [topic]
            elif campaign:
                active_phase_index = campaign.active_phase_index
                attack_plan = json.loads(campaign.attack_plan_json or "[]")
                if active_phase_index < len(attack_plan):
                    phase_def = attack_plan[active_phase_index]
                    active_topics = phase_def.get("topics", [])
                    phase_focus = phase_def.get("focus")
                    if not active_topics:
                        active_topics = [campaign.topic_path]
                else:
                    active_topics = [campaign.topic_path]
            else:
                active_topics = []

            if not active_topics and campaign:
                active_topics = [campaign.topic_path]

            target_topic = active_topics[0] if active_topics else "diagnostic"

            # Check due count
            stmt = select(db.Attempt.exercise_id).where(
                (db.Attempt.skip_reason == None) | (db.Attempt.skip_reason != "forgot")
            )
            non_forgot_attempted_ids = set(session.exec(stmt).all())

            statement = select(db.Exercise).where(
                db.Exercise.quality != "archived",
                db.Exercise.quality != "too_easy",
                db.Exercise.quality != "too_hard",
                db.Exercise.quality != "bad_quality"
            )
            all_ex = session.exec(statement).all()
            if active_topics:
                filtered = []
                for ex in all_ex:
                    matches_topic = False
                    for t in active_topics:
                        if ex.topic_path == t or ex.topic_path.startswith(t + "."):
                            matches_topic = True
                            break
                    if matches_topic:
                        filtered.append(ex)
                    elif campaign and campaign.syllabus_markdown is None and campaign.source_id and ex.source_id == campaign.source_id:
                        filtered.append(ex)
            else:
                filtered = all_ex
            due_exercises = [ex for ex in filtered if ex.id not in non_forgot_attempted_ids]

            if len(due_exercises) < 3 and campaign:
                # Trigger JIT Generation!
                strategy = json.loads(campaign.strategy_profile_json or "{}")
                is_diagnostic = (strategy.get("mode") == "diagnostic" or any(t.endswith(".diagnostic") for t in active_topics))

                if is_diagnostic:
                    # Onboarding/Diagnostic mode
                    request = {
                        "task": "exercise.generate",
                        "version": 1,
                        "instructions": (
                            "You are in onboarding/diagnostic mode. "
                            f"The user's goal is: '{campaign.name}'. "
                            "Based on this goal, you must return a JSON object containing:\n"
                            "1. 'title': A suggested campaign title.\n"
                            "2. 'base_topic': A clean, dot-separated topic path namespace (e.g. 'math.quaternions' or 'devops.docker').\n"
                            "3. 'diagnostic_questions': A list of 2-3 targeted diagnostic questions to assess their level and success definition."
                        ),
                        "source": {
                            "id": None,
                            "title": campaign.name,
                            "refs": [],
                            "content": ""
                        },
                        "topic_hint": target_topic or "diagnostic",
                        "max_candidates": 3,
                        "expected_artifacts": ["diagnostic_questions"]
                    }

                    from . import connectors
                    result = connectors.invoke_command_connector(self.db_path, request)
                    diagnostics = []
                    if result.status == "ok":
                        data = result.parsed_stdout or {}
                        title = data.get("title") or campaign.name
                        base_topic = data.get("base_topic") or campaign.topic_path
                        diagnostic_questions = data.get("diagnostic_questions") or ["What is your background?", "What is your main goal?"]

                        # Update Campaign
                        campaign.name = title
                        campaign.topic_path = base_topic
                        new_plan = [
                            {
                                "phase": 0,
                                "topics": [f"{base_topic}.diagnostic"],
                                "criteria": {"min_attempts": len(diagnostic_questions), "min_accuracy": 0.0}
                            }
                        ]
                        campaign.attack_plan_json = json.dumps(new_plan)
                        session.add(campaign)
                        session.commit()

                        target_topic = f"{base_topic}.diagnostic"
                        active_topics = [f"{base_topic}.diagnostic"]

                        # Save the diagnostic questions as Exercises
                        import uuid
                        for q in diagnostic_questions:
                            cand_id = f"cand_{uuid.uuid4().hex[:8]}"
                            db.save_candidate(
                                session,
                                id=cand_id,
                                source_id=None,
                                prompt=q,
                                answer=None,
                                rubric=None,
                                topic_path=f"{base_topic}.diagnostic",
                                source_refs=[],
                                quality="diagnostic"
                            )
                            db.promote_candidate(session, cand_id)
                    else:
                        diagnostics = [result.error or "connector execution failed"]

                    db.record_generation_run(
                        session,
                        task="exercise.generate.diagnostic",
                        request=request,
                        raw_output=result.raw_stdout,
                        status=result.status,
                        diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
                    )
                else:
                    # Regular phase JIT generation
                    target_topic = active_topics[0] if active_topics else campaign.topic_path
                    if len(active_topics) > 1:
                        topic_counts = {}
                        for t in active_topics:
                            count = 0
                            for ex in all_ex:
                                if ex.topic_path == t or ex.topic_path.startswith(t + "."):
                                    count += 1
                            topic_counts[t] = count
                        target_topic = min(active_topics, key=lambda t: topic_counts[t])

                    sources_config = json.loads(campaign.sources_config_json or "[]")
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
                    source_title = campaign.name
                    custom_instructions = db.get_config(session, "prompt.exercise_generate_instructions")

                    if active_source_id:
                        full_source = db.get_source(session, active_source_id)
                        if full_source:
                            source_title = full_source["title"]
                            from .generate import resolve_source_context
                            source_content, start_line, end_line = resolve_source_context(
                                full_source["content"],
                                source_title,
                                target_topic,
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
                            purpose_inst = f" SPECIAL INSTRUCTION: The user provided this source with the intent: '{active_purpose}'. Ground the exercises in this source according to this intent."
                            if custom_instructions:
                                custom_instructions += purpose_inst
                            else:
                                custom_instructions = purpose_inst
                    else:
                        synthetic_inst = " SPECIAL INSTRUCTION: No grounding source material is available. You must synthesize practice exercises using your general knowledge, guided by the target topic and campaign mission."
                        if custom_instructions:
                            custom_instructions += synthetic_inst
                        else:
                            custom_instructions = synthetic_inst

                    active_hyps = db.list_learner_hypotheses(session, status="active", topic_path=target_topic)
                    hyp_descriptions = [h["description"] for h in active_hyps]

                    topics_set = set()
                    for ex in session.exec(select(db.Exercise)).all():
                        topics_set.add(ex.topic_path)
                    for camp in session.exec(select(db.Campaign)).all():
                        topics_set.add(camp.topic_path)
                    existing_topics = sorted(list(topics_set))

                    import uuid
                    request = generate.ExerciseGenerateRequest(
                        source_id=active_source_id,
                        source_title=source_title,
                        source_refs=source_refs,
                        topic=target_topic,
                        mission=campaign.mission,
                        existing_topics=existing_topics,
                        learner_hypotheses=hyp_descriptions if hyp_descriptions else None,
                        instructions=custom_instructions,
                        source_content=source_content,
                        strategy=strategy if strategy else None,
                        active_topics=active_topics,
                        phase_focus=phase_focus,
                    )

                    from . import connectors
                    result = connectors.invoke_command_connector(self.db_path, request.to_task_request())

                    diagnostics = []
                    if result.status == "ok":
                        val = generate.validate_exercise_generate_output(result.parsed_stdout or result.raw_stdout, default_topic=target_topic)
                        if val["candidates"]:
                            for cand in val["candidates"]:
                                cand_id = f"cand_{uuid.uuid4().hex[:8]}"
                                db.save_candidate(
                                    session,
                                    id=cand_id,
                                    source_id=active_source_id,
                                    prompt=cand["prompt"],
                                    answer=cand.get("answer"),
                                    rubric=cand.get("rubric"),
                                    topic_path=cand["topic_path"],
                                    source_refs=cand["source_refs"],
                                    difficulty=cand.get("difficulty"),
                                )
                                db.promote_candidate(session, cand_id)
                            if not val["ok"]:
                                diagnostics = val.get("diagnostics") or []
                                self.log.warning(f"JIT generate had some invalid candidates: {diagnostics}")
                        else:
                            diagnostics = val.get("diagnostics") or ["no valid candidates generated"]
                            self.log.error(f"JIT generate validation failed: {diagnostics}. Raw output: {result.raw_stdout}")
                    else:
                        diagnostics = [result.error or "connector execution failed"]

                    db.record_generation_run(
                        session,
                        task="exercise.generate.jit",
                        request=request.to_task_request(),
                        raw_output=result.raw_stdout,
                        status=result.status,
                        diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
                    )

            # Re-query due exercises after JIT generation
            stmt = select(db.Attempt.exercise_id).where(
                (db.Attempt.skip_reason == None) | (db.Attempt.skip_reason != "forgot")
            )
            non_forgot_attempted_ids = set(session.exec(stmt).all())

            statement = select(db.Exercise).where(
                db.Exercise.quality != "archived",
                db.Exercise.quality != "too_easy",
                db.Exercise.quality != "too_hard",
                db.Exercise.quality != "bad_quality"
            )
            all_ex = session.exec(statement).all()
            if active_topics:
                filtered = []
                for ex in all_ex:
                    matches_topic = False
                    for t in active_topics:
                        if ex.topic_path == t or ex.topic_path.startswith(t + "."):
                            matches_topic = True
                            break
                    if matches_topic:
                        filtered.append(ex)
                    elif campaign and campaign.syllabus_markdown is None and campaign.source_id and ex.source_id == campaign.source_id:
                        filtered.append(ex)
            else:
                filtered = all_ex
            due_exercises = [ex for ex in filtered if ex.id not in non_forgot_attempted_ids]

            due_exercises = sorted(due_exercises, key=lambda x: x.created_at)

            if not due_exercises:
                raise ValueError("no active exercises in queue; ingest and queue sources first")

            selected = due_exercises[:limit]
            import uuid
            exercise_ids = [ex.id for ex in selected]

            session_id = f"sess_{uuid.uuid4().hex[:8]}"
            ps = db.create_practice_session(session, session_id, exercise_ids)
            return {
                "is_new": True,
                "session": ps
            }

    def get_active_practice_session(self) -> dict[str, Any] | None:
        with db.connect(self.db_path) as session:
            return db.get_active_practice_session(session)

    def reveal_prompt(self, session_id: str | None = None) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            target_session_id = session_id
            if not target_session_id:
                active = db.get_active_practice_session(session)
                if not active:
                    raise ValueError("no active practice session; start one first")
                target_session_id = active["id"]

            ps = db.get_practice_session(session, target_session_id)
            if ps is None:
                raise ValueError(f"unknown practice session: {target_session_id}")

            if ps["status"] == "completed":
                raise ValueError(f"practice session {target_session_id} is already completed")

            index = ps["current_index"]
            exercise_ids = ps["exercise_ids"]
            if index >= len(exercise_ids):
                db.update_practice_session(session, target_session_id, status="completed")
                raise ValueError(f"practice session {target_session_id} is completed")

            exercise_id = exercise_ids[index]
            ex = session.get(Exercise, exercise_id)
            if not ex:
                raise ValueError(f"error: exercise {exercise_id} not found in database")

            started_at = datetime.now(timezone.utc).isoformat()
            db.update_practice_session(session, target_session_id, current_attempt_started_at=started_at)

            return {
                "session_id": target_session_id,
                "exercise_id": exercise_id,
                "index": index,
                "total": len(exercise_ids),
                "prompt": ex.prompt,
                "topic_path": ex.topic_path,
                "difficulty": ex.difficulty,
                "started_at": started_at,
            }

    def submit_answer(self, user_answer: str, session_id: str | None = None) -> dict[str, Any]:
        self.log.info(f"Submitting answer (session_id={session_id}, user_answer_len={len(user_answer)})")
        with db.connect(self.db_path) as session:
            target_session_id = session_id
            if not target_session_id:
                active = db.get_active_practice_session(session)
                if not active:
                    raise ValueError("no active practice session; start one first")
                target_session_id = active["id"]

            ps = db.get_practice_session(session, target_session_id)
            if ps is None:
                raise ValueError(f"unknown practice session: {target_session_id}")

            if ps["status"] == "completed":
                raise ValueError(f"practice session {target_session_id} is already completed")

            index = ps["current_index"]
            exercise_ids = ps["exercise_ids"]
            if index >= len(exercise_ids):
                db.update_practice_session(session, target_session_id, status="completed")
                raise ValueError(f"practice session {target_session_id} is completed")

            exercise_id = exercise_ids[index]
            ex = session.get(Exercise, exercise_id)
            if not ex:
                raise ValueError(f"error: exercise {exercise_id} not found in database")

            started_at_str = ps["current_attempt_started_at"]
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

            campaign_id = None
            for camp in session.exec(select(db.Campaign)).all():
                if ex.topic_path and (ex.topic_path == camp.topic_path or ex.topic_path.startswith(camp.topic_path + ".")):
                    campaign_id = camp.id
                    break
                elif camp.source_id and ex.source_id == camp.source_id:
                    campaign_id = camp.id
                    break
                else:
                    try:
                        config = json.loads(camp.sources_config_json or "[]")
                        if ex.source_id and any(link.get("source_id") == ex.source_id for link in config):
                            campaign_id = camp.id
                            break
                    except Exception:
                        pass

            attempt_id = f"att_{uuid.uuid4().hex[:8]}"
            db.save_attempt(
                session,
                id=attempt_id,
                session_id=target_session_id,
                exercise_id=exercise_id,
                source_id=ex.source_id,
                prompt=ex.prompt,
                user_answer=user_ans,
                score=score,
                latency_seconds=latency,
                campaign_id=campaign_id,
                consolidated=False,
            )

            next_index = index + 1
            is_completed = next_index >= len(exercise_ids)
            status = "completed" if is_completed else "active"

            db.update_practice_session(
                session,
                target_session_id,
                current_index=next_index,
                current_attempt_started_at="",
                status=status
            )

            self.log.info(f"Answer submitted successfully: session_id={target_session_id}, exercise_id={exercise_id}, score={score}, latency={latency:.2f}s, status={status}")

            return {
                "session_id": target_session_id,
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

    def get_progress(self) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            attempts = db.list_attempts(session)
            if not attempts:
                return {
                    "total_attempts": 0,
                    "average_score": 0.0,
                    "average_latency_seconds": 0.0,
                    "recent_attempts": []
                }

            total = len(attempts)
            avg_score = sum(a["score"] for a in attempts) / total
            avg_latency = sum(a["latency_seconds"] for a in attempts) / total

            return {
                "total_attempts": total,
                "average_score": avg_score,
                "average_latency_seconds": avg_latency,
                "recent_attempts": attempts[:10]
            }

    def get_due_count(self, topic: str | None = None) -> int:
        with db.connect(self.db_path) as session:
            stmt = select(db.Attempt.exercise_id).where(
                (db.Attempt.skip_reason == None) | (db.Attempt.skip_reason != "forgot")
            )
            non_forgot_attempted_ids = set(session.exec(stmt).all())
            statement = select(db.Exercise).where(
                db.Exercise.quality != "archived",
                db.Exercise.quality != "too_easy",
                db.Exercise.quality != "too_hard",
                db.Exercise.quality != "bad_quality"
            )
            all_ex = session.exec(statement).all()
            if topic:
                filtered = [
                    ex for ex in all_ex
                    if ex.topic_path == topic or ex.topic_path.startswith(topic + ".")
                ]
            else:
                filtered = all_ex
            due_count = len([ex for ex in filtered if ex.id not in non_forgot_attempted_ids])
            return due_count

    def get_learner_hypotheses(self, status: str = "active") -> list[dict[str, Any]]:
        with db.connect(self.db_path) as session:
            return db.list_learner_hypotheses(session, status=status)

    def save_learner_hypothesis(self, key: str, description: str, status: str = "active") -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            statement = select(db.LearnerHypothesis).where(db.LearnerHypothesis.key == key)
            existing = session.exec(statement).first()
            if existing:
                hyp_id = existing.id
            else:
                hyp_id = f"hyp_{uuid.uuid4().hex[:8]}"
            return db.save_learner_hypothesis(session, id=hyp_id, key=key, description=description, status=status)

    def skip_active_exercise(self, reason: str, feedback: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        if reason not in ("forgot", "too_easy", "too_hard", "bad_quality"):
            raise ValueError(f"invalid skip reason: {reason}. Must be forgot, too_easy, too_hard, or bad_quality")

        with db.connect(self.db_path) as session:
            target_session_id = session_id
            if not target_session_id:
                active = db.get_active_practice_session(session)
                if not active:
                    raise ValueError("no active practice session; start one first")
                target_session_id = active["id"]

            ps = db.get_practice_session(session, target_session_id)
            if ps is None:
                raise ValueError(f"unknown practice session: {target_session_id}")

            if ps["status"] == "completed":
                raise ValueError(f"practice session {target_session_id} is already completed")

            index = ps["current_index"]
            exercise_ids = ps["exercise_ids"]
            if index >= len(exercise_ids):
                db.update_practice_session(session, target_session_id, status="completed")
                raise ValueError(f"practice session {target_session_id} is completed")

            exercise_id = exercise_ids[index]
            ex = session.get(Exercise, exercise_id)
            if not ex:
                raise ValueError(f"error: exercise {exercise_id} not found in database")

            started_at_str = ps["current_attempt_started_at"]
            if started_at_str:
                started_at = datetime.fromisoformat(started_at_str)
                now = datetime.now(timezone.utc)
                latency = (now - started_at).total_seconds()
                if latency < 0:
                    latency = 0.0
            else:
                latency = 0.0

            campaign_id = None
            if ex.topic_path:
                for camp in session.exec(select(db.Campaign)).all():
                    if ex.topic_path == camp.topic_path or ex.topic_path.startswith(camp.topic_path + "."):
                        campaign_id = camp.id
                        break

            attempt_id = f"att_{uuid.uuid4().hex[:8]}"
            db.save_attempt(
                session,
                id=attempt_id,
                session_id=target_session_id,
                exercise_id=exercise_id,
                source_id=ex.source_id,
                prompt=ex.prompt,
                user_answer="[SKIPPED]",
                score=0.0,
                latency_seconds=latency,
                skip_reason=reason,
                feedback=feedback,
                campaign_id=campaign_id,
                consolidated=False,
            )

            # Archive/update exercise quality dynamically by setting it to the skip reason
            ex.quality = reason
            ex.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(ex)

            next_index = index + 1
            is_completed = next_index >= len(exercise_ids)
            status = "completed" if is_completed else "active"

            db.update_practice_session(
                session,
                target_session_id,
                current_index=next_index,
                current_attempt_started_at="",
                status=status
            )

            return {
                "session_id": target_session_id,
                "exercise_id": exercise_id,
                "attempt_id": attempt_id,
                "skip_reason": reason,
                "feedback": feedback,
                "is_session_completed": is_completed,
                "next_index": next_index,
                "total_exercises": len(exercise_ids),
            }

    def correct_last_attempt(
        self,
        score: float = 1.0,
        feedback: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            statement = select(db.Attempt)
            if session_id:
                statement = statement.where(db.Attempt.session_id == session_id)
            else:
                active_sess = db.get_active_practice_session(session)
                if active_sess:
                    statement = statement.where(db.Attempt.session_id == active_sess["id"])

            statement = statement.order_by(db.Attempt.created_at.desc())
            last_attempt = session.exec(statement).first()
            if not last_attempt:
                raise ValueError("No attempts found to correct")

            last_attempt.score = score
            last_attempt.consolidated = False
            if feedback:
                last_attempt.feedback = feedback
            session.add(last_attempt)
            session.commit()
            session.refresh(last_attempt)
            return db._attempt_from_model(last_attempt)

    def add_learner_feedback(
        self,
        content: str,
        campaign_id: str | None = None,
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            target_campaign_id = campaign_id
            target_attempt_id = attempt_id
            topic_path = None

            if target_attempt_id:
                att = session.get(db.Attempt, target_attempt_id)
                if not att:
                    raise ValueError(f"Attempt {target_attempt_id} not found")
                target_campaign_id = att.campaign_id
            elif not target_campaign_id:
                last_attempt_stmt = select(db.Attempt).order_by(db.Attempt.created_at.desc()).limit(1)
                last_attempt = session.exec(last_attempt_stmt).first()
                if last_attempt:
                    target_campaign_id = last_attempt.campaign_id

            if target_campaign_id:
                campaign = session.get(db.Campaign, target_campaign_id)
                if campaign:
                    topic_path = campaign.topic_path

            # Save raw feedback as learner hypothesis
            hyp_id = f"hyp_feedback_{uuid.uuid4().hex[:8]}"
            res = db.save_learner_hypothesis(
                session,
                id=hyp_id,
                key=f"feedback.user.{uuid.uuid4().hex[:8]}",
                description=content,
                status="active",
                topic_path=topic_path,
                attempt_id=target_attempt_id,
            )
            return res

    def consolidate_learner_profile(self, campaign_id: str | None = None) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            if campaign_id is None:
                campaigns = session.exec(select(db.Campaign)).all()
                if not campaigns:
                    return self._consolidate_global_fallback(session)
                results = []
                all_hypotheses = []
                all_diagnostics = []
                for c in campaigns:
                    res = self._consolidate_single_campaign(session, c.id)
                    results.append(res)
                    all_hypotheses.extend(res.get("hypotheses") or [])
                    all_diagnostics.extend(res.get("diagnostics") or [])
                return {
                    "status": "ok",
                    "campaigns": results,
                    "hypotheses": all_hypotheses,
                    "diagnostics": all_diagnostics
                }
            else:
                return self._consolidate_single_campaign(session, campaign_id)

    def _consolidate_global_fallback(self, session: Any) -> dict[str, Any]:
        statement = select(db.Attempt).order_by(db.Attempt.created_at.desc()).limit(20)
        attempts = session.exec(statement).all()

        active_hyps = db.list_learner_hypotheses(session, status="active")
        hyp_descriptions = [h["description"] for h in active_hyps]

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

        custom_consolidate_instructions = db.get_config(session, "prompt.profile_consolidate_instructions")

        default_consolidate_instructions = (
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
            "instructions": custom_consolidate_instructions or default_consolidate_instructions,
            "attempts": formatted_attempts,
            "active_hypotheses": hyp_descriptions,
        }

        result = connectors.invoke_command_connector(self.db_path, request)

        diagnostics = []
        saved_hypotheses = []
        if result.status == "ok":
            raw_data = result.parsed_stdout
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception as exc:
                    diagnostics.append(f"Failed to parse raw output as JSON: {exc}")

            hypotheses_to_save = []
            if isinstance(raw_data, dict):
                hypotheses_to_save = raw_data.get("hypotheses") or []
                if not isinstance(hypotheses_to_save, list):
                    hypotheses_to_save = []
            elif isinstance(raw_data, list):
                hypotheses_to_save = raw_data

            consolidated_keys = {hyp.get("key") for hyp in hypotheses_to_save if hyp.get("key")}

            # Deactivate active hypotheses that are no longer reported
            active_stmt = select(db.LearnerHypothesis).where(db.LearnerHypothesis.status == "active")
            for existing_hyp in session.exec(active_stmt).all():
                if existing_hyp.key not in consolidated_keys:
                    existing_hyp.status = "resolved"
                    existing_hyp.updated_at = datetime.now(timezone.utc).isoformat()
                    session.add(existing_hyp)

            for idx, hyp in enumerate(hypotheses_to_save):
                if not isinstance(hyp, dict):
                    diagnostics.append(f"Hypothesis at index {idx} is not a dict")
                    continue
                key = hyp.get("key")
                description = hyp.get("description")
                if not key or not description:
                    diagnostics.append(f"Hypothesis at index {idx} missing key or description")
                    continue

                stmt = select(db.LearnerHypothesis).where(db.LearnerHypothesis.key == key)
                existing = session.exec(stmt).first()
                if existing:
                    hyp_id = existing.id
                else:
                    hyp_id = f"hyp_{uuid.uuid4().hex[:8]}"

                saved = db.save_learner_hypothesis(
                    session,
                    id=hyp_id,
                    key=key,
                    description=description,
                    status="active"
                )
                saved_hypotheses.append(saved)

            for a in attempts:
                a.consolidated = True
                session.add(a)
            session.commit()
        else:
            diagnostics.append(result.error or "connector execution failed")

        db.record_generation_run(
            session,
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
            "hypotheses": saved_hypotheses,
            "diagnostics": diagnostics,
        }

    def _evaluate_campaign_phase_advancement(self, session: Any, campaign: db.Campaign) -> None:
        try:
            attack_plan = json.loads(campaign.attack_plan_json)
        except Exception:
            return

        if not isinstance(attack_plan, list) or not attack_plan:
            return

        advanced = False
        while campaign.active_phase_index < len(attack_plan):
            phase_idx = campaign.active_phase_index
            phase_def = attack_plan[phase_idx]

            criteria = phase_def.get("criteria", {})
            phase_topics = phase_def.get("topics", [])

            min_attempts = criteria.get("min_attempts", 0)
            min_accuracy = criteria.get("min_accuracy", 0.0)

            if not phase_topics:
                campaign.active_phase_index += 1
                advanced = True
                continue

            stmt = (
                select(db.Attempt, db.Exercise)
                .join(db.Exercise, db.Attempt.exercise_id == db.Exercise.id)
                .where(db.Attempt.campaign_id == campaign.id)
            )
            results = session.exec(stmt).all()

            phase_attempts = []
            for attempt, exercise in results:
                if attempt.skip_reason and attempt.skip_reason != "forgot":
                    continue
                for t in phase_topics:
                    if exercise.topic_path == t or exercise.topic_path.startswith(t + "."):
                        phase_attempts.append(attempt)
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
            try:
                journal = json.loads(campaign.pedagogical_journal_json or "[]")
            except Exception:
                journal = []

            performance_snapshot = {
                "attempts": attempts_count,
                "accuracy": average_score,
                "average_latency_seconds": sum(a.latency_seconds for a in phase_attempts) / attempts_count if attempts_count > 0 else 0.0
            }

            active_hyps = db.list_learner_hypotheses(session, status="active", topic_path=campaign.topic_path)
            hyps_snapshot = [{"key": h["key"], "description": h["description"]} for h in active_hyps]

            journal_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_phase_index": phase_idx,
                "action": "PHASE_ADVANCE",
                "trigger": f"Passed Phase {phase_idx} criteria ({attempts_count} attempts, {average_score*100:.1f}% accuracy)",
                "hypothesis": f"User demonstrated mastery of topics: {', '.join(phase_topics)}",
                "status": "resolved",
                "performance_snapshot": performance_snapshot,
                "plan_snapshot": attack_plan,
                "syllabus_snapshot": campaign.syllabus_markdown,
                "hypotheses_snapshot": hyps_snapshot
            }
            journal.append(journal_entry)
            campaign.pedagogical_journal_json = json.dumps(journal)

        if advanced:
            campaign.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(campaign)
            session.commit()

    def _consolidate_single_campaign(self, session: Any, campaign_id: str) -> dict[str, Any]:
        campaign = session.get(db.Campaign, campaign_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found")

        self.log.info(f"Consolidating campaign '{campaign_id}' ('{campaign.name}')")
        if campaign.active_phase_index > 0:
            self._evaluate_campaign_phase_advancement(session, campaign)

        topic_path = campaign.topic_path

        # 1. Query unconsolidated Attempts for this campaign
        attempts_stmt = select(db.Attempt).where(
            (db.Attempt.consolidated == False) &
            (
                (db.Attempt.campaign_id == campaign_id) |
                (db.Attempt.exercise_id.in_(
                    select(db.Exercise.id).where(
                        (db.Exercise.topic_path == topic_path) |
                        (db.Exercise.topic_path.like(topic_path + ".%"))
                    )
                ))
            )
        )
        attempts = session.exec(attempts_stmt).all()

        # 2. Query active user feedback hypotheses for this campaign/topic
        feedback_stmt = select(db.LearnerHypothesis).where(
            (db.LearnerHypothesis.status == "active") &
            (db.LearnerHypothesis.key.like("feedback.user.%")) &
            (
                (db.LearnerHypothesis.topic_path == topic_path) |
                (db.LearnerHypothesis.topic_path.like(topic_path + ".%"))
            )
        )
        feedback_hyps = session.exec(feedback_stmt).all()

        sources_config = json.loads(campaign.sources_config_json or "[]")
        has_unmapped_source = any(not link.get("topics") for link in sources_config)

        if not attempts and not feedback_hyps and not has_unmapped_source:
            self.log.info(f"Consolidation skipped for campaign '{campaign_id}': no new attempts, active feedback, or unmapped sources")
            return {
                "status": "skipped",
                "campaign_id": campaign_id,
                "diagnostics": ["No new attempts, active feedback, or unmapped sources since last consolidation"]
            }

        # Format attempts for LLM payload
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

        # Get active hypotheses
        active_hyps = db.list_learner_hypotheses(session, status="active", topic_path=topic_path)

        hyp_descriptions = []
        for h in active_hyps:
            desc = h["description"]
            att_id = h.get("attempt_id")
            if att_id:
                att = session.get(db.Attempt, att_id)
                if att:
                    desc += f" (Logged on Exercise: prompt='{att.prompt}', user_answer='{att.user_answer or ''}', score={att.score})"
            hyp_descriptions.append(desc)

        strategy_profile = {}
        if campaign.strategy_profile_json:
            try:
                strategy_profile = json.loads(campaign.strategy_profile_json)
            except Exception:
                pass

        # Parse Pedagogical Journal and extract the latest baseline plan
        try:
            journal = json.loads(campaign.pedagogical_journal_json or "[]")
        except Exception:
            journal = []

        latest_baseline_plan = []
        for entry in reversed(journal):
            if entry.get("action") in ("CREATE", "PIVOT"):
                latest_baseline_plan = entry.get("plan_snapshot") or []
                break

        # Token Optimization: Clean resolved journal entries
        prompt_journal = []
        for entry in journal:
            cleaned = entry.copy()
            if cleaned.get("status") != "active":
                cleaned.pop("plan_snapshot", None)
                cleaned.pop("performance_snapshot", None)
            prompt_journal.append(cleaned)

        # Token Optimization: Prune completed phases from current plan
        try:
            current_plan = json.loads(campaign.attack_plan_json)
        except Exception:
            current_plan = []

        active_idx = campaign.active_phase_index
        prompt_current_plan = []
        for idx, phase in enumerate(current_plan):
            if idx < active_idx:
                prompt_current_plan.append({
                    "phase": idx,
                    "status": "completed",
                    "topics": phase.get("topics", []),
                })
            else:
                prompt_current_plan.append(phase)

        # Collect linked sources information
        linked_sources = []
        sources_config = json.loads(campaign.sources_config_json or "[]")
        for link in sources_config:
            sid = link["source_id"]
            src_rec = session.get(db.Source, sid)
            if src_rec:
                from .generate import parse_markdown_headings
                headings = parse_markdown_headings(src_rec.content)
                outline = [f"{'#' * h['level']} {h['title']}" for h in headings]
                linked_sources.append({
                    "source_id": sid,
                    "title": src_rec.title,
                    "purpose": link.get("purpose", ""),
                    "content_preview": src_rec.content[:1500],
                    "outline": outline[:100],
                })

        # Prep task request JSON
        custom_consolidate_instructions = db.get_config(session, "prompt.profile_consolidate_instructions")

        default_consolidate_instructions = (
            "Analyze the learner's recent practice attempts, user feedback, and goals.\n"
            "Refine the campaign mission instructions to better match the user's focus.\n"
            "Calibrate the strategy profile parameters (set mode to 'practice' or 'diagnostic', difficulty to 'beginner', 'intermediate', or 'advanced', and scaffolding to 'high', 'medium', or 'low').\n"
            "Review the pedagogical journal history. Note that stable, consistent progression is highly preferred.\n"
            "Only change/revise the attack plan if the user is stuck, exhibits major prerequisites gaps, or pivots interest.\n\n"
            "ADDITIONAL PEDAGOGICAL GUIDELINES:\n"
            "1. Self-Stated Constraints & Timeline-Awareness: Analyze the user's self-stated availability, constraints, target deadlines, or upcoming milestones. "
            "If the user indicates a tight timeline or immediate target, compress the attack plan to focus purely on the highest-leverage active topics, and scale down completion criteria (e.g. min_attempts) to fit the time horizon. "
            "If no deadline exists, design a progressive, comprehensive path optimized for long-term retention.\n"
            "2. Goal-Based Progression: If the active phase index is 0 (diagnostic onboarding), you MUST design a comprehensive syllabus outline (in markdown) and the initial study plan starting from Phase 1.\n"
            "3. Structured Outputs: Use the 'thinking' field for all your internal reasoning, constraints analysis, and pedagogical decision making. Ensure all other keys strictly match the output schema."
        )

        from .schemas import get_schema_instruction, ProfileConsolidateResponse
        schema_instruction = get_schema_instruction("profile.consolidate")
        instructions = (custom_consolidate_instructions or default_consolidate_instructions) + schema_instruction

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
                "strategy_profile": strategy_profile,
                "linked_sources": linked_sources,
            },
            "active_hypotheses": hyp_descriptions,
        }

        result = connectors.invoke_command_connector(self.db_path, request)

        diagnostics = []
        saved_hypotheses = []

        if result.status == "ok":
            raw_data = result.parsed_stdout
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception as exc:
                    diagnostics.append(f"Failed to parse raw output as JSON: {exc}")

            if isinstance(raw_data, dict):
                try:
                    # Validate raw output against Pydantic schema
                    ProfileConsolidateResponse.model_validate(raw_data)
                except Exception as exc:
                    self.log.warning(f"Profile consolidation response validation warning: {exc}")
                    diagnostics.append(f"Response validation warning: {exc}")
            else:
                raw_data = {}

            # 1. Update Campaign Mission if LLM returned refined_mission
            refined_mission = raw_data.get("refined_mission")
            if refined_mission:
                campaign.mission = refined_mission

            # 2. Update Campaign Strategy if LLM returned calibrated_strategy
            calibrated_strategy = raw_data.get("calibrated_strategy")
            if calibrated_strategy:
                campaign.strategy_profile_json = json.dumps(calibrated_strategy)

            # 3. Update Attack Plan if LLM returned revised_attack_plan
            revised_attack_plan = raw_data.get("revised_attack_plan")
            if revised_attack_plan:
                campaign.attack_plan_json = json.dumps(revised_attack_plan)

            # 4. Update Syllabus Markdown if LLM returned it
            syllabus_markdown = raw_data.get("syllabus_markdown")
            if syllabus_markdown:
                campaign.syllabus_markdown = syllabus_markdown

            # 5. Update Source Mappings if LLM returned them
            source_topic_mappings = raw_data.get("source_topic_mappings") or {}
            try:
                sources_config = json.loads(campaign.sources_config_json or "[]")
            except Exception:
                sources_config = []

            updated_sources_config = []
            for link in sources_config:
                sid = link.get("source_id")
                if sid in source_topic_mappings:
                    link["topics"] = source_topic_mappings[sid]
                updated_sources_config.append(link)

            campaign.sources_config_json = json.dumps(updated_sources_config)

            # 6. Append Journal Entry if LLM returned journal_entry
            new_journal_entry = raw_data.get("journal_entry")
            if new_journal_entry:
                try:
                    current_journal = json.loads(campaign.pedagogical_journal_json or "[]")
                except Exception:
                    current_journal = []

                # Fetch performance snapshot at the moment of change
                try:
                    curr_plan = revised_attack_plan or json.loads(campaign.attack_plan_json)
                    phase_def = curr_plan[campaign.active_phase_index]
                    phase_topics = phase_def.get("topics", [])
                except Exception:
                    phase_topics = []

                attempts_stmt = select(db.Attempt).where(db.Attempt.campaign_id == campaign.id)
                all_attempts = session.exec(attempts_stmt).all()
                phase_attempts = []
                for a in all_attempts:
                    if a.skip_reason and a.skip_reason != "forgot":
                        continue
                    ex = session.get(db.Exercise, a.exercise_id)
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

                active_hyps = db.list_learner_hypotheses(session, status="active", topic_path=campaign.topic_path)
                hyps_snapshot = [{"key": h["key"], "description": h["description"]} for h in active_hyps]

                entry_to_save = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "active_phase_index": campaign.active_phase_index,
                    "action": new_journal_entry.get("action", "CALIBRATE_STRATEGY"),
                    "trigger": new_journal_entry.get("trigger", "Profile consolidation"),
                    "hypothesis": new_journal_entry.get("hypothesis", ""),
                    "status": new_journal_entry.get("status", "resolved"),
                    "performance_snapshot": perf_snapshot,
                    "plan_snapshot": new_journal_entry.get("plan_snapshot") or revised_attack_plan or current_plan,
                    "syllabus_snapshot": campaign.syllabus_markdown,
                    "hypotheses_snapshot": hyps_snapshot
                }
                current_journal.append(entry_to_save)
                campaign.pedagogical_journal_json = json.dumps(current_journal)

            session.add(campaign)

            # 7. Process returned hypotheses
            hypotheses_to_save = raw_data.get("hypotheses") or []
            if not isinstance(hypotheses_to_save, list):
                hypotheses_to_save = []

            consolidated_keys = {hyp.get("key") for hyp in hypotheses_to_save if hyp.get("key")}

            # Deactivate active hypotheses matching this topic hierarchy that are no longer reported
            campaign_hyps_stmt = select(db.LearnerHypothesis).where(
                (db.LearnerHypothesis.status == "active") &
                (
                    (db.LearnerHypothesis.topic_path == topic_path) |
                    (db.LearnerHypothesis.topic_path.like(topic_path + ".%"))
                )
            )
            for existing_hyp in session.exec(campaign_hyps_stmt).all():
                if existing_hyp.key not in consolidated_keys:
                    existing_hyp.status = "resolved"
                    existing_hyp.updated_at = datetime.now(timezone.utc).isoformat()
                    session.add(existing_hyp)

            for idx, hyp in enumerate(hypotheses_to_save):
                if not isinstance(hyp, dict):
                    diagnostics.append(f"Hypothesis at index {idx} is not a dict")
                    continue
                key = hyp.get("key")
                description = hyp.get("description")
                if not key or not description:
                    diagnostics.append(f"Hypothesis at index {idx} missing key or description")
                    continue

                stmt = select(db.LearnerHypothesis).where(db.LearnerHypothesis.key == key)
                existing = session.exec(stmt).first()
                if existing:
                    hyp_id = existing.id
                else:
                    hyp_id = f"hyp_{uuid.uuid4().hex[:8]}"

                topic_path_hyp = hyp.get("topic_path") or topic_path
                saved = db.save_learner_hypothesis(
                    session,
                    id=hyp_id,
                    key=key,
                    description=description,
                    status="active",
                    topic_path=topic_path_hyp
                )
                saved_hypotheses.append(saved)

            # 8. Set consolidated=True for processed attempts
            for a in attempts:
                a.consolidated = True
                session.add(a)

            session.commit()

            # Evaluate phase advancement now that plan has been generated/calibrated
            self._evaluate_campaign_phase_advancement(session, campaign)

        else:
            diagnostics.append(result.error or "connector execution failed")

        db.record_generation_run(
            session,
            task="profile.consolidate",
            request=request,
            raw_output=result.raw_stdout,
            status=result.status,
            diagnostics={"diagnostics": diagnostics, "stderr": result.stderr_tail},
        )

        if result.status != "ok":
            raise ValueError(f"Profile consolidation failed: {result.error or 'connector execution failed'}")

        if result.status == "ok":
            self.log.info(f"Consolidation for campaign '{campaign_id}' completed successfully: {len(saved_hypotheses)} hypotheses saved")
        else:
            self.log.error(f"Consolidation for campaign '{campaign_id}' failed: {diagnostics}")

        return {
            "status": result.status,
            "campaign_id": campaign_id,
            "hypotheses": saved_hypotheses,
            "diagnostics": diagnostics,
        }

    def save_config(self, key: str, value: str) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            return db.save_config(session, key, value)

    def get_config(self, key: str) -> str | None:
        with db.connect(self.db_path) as session:
            return db.get_config(session, key)

    def list_configs(self) -> dict[str, str]:
        with db.connect(self.db_path) as session:
            return db.list_configs(session)

    def get_all_topic_paths(self) -> list[str]:
        with db.connect(self.db_path) as session:
            topics = set()
            for ex in session.exec(select(db.Exercise)).all():
                if ex.topic_path:
                    topics.add(ex.topic_path)
            for camp in session.exec(select(db.Campaign)).all():
                if camp.topic_path:
                    topics.add(camp.topic_path)
            for cand in session.exec(select(db.Candidate)).all():
                if cand.topic_path:
                    topics.add(cand.topic_path)
            return sorted(list(topics))

    def format_topic_tree(self, flat_paths: list[str]) -> str:
        tree = {}
        for path in sorted(flat_paths):
            parts = path.split('.')
            curr = tree
            for part in parts:
                if part not in curr:
                    curr[part] = {}
                curr = curr[part]

        def _render(node, indent=0):
            lines = []
            for k, v in sorted(node.items()):
                lines.append("  " * indent + f"- {k}")
                if v:
                    lines.extend(_render(v, indent + 1))
            return lines

        return "\n".join(_render(tree))

    def create_campaign(
        self,
        goal: str,
        level: str = "intermediate",
        name: str | None = None,
        exclusions: str | None = None,
        feedback: str | None = None,
    ) -> dict[str, Any]:
        import uuid
        campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
        final_title = name or f"Learning Campaign: {goal}"

        # Clean slug for base topic path
        temp_slug = "".join(c for c in goal.lower() if c.isalnum() or c == " ").strip().replace(" ", ".")[:25]
        if not temp_slug:
            temp_slug = f"topic_{uuid.uuid4().hex[:8]}"

        attack_plan = [
            {
                "phase": 0,
                "topics": [f"{temp_slug}.diagnostic"],
                "criteria": {"min_attempts": 2, "min_accuracy": 0.0}
            }
        ]

        initial_strategy = {
            "mode": "diagnostic",
            "difficulty": level,
            "scaffolding": "high" if level == "beginner" else ("medium" if level == "intermediate" else "low")
        }

        initial_journal = [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "active_phase_index": 0,
                "action": "CREATE",
                "trigger": "Initial campaign setup",
                "hypothesis": "Onboarding/Diagnostic calibration phase",
                "status": "resolved",
                "performance_snapshot": {
                    "attempts": 0,
                    "accuracy": 0.0,
                    "average_latency_seconds": 0.0
                },
                "plan_snapshot": attack_plan,
                "syllabus_snapshot": None,
                "hypotheses_snapshot": []
            }
        ]

        self.log.info(f"Creating skeleton campaign for goal '{goal}' (id='{campaign_id}')")

        with db.connect(self.db_path) as session:
            new_campaign = db.Campaign(
                id=campaign_id,
                name=final_title,
                source_id=None,
                topic_path=temp_slug,
                mission=f"Master {goal} starting from {level} level.",
                attack_plan_json=json.dumps(attack_plan),
                pedagogical_journal_json=json.dumps(initial_journal),
                strategy_profile_json=json.dumps(initial_strategy),
                active_phase_index=0,
                syllabus_markdown=None,
                sources_config_json="[]",
            )
            session.add(new_campaign)
            session.commit()
            session.refresh(new_campaign)

            return {
                "campaign_id": new_campaign.id,
                "name": new_campaign.name,
                "source_id": None,
                "topic_path": new_campaign.topic_path,
                "mission": new_campaign.mission,
                "attack_plan": attack_plan,
                "strategy_profile": initial_strategy,
                "active_phase_index": new_campaign.active_phase_index,
                "syllabus_markdown": None,
                "sources_config": [],
            }

    def attach_source_to_campaign(
        self,
        campaign_id: str,
        source_id: str,
        purpose: str = "Primary study material",
    ) -> dict[str, Any]:
        self.log.info(f"Attaching source '{source_id}' to campaign '{campaign_id}' with purpose '{purpose}'")
        with db.connect(self.db_path) as session:
            campaign = session.get(db.Campaign, campaign_id)
            if campaign is None:
                raise ValueError(f"unknown campaign: {campaign_id}")

            source = session.get(db.Source, source_id)
            if source is None:
                raise ValueError(f"unknown source: {source_id}")

            config = json.loads(campaign.sources_config_json or "[]")
            if not any(link["source_id"] == source_id for link in config):
                config.append({
                    "source_id": source_id,
                    "purpose": purpose,
                    "topics": [],
                })
                campaign.sources_config_json = json.dumps(config)
                session.add(campaign)
                session.commit()
                session.refresh(campaign)
            return db._campaign_from_model(campaign)

    def get_campaign_history(self, campaign_id: str | None = None) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            if campaign_id is None:
                campaign = session.exec(select(db.Campaign).order_by(db.Campaign.created_at.desc())).first()
            else:
                campaign = session.get(db.Campaign, campaign_id)

            if not campaign:
                raise ValueError("Campaign not found")

            try:
                journal = json.loads(campaign.pedagogical_journal_json or "[]")
            except Exception:
                journal = []

            return {
                "campaign_id": campaign.id,
                "name": campaign.name,
                "active_phase_index": campaign.active_phase_index,
                "journal": journal
            }

    def export_campaign_syllabus(
        self,
        campaign_id: str,
        output_path: str | Path,
        format_type: str = "pdf"
    ) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            campaign = session.get(db.Campaign, campaign_id)
            if not campaign:
                raise ValueError(f"Campaign '{campaign_id}' not found")

            syllabus = campaign.syllabus_markdown
            if not syllabus:
                raise ValueError(f"No syllabus generated yet for campaign '{campaign_id}'")

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            if format_type == "pdf":
                from .pdf_generator import render_markdown_to_pdf
                render_markdown_to_pdf(syllabus, output_path)
            elif format_type == "markdown":
                output_path.write_text(syllabus, encoding="utf-8")
            else:
                raise ValueError(f"Unsupported format: {format_type}")

            return {
                "campaign_id": campaign.id,
                "name": campaign.name,
                "output_path": str(output_path.resolve()),
                "format": format_type,
            }

    def get_generation_run(self, run_id: int) -> dict[str, Any] | None:
        with db.connect(self.db_path) as session:
            run = session.get(db.GenerationRun, run_id)
            if not run:
                return None
            try:
                request = json.loads(run.request_json)
            except Exception:
                request = {}
            try:
                diagnostics = json.loads(run.diagnostics_json)
            except Exception:
                diagnostics = {}

            return {
                "id": run.id,
                "task": run.task,
                "request": request,
                "raw_output": run.raw_output,
                "status": run.status,
                "diagnostics": diagnostics,
                "created_at": run.created_at
            }
