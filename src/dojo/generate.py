from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExerciseGenerateRequest:
    source_id: str
    source_title: str
    source_refs: list[dict[str, Any]]
    topic: str | None = None
    max_candidates: int = 5
    mission: str | None = None
    existing_topics: list[str] | None = None
    learner_hypotheses: list[str] | None = None
    instructions: str | None = None

    def to_task_request(self) -> dict[str, Any]:
        default_instructions = (
            "Draft practice candidates from the provided source references. "
            "If topic is provided, treat it as an optional parent-topic hint, not a single-topic assertion. "
            "Return candidates that may span multiple subtopics. "
            "If you realize you lack sufficient context about the user's goals, prior knowledge, or learning style for this topic to generate useful, calibrated exercises, or if you determine a pedagogical intervention is needed, you may instead generate 1–3 highly targeted, concise diagnostic questions to help personalize future sessions (set their 'quality' to 'diagnostic')."
        )
        req = {
            "task": "exercise.generate",
            "version": 1,
            "instructions": self.instructions or default_instructions,
            "source": {
                "id": self.source_id,
                "title": self.source_title,
                "refs": self.source_refs,
            },
            "topic_hint": self.topic,
            "max_candidates": self.max_candidates,
            "expected_artifacts": ["topic_span", "exercise_draft"],
        }
        if self.mission:
            req["mission_instruction"] = self.mission
        if self.existing_topics:
            req["existing_topics"] = self.existing_topics
        if self.learner_hypotheses:
            req["learner_profile"] = {
                "active_hypotheses": self.learner_hypotheses
            }
            # Append instructions to target these misconceptions/patterns
            req["instructions"] += (
                " Design practice items that specifically address the learner's "
                "active profile hypotheses/misconceptions: "
                f"{'; '.join(self.learner_hypotheses)}."
            )
        return req


def _coerce_output(raw: str | list[Any] | dict[str, Any]) -> Any:
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _candidate_from_artifact(artifact: dict[str, Any]) -> dict[str, Any] | None:
    if artifact.get("type") != "exercise_draft":
        return None
    payload = artifact.get("payload") if isinstance(artifact.get("payload"), dict) else artifact
    return payload


def _normalize_candidate(item: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    prompt = item.get("prompt")
    topic_path = item.get("topic_path") or item.get("topic")
    source_refs = item.get("source_refs") or item.get("source_ref") or item.get("provenance")
    answer = item.get("answer")
    rubric = item.get("rubric")
    if isinstance(source_refs, dict):
        source_refs = [source_refs]
    missing = [name for name, value in (("prompt", prompt), ("topic_path", topic_path), ("source_refs", source_refs)) if not value]
    if missing:
        return None, f"candidate missing required fields: {', '.join(missing)}"
    if item.get("quality") != "diagnostic":
        if answer is None and rubric is None:
            return None, "candidate needs either answer or rubric"
    normalized = {
        "prompt": prompt,
        "answer": answer,
        "rubric": rubric,
        "topic_path": topic_path,
        "source_refs": source_refs,
        "difficulty": item.get("difficulty"),
        "quality": item.get("quality", "candidate"),
        "metadata": item.get("metadata", {}),
    }
    return normalized, None


def validate_exercise_generate_output(raw: str | list[Any] | dict[str, Any]) -> dict[str, Any]:
    try:
        data = _coerce_output(raw)
    except json.JSONDecodeError as exc:
        return {"ok": False, "candidates": [], "diagnostics": [f"malformed JSON: {exc.msg}"]}

    artifacts: list[Any] = []
    if isinstance(data, list):
        candidate_items = data
    elif isinstance(data, dict):
        candidate_items = data.get("candidates") or []
        artifacts = data.get("artifacts") or []
        if not candidate_items and artifacts:
            candidate_items = [c for c in (_candidate_from_artifact(a) for a in artifacts if isinstance(a, dict)) if c]
    else:
        return {"ok": False, "candidates": [], "diagnostics": ["output must be a JSON object or array"]}

    candidates: list[dict[str, Any]] = []
    diagnostics: list[str] = []
    for idx, item in enumerate(candidate_items, start=1):
        if not isinstance(item, dict):
            diagnostics.append(f"candidate {idx} is not an object")
            continue
        normalized, error = _normalize_candidate(item)
        if error:
            diagnostics.append(f"candidate {idx}: {error}")
        else:
            candidates.append(normalized)  # type: ignore[arg-type]

    return {"ok": bool(candidates) and not diagnostics, "candidates": candidates, "diagnostics": diagnostics}
