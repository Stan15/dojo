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
from .db import Exercise, Campaign, Candidate

class DojoAPI:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        db.init_db(self.db_path)

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
                )
                
                result = connectors.invoke_command_connector(self.db_path, request.to_task_request())
                
                if result.status == "ok":
                    val = generate.validate_exercise_generate_output(result.parsed_stdout or result.raw_stdout)
                    if val["ok"]:
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
                    else:
                        diagnostics = val["diagnostics"]
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

    def get_source(self, source_id: str) -> dict[str, Any] | None:
        with db.connect(self.db_path) as session:
            source = db.get_source(session, source_id)
            if not source:
                return None
            candidates = db.list_candidates(session, source["id"])
            return {
                "id": source["id"],
                "title": source["title"],
                "kind": source["kind"],
                "path": source["path"],
                "mission": source["mission"],
                "content": source["content"],
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

    def promote_candidate(self, candidate_id: str) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
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
                ex = db.promote_candidate(session, c["id"])
                promoted_exercises.append(ex)
            return promoted_exercises

    def start_practice_session(
        self,
        topic: str | None = None,
        limit: int = 5,
        reset: bool = False,
    ) -> dict[str, Any]:
        with db.connect(self.db_path) as session:
            active_session = db.get_active_practice_session(session)
            if active_session and not reset:
                return {
                    "is_new": False,
                    "session": active_session
                }
                
            if active_session and reset:
                db.update_practice_session(session, active_session["id"], status="completed")
                
            statement = select(Exercise)
            if topic:
                all_exercises = session.exec(statement).all()
                exercises = [
                    ex for ex in all_exercises
                    if ex.topic_path == topic or ex.topic_path.startswith(topic + ".")
                ]
            else:
                exercises = session.exec(statement).all()
                
            exercises = sorted(exercises, key=lambda x: x.created_at)
            
            if not exercises:
                raise ValueError("no active exercises in queue; ingest and queue sources first")
                
            selected = exercises[:limit]
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
