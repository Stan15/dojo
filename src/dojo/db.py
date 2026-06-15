from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from sqlmodel import SQLModel, Field, Session, create_engine, select

DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "dojo" / "dojo.sqlite3"


class AIConnector(SQLModel, table=True):
    __tablename__ = "ai_connectors"
    name: str = Field(primary_key=True)
    kind: str
    argv_json: str
    input_mode: str
    output_mode: str
    timeout_seconds: int
    is_default: int = Field(default=0)
    last_test_status: Optional[str] = None
    last_test_at: Optional[str] = None
    last_test_summary: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GenerationRun(SQLModel, table=True):
    __tablename__ = "generation_runs"
    id: Optional[int] = Field(default=None, primary_key=True)
    task: str
    request_json: str
    raw_output: str
    status: str
    diagnostics_json: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Source(SQLModel, table=True):
    __tablename__ = "sources"
    id: str = Field(primary_key=True)
    title: str
    content: str
    kind: str
    path: Optional[str] = None
    mission: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Campaign(SQLModel, table=True):
    __tablename__ = "campaigns"
    id: str = Field(primary_key=True)
    name: str
    topic_path: Optional[str] = None
    mission: str
    attack_plan_json: str
    active_phase_index: int = Field(default=0)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Candidate(SQLModel, table=True):
    __tablename__ = "candidates"
    id: str = Field(primary_key=True)
    source_id: str = Field(foreign_key="sources.id")
    prompt: str
    answer: Optional[str] = None
    rubric: Optional[str] = None
    topic_path: str
    source_refs: str
    difficulty: Optional[str] = None
    quality: str = Field(default="candidate")
    generation_run_id: Optional[int] = Field(default=None, foreign_key="generation_runs.id")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Exercise(SQLModel, table=True):
    __tablename__ = "exercises"
    id: str = Field(primary_key=True)
    candidate_id: Optional[str] = Field(default=None, foreign_key="candidates.id")
    source_id: str = Field(foreign_key="sources.id")
    prompt: str
    answer: Optional[str] = None
    rubric: Optional[str] = None
    topic_path: str
    source_refs: str
    difficulty: Optional[str] = None
    quality: str = Field(default="reviewed")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PracticeSession(SQLModel, table=True):
    __tablename__ = "practice_sessions"
    id: str = Field(primary_key=True)
    status: str = Field(default="active")
    exercise_ids_json: str
    current_index: int = Field(default=0)
    current_attempt_started_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"
    id: str = Field(primary_key=True)
    session_id: Optional[str] = Field(default=None, foreign_key="practice_sessions.id")
    exercise_id: str = Field(foreign_key="exercises.id")
    source_id: str = Field(foreign_key="sources.id")
    prompt: str
    user_answer: str
    score: float
    latency_seconds: float
    skip_reason: Optional[str] = Field(default=None)
    feedback: Optional[str] = Field(default=None)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class LearnerHypothesis(SQLModel, table=True):
    __tablename__ = "learner_hypotheses"
    id: str = Field(primary_key=True)
    key: str
    description: str
    status: str = Field(default="active")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


_engines = {}

def get_engine(path: str | Path | None = None):
    db_path = Path(path) if path is not None else DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    key = str(db_path.resolve())
    if key not in _engines:
        _engines[key] = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    return _engines[key]


def connect(path: str | Path | None = None) -> Session:
    engine = get_engine(path)
    return Session(engine)


def init_db(path: str | Path | None = None) -> None:
    engine = get_engine(path)
    SQLModel.metadata.create_all(engine)


def _connector_from_model(model: AIConnector) -> dict[str, Any]:
    return {
        "name": model.name,
        "kind": model.kind,
        "argv": json.loads(model.argv_json),
        "input_mode": model.input_mode,
        "output_mode": model.output_mode,
        "timeout_seconds": model.timeout_seconds,
        "is_default": bool(model.is_default),
        "last_test_status": model.last_test_status,
        "last_test_at": model.last_test_at,
        "last_test_summary": model.last_test_summary,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _source_from_model(model: Source) -> dict[str, Any]:
    return {
        "id": model.id,
        "title": model.title,
        "content": model.content,
        "kind": model.kind,
        "path": model.path,
        "mission": model.mission,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _campaign_from_model(model: Campaign) -> dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "topic_path": model.topic_path,
        "mission": model.mission,
        "attack_plan": json.loads(model.attack_plan_json),
        "active_phase_index": model.active_phase_index,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _candidate_from_model(model: Candidate) -> dict[str, Any]:
    return {
        "id": model.id,
        "source_id": model.source_id,
        "prompt": model.prompt,
        "answer": model.answer,
        "rubric": json.loads(model.rubric) if model.rubric else None,
        "topic_path": model.topic_path,
        "source_refs": json.loads(model.source_refs),
        "difficulty": model.difficulty,
        "quality": model.quality,
        "generation_run_id": model.generation_run_id,
        "created_at": model.created_at,
    }


def _exercise_from_model(model: Exercise) -> dict[str, Any]:
    return {
        "id": model.id,
        "candidate_id": model.candidate_id,
        "source_id": model.source_id,
        "prompt": model.prompt,
        "answer": model.answer,
        "rubric": json.loads(model.rubric) if model.rubric else None,
        "topic_path": model.topic_path,
        "source_refs": json.loads(model.source_refs),
        "difficulty": model.difficulty,
        "quality": model.quality,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _session_from_model(model: PracticeSession) -> dict[str, Any]:
    return {
        "id": model.id,
        "status": model.status,
        "exercise_ids": json.loads(model.exercise_ids_json),
        "current_index": model.current_index,
        "current_attempt_started_at": model.current_attempt_started_at,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _attempt_from_model(model: Attempt) -> dict[str, Any]:
    return {
        "id": model.id,
        "session_id": model.session_id,
        "exercise_id": model.exercise_id,
        "source_id": model.source_id,
        "prompt": model.prompt,
        "user_answer": model.user_answer,
        "score": model.score,
        "latency_seconds": model.latency_seconds,
        "skip_reason": model.skip_reason,
        "feedback": model.feedback,
        "created_at": model.created_at,
    }


def _hypothesis_from_model(model: LearnerHypothesis) -> dict[str, Any]:
    return {
        "id": model.id,
        "key": model.key,
        "description": model.description,
        "status": model.status,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def save_ai_connector(
    session: Session,
    *,
    name: str,
    argv: list[str],
    kind: str = "command",
    input_mode: str = "stdin-prompt",
    output_mode: str = "stdout-json-or-text",
    timeout_seconds: int = 120,
    is_default: bool = False,
    replace: bool = False,
) -> dict[str, Any]:
    if not argv:
        raise ValueError("command connector argv cannot be empty")
    
    existing = session.get(AIConnector, name)
    if existing and not replace:
        raise ValueError(f"AI connector already exists: {name}; pass --replace to update")
        
    if is_default:
        session.execute(SQLModel.metadata.tables["ai_connectors"].update().values(is_default=0))
        
    if existing:
        existing.kind = kind
        existing.argv_json = json.dumps(argv)
        existing.input_mode = input_mode
        existing.output_mode = output_mode
        existing.timeout_seconds = timeout_seconds
        existing.is_default = int(is_default)
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        connector = existing
    else:
        connector = AIConnector(
            name=name,
            kind=kind,
            argv_json=json.dumps(argv),
            input_mode=input_mode,
            output_mode=output_mode,
            timeout_seconds=timeout_seconds,
            is_default=int(is_default),
        )
        session.add(connector)
        
    session.commit()
    session.refresh(connector)
    return _connector_from_model(connector)


def get_ai_connector(session: Session, name: str) -> dict[str, Any] | None:
    connector = session.get(AIConnector, name)
    return _connector_from_model(connector) if connector else None


def list_ai_connectors(session: Session) -> list[dict[str, Any]]:
    statement = select(AIConnector).order_by(AIConnector.is_default.desc(), AIConnector.name.asc())
    results = session.exec(statement).all()
    return [_connector_from_model(c) for c in results]


def set_default_ai_connector(session: Session, name: str) -> dict[str, Any]:
    connector = session.get(AIConnector, name)
    if connector is None:
        raise ValueError(f"unknown AI connector: {name}")
    session.execute(SQLModel.metadata.tables["ai_connectors"].update().values(is_default=0))
    connector.is_default = 1
    connector.updated_at = datetime.now(timezone.utc).isoformat()
    session.commit()
    session.refresh(connector)
    return _connector_from_model(connector)


def remove_ai_connector(session: Session, name: str, *, force: bool = False) -> dict[str, Any]:
    connector = session.get(AIConnector, name)
    if connector is None:
        raise ValueError(f"unknown AI connector: {name}")
    if bool(connector.is_default) and not force:
        raise ValueError(f"refusing to remove default connector {name}; pass --force or choose another default first")
    data = _connector_from_model(connector)
    session.delete(connector)
    session.commit()
    return data


def update_connector_test_result(
    session: Session,
    name: str,
    status: str,
    summary: str,
) -> dict[str, Any]:
    connector = session.get(AIConnector, name)
    if connector is None:
        raise ValueError(f"unknown AI connector: {name}")
    connector.last_test_status = status
    connector.last_test_at = datetime.now(timezone.utc).isoformat()
    connector.last_test_summary = summary
    connector.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(connector)
    session.commit()
    session.refresh(connector)
    return _connector_from_model(connector)


def record_generation_run(
    session: Session,
    *,
    task: str,
    request: dict[str, Any],
    raw_output: str,
    status: str,
    diagnostics: dict[str, Any],
) -> int:
    run = GenerationRun(
        task=task,
        request_json=json.dumps(request, sort_keys=True),
        raw_output=raw_output,
        status=status,
        diagnostics_json=json.dumps(diagnostics, sort_keys=True),
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run.id


def save_source(
    session: Session,
    *,
    id: str,
    title: str,
    content: str,
    kind: str,
    path: str | None = None,
    mission: str | None = None,
) -> dict[str, Any]:
    existing = session.get(Source, id)
    if existing:
        existing.title = title
        existing.content = content
        existing.kind = kind
        existing.path = path
        existing.mission = mission
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        source = existing
    else:
        source = Source(
            id=id,
            title=title,
            content=content,
            kind=kind,
            path=path,
            mission=mission,
        )
        session.add(source)
    session.commit()
    session.refresh(source)
    return _source_from_model(source)


def get_source(session: Session, id: str) -> dict[str, Any] | None:
    source = session.get(Source, id)
    return _source_from_model(source) if source else None


def list_sources(session: Session) -> list[dict[str, Any]]:
    statement = select(Source).order_by(Source.created_at.desc(), Source.id.desc())
    results = session.exec(statement).all()
    return [_source_from_model(s) for s in results]


def save_candidate(
    session: Session,
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
    existing = session.get(Candidate, id)
    if existing:
        existing.source_id = source_id
        existing.prompt = prompt
        existing.answer = answer
        existing.rubric = json.dumps(rubric) if rubric else None
        existing.topic_path = topic_path
        existing.source_refs = json.dumps(source_refs)
        existing.difficulty = difficulty
        existing.quality = quality
        existing.generation_run_id = generation_run_id
        candidate = existing
    else:
        candidate = Candidate(
            id=id,
            source_id=source_id,
            prompt=prompt,
            answer=answer,
            rubric=json.dumps(rubric) if rubric else None,
            topic_path=topic_path,
            source_refs=json.dumps(source_refs),
            difficulty=difficulty,
            quality=quality,
            generation_run_id=generation_run_id,
        )
        session.add(candidate)
    session.commit()
    session.refresh(candidate)
    return _candidate_from_model(candidate)


def get_candidate(session: Session, id: str) -> dict[str, Any] | None:
    candidate = session.get(Candidate, id)
    return _candidate_from_model(candidate) if candidate else None


def list_candidates(
    session: Session, source_id: str, topic_path: str | None = None
) -> list[dict[str, Any]]:
    if topic_path:
        statement = select(Candidate).where(
            Candidate.source_id == source_id,
            Candidate.topic_path.like(f"{topic_path}%"),
        ).order_by(Candidate.created_at.asc())
    else:
        statement = select(Candidate).where(Candidate.source_id == source_id).order_by(Candidate.created_at.asc())
    results = session.exec(statement).all()
    return [_candidate_from_model(c) for c in results]


def remove_candidate(session: Session, candidate_id: str) -> dict[str, Any]:
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise ValueError(f"unknown candidate: {candidate_id}")
    data = _candidate_from_model(candidate)
    session.delete(candidate)
    session.commit()
    return data


def promote_candidate(session: Session, candidate_id: str) -> dict[str, Any]:
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise ValueError(f"unknown candidate: {candidate_id}")
    
    exercise_id = f"ex_{candidate_id.split('_', 1)[-1]}" if "_" in candidate_id else f"ex_{candidate_id}"
    
    existing_ex = session.get(Exercise, exercise_id)
    if existing_ex:
        existing_ex.candidate_id = candidate_id
        existing_ex.source_id = candidate.source_id
        existing_ex.prompt = candidate.prompt
        existing_ex.answer = candidate.answer
        existing_ex.rubric = candidate.rubric
        existing_ex.topic_path = candidate.topic_path
        existing_ex.source_refs = candidate.source_refs
        existing_ex.difficulty = candidate.difficulty
        existing_ex.quality = "reviewed"
        existing_ex.updated_at = datetime.now(timezone.utc).isoformat()
        exercise = existing_ex
    else:
        exercise = Exercise(
            id=exercise_id,
            candidate_id=candidate_id,
            source_id=candidate.source_id,
            prompt=candidate.prompt,
            answer=candidate.answer,
            rubric=candidate.rubric,
            topic_path=candidate.topic_path,
            source_refs=candidate.source_refs,
            difficulty=candidate.difficulty,
            quality="reviewed",
        )
        session.add(exercise)
        
    session.delete(candidate)
    session.commit()
    session.refresh(exercise)
    return _exercise_from_model(exercise)


def save_campaign(
    session: Session,
    *,
    id: str,
    name: str,
    topic_path: str | None = None,
    mission: str,
    attack_plan: dict[str, Any],
    active_phase_index: int = 0,
) -> dict[str, Any]:
    existing = session.get(Campaign, id)
    if existing:
        existing.name = name
        existing.topic_path = topic_path
        existing.mission = mission
        existing.attack_plan_json = json.dumps(attack_plan)
        existing.active_phase_index = active_phase_index
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        campaign = existing
    else:
        campaign = Campaign(
            id=id,
            name=name,
            topic_path=topic_path,
            mission=mission,
            attack_plan_json=json.dumps(attack_plan),
            active_phase_index=active_phase_index,
        )
        session.add(campaign)
    session.commit()
    session.refresh(campaign)
    return _campaign_from_model(campaign)


def get_campaign(session: Session, id: str) -> dict[str, Any] | None:
    campaign = session.get(Campaign, id)
    return _campaign_from_model(campaign) if campaign else None


def create_practice_session(
    session: Session,
    id: str,
    exercise_ids: list[str],
) -> dict[str, Any]:
    ps = PracticeSession(
        id=id,
        status="active",
        exercise_ids_json=json.dumps(exercise_ids),
        current_index=0,
    )
    session.add(ps)
    session.commit()
    session.refresh(ps)
    return _session_from_model(ps)


def get_active_practice_session(session: Session) -> dict[str, Any] | None:
    statement = select(PracticeSession).where(PracticeSession.status == "active")
    ps = session.exec(statement).first()
    return _session_from_model(ps) if ps else None


def get_practice_session(session: Session, id: str) -> dict[str, Any] | None:
    ps = session.get(PracticeSession, id)
    return _session_from_model(ps) if ps else None


def update_practice_session(
    session: Session,
    id: str,
    *,
    current_index: int | None = None,
    current_attempt_started_at: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    ps = session.get(PracticeSession, id)
    if ps is None:
        raise ValueError(f"unknown practice session: {id}")
    if current_index is not None:
        ps.current_index = current_index
    if current_attempt_started_at is not None:
        ps.current_attempt_started_at = None if current_attempt_started_at == "" else current_attempt_started_at
    if status is not None:
        ps.status = status
    ps.updated_at = datetime.now(timezone.utc).isoformat()
    session.add(ps)
    session.commit()
    session.refresh(ps)
    return _session_from_model(ps)


def save_attempt(
    session: Session,
    id: str,
    session_id: Optional[str],
    exercise_id: str,
    source_id: str,
    prompt: str,
    user_answer: str,
    score: float,
    latency_seconds: float,
    skip_reason: Optional[str] = None,
    feedback: Optional[str] = None,
) -> dict[str, Any]:
    attempt = Attempt(
        id=id,
        session_id=session_id,
        exercise_id=exercise_id,
        source_id=source_id,
        prompt=prompt,
        user_answer=user_answer,
        score=score,
        latency_seconds=latency_seconds,
        skip_reason=skip_reason,
        feedback=feedback,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return _attempt_from_model(attempt)


def list_attempts(session: Session) -> list[dict[str, Any]]:
    statement = select(Attempt).order_by(Attempt.created_at.desc())
    results = session.exec(statement).all()
    return [_attempt_from_model(a) for a in results]


def save_learner_hypothesis(
    session: Session,
    id: str,
    key: str,
    description: str,
    status: str = "active",
) -> dict[str, Any]:
    existing = session.get(LearnerHypothesis, id)
    if existing:
        existing.key = key
        existing.description = description
        existing.status = status
        existing.updated_at = datetime.now(timezone.utc).isoformat()
        hypothesis = existing
    else:
        hypothesis = LearnerHypothesis(
            id=id,
            key=key,
            description=description,
            status=status,
        )
        session.add(hypothesis)
    session.commit()
    if existing:
        session.refresh(existing)
        hypothesis = existing
    else:
        session.refresh(hypothesis)
    return _hypothesis_from_model(hypothesis)


def list_learner_hypotheses(session: Session, status: Optional[str] = None) -> list[dict[str, Any]]:
    statement = select(LearnerHypothesis)
    if status is not None:
        statement = statement.where(LearnerHypothesis.status == status)
    statement = statement.order_by(LearnerHypothesis.created_at.desc())
    results = session.exec(statement).all()
    return [_hypothesis_from_model(h) for h in results]
