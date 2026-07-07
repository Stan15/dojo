from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .prompts import load_prompt
from .schemas import get_schema_instruction, ExerciseGenerateResponse


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
    source_content: str | None = None
    strategy: dict[str, Any] | None = None
    active_topics: list[str] | None = None
    phase_focus: str | None = None

    def to_task_request(self) -> dict[str, Any]:
        schema_instruction = get_schema_instruction("exercise.generate")

        if self.instructions:
            instructions = self.instructions + schema_instruction
            if self.active_topics:
                instructions += f" The active phase targets multiple topics: {', '.join(self.active_topics)}."
            if self.phase_focus:
                instructions += f" Pedagogical Focus: {self.phase_focus}"
            if self.learner_hypotheses:
                instructions += f" Design practice items that specifically address the learner's active profile hypotheses/misconceptions: {'; '.join(self.learner_hypotheses)}."
            if self.strategy:
                scaffolding = self.strategy.get("scaffolding")
                difficulty = self.strategy.get("difficulty")
                if scaffolding == "high":
                    instructions += "\nProvide extra context, helpful hints, or structural scaffolding for the learner."
                elif scaffolding == "low":
                    instructions += "\nAvoid hints, extra context, or explanatory setup; keep the prompt direct and challenging."
                if difficulty == "beginner":
                    instructions += "\nTarget fundamental/introductory concepts and keep complexity low."
                elif difficulty == "advanced":
                    instructions += "\nTarget complex, high-level combined applications or edge cases."
        else:
            active_topics_context = f"The active phase targets multiple topics: {', '.join(self.active_topics)}." if self.active_topics else ""
            phase_focus_context = f"Pedagogical Focus: {self.phase_focus}" if self.phase_focus else ""
            learner_profile_context = (
                f"Design practice items that specifically address the learner's active profile hypotheses/misconceptions: {'; '.join(self.learner_hypotheses)}."
                if self.learner_hypotheses else ""
            )
            
            strategy_context = ""
            if self.strategy:
                strat_lines = []
                scaffolding = self.strategy.get("scaffolding")
                difficulty = self.strategy.get("difficulty")
                if scaffolding == "high":
                    strat_lines.append("Provide extra context, helpful hints, or structural scaffolding for the learner.")
                elif scaffolding == "low":
                    strat_lines.append("Avoid hints, extra context, or explanatory setup; keep the prompt direct and challenging.")
                if difficulty == "beginner":
                    strat_lines.append("Target fundamental/introductory concepts and keep complexity low.")
                elif difficulty == "advanced":
                    strat_lines.append("Target complex, high-level combined applications or edge cases.")
                if strat_lines:
                    strategy_context = "\n".join(strat_lines)

            placeholders = {
                "active_topics_context": active_topics_context,
                "phase_focus_context": phase_focus_context,
                "learner_profile_context": learner_profile_context,
                "strategy_context": strategy_context,
                "schema_instructions": schema_instruction,
            }
            instructions = load_prompt("legacy_exercise_generate.md", placeholders)

        req = {
            "task": "exercise.generate",
            "version": 1,
            "instructions": instructions,
            "topic_hint": self.topic,
            "max_candidates": self.max_candidates,
            "expected_artifacts": ["topic_span", "exercise_draft"],
        }
        
        if self.source_content or self.source_id:
            req["source"] = {
                "id": self.source_id,
                "title": self.source_title,
                "refs": self.source_refs,
                "content": self.source_content,
            }

        if self.active_topics:
            req["active_topics"] = self.active_topics
        if self.phase_focus:
            req["phase_focus"] = self.phase_focus
        if self.strategy:
            req["strategy_profile"] = self.strategy
        if self.mission:
            req["mission_instruction"] = self.mission
        if self.existing_topics:
            req["existing_topics"] = self.existing_topics
        if self.learner_hypotheses:
            req["learner_profile"] = {
                "active_hypotheses": self.learner_hypotheses
            }
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


def _normalize_candidate(item: dict[str, Any], default_topic: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    prompt = item.get("prompt")
    topic_path = item.get("topic_path") or item.get("topic") or default_topic
    source_refs = None
    for key in ("source_refs", "source_ref", "provenance"):
        if key in item:
            source_refs = item[key]
            break
    if source_refs is None:
        source_refs = []
    
    extra_prompt_text = []

    for key in ("learner_tasks", "tasks", "checklist", "questions", "options"):
        val = item.get(key)
        if val:
            if isinstance(val, list):
                extra_prompt_text.append(f"\n\n### {key.replace('_', ' ').title()}:")
                for subval in val:
                    if isinstance(subval, dict):
                        lines = []
                        for k, v in subval.items():
                            lines.append(f"**{k.title()}**: {v}")
                        extra_prompt_text.append("- " + " | ".join(lines))
                    else:
                        extra_prompt_text.append(f"- {subval}")
            elif isinstance(val, dict):
                extra_prompt_text.append(f"\n\n### {key.replace('_', ' ').title()}:")
                for k, v in val.items():
                    extra_prompt_text.append(f"- **{k.title()}**: {v}")
            elif isinstance(val, str):
                extra_prompt_text.append(f"\n\n### {key.replace('_', ' ').title()}:\n{val}")

    for key in ("scaffolding_details", "scaffolding"):
        val = item.get(key)
        if val:
            if isinstance(val, dict):
                extra_prompt_text.append(f"\n\n### Scaffolding:")
                for k, v in val.items():
                    if isinstance(v, list):
                        extra_prompt_text.append(f"- **{k.title()}**:")
                        for item_v in v:
                            extra_prompt_text.append(f"  - {item_v}")
                    else:
                        extra_prompt_text.append(f"- **{k.title()}**: {v}")
            elif isinstance(val, str):
                extra_prompt_text.append(f"\n\n### Scaffolding:\n{val}")

    if extra_prompt_text:
        prompt = (prompt or "") + "\n" + "\n".join(extra_prompt_text)

    answer = (
        item.get("answer") or
        item.get("expected_answer") or
        item.get("expected_answer_elements") or
        item.get("answer_key") or
        item.get("correct_answer") or
        item.get("solution") or
        item.get("ideal_response") or
        item.get("sample_response") or
        item.get("model_rewrite") or
        item.get("sample_answer") or
        item.get("model_answer")
    )
    rubric = (
        item.get("rubric") or
        item.get("expected_response") or
        item.get("self_check") or
        item.get("success_criteria") or
        item.get("answer_key_or_rubric") or
        item.get("evaluation_rubric") or
        item.get("grading_rubric") or
        item.get("grading_criteria") or
        item.get("rubric_criteria") or
        item.get("score_guidance") or
        item.get("expected_answer_features") or
        item.get("rubric_diagnosis") or
        item.get("rubric_focus") or
        item.get("rubric_spec")
    )

    if answer is not None:
        if isinstance(answer, (dict, list)):
            answer = json.dumps(answer, ensure_ascii=False)
        else:
            answer = str(answer)

    if isinstance(source_refs, dict):
        source_refs = [source_refs]
    missing = []
    if not prompt:
        missing.append("prompt")
    if not topic_path:
        missing.append("topic_path")
    if source_refs is None:
        missing.append("source_refs")
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


def validate_exercise_generate_output(raw: str | list[Any] | dict[str, Any], default_topic: str | None = None) -> dict[str, Any]:
    try:
        data = _coerce_output(raw)
    except json.JSONDecodeError as exc:
        return {"ok": False, "candidates": [], "diagnostics": [f"malformed JSON: {exc.msg}"]}

    diagnostics: list[str] = []

    if isinstance(data, dict) and ("exercise_draft" in data or "thinking" in data):
        try:
            ExerciseGenerateResponse.model_validate(data)
        except Exception as exc:
            diagnostics.append(f"Response validation warning: {exc}")

    parent_topic = default_topic
    artifacts: list[Any] = []
    if isinstance(data, list):
        candidate_items = data
    elif isinstance(data, dict):
        if not parent_topic:
            parent_topic = data.get("topic_path") or data.get("topic")
        if not parent_topic and "exercise_draft" in data:
            draft = data["exercise_draft"]
            if isinstance(draft, dict):
                parent_topic = draft.get("topic_path") or draft.get("topic")

        candidate_items = data.get("candidates") or []
        if not candidate_items and "exercise_draft" in data:
            draft = data["exercise_draft"]
            if isinstance(draft, dict):
                candidate_items = draft.get("candidates") or []
        if not candidate_items:
            for val in data.values():
                if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict) and ("prompt" in val[0] or "topic_path" in val[0] or "topic" in val[0]):
                    candidate_items = val
                    break
        artifacts = data.get("artifacts") or []
        if not candidate_items and artifacts:
            candidate_items = [c for c in (_candidate_from_artifact(a) for a in artifacts if isinstance(a, dict)) if c]
    else:
        return {"ok": False, "candidates": [], "diagnostics": ["output must be a JSON object or array"]}

    candidates: list[dict[str, Any]] = []
    for idx, item in enumerate(candidate_items, start=1):
        if not isinstance(item, dict):
            diagnostics.append(f"candidate {idx} is not an object")
            continue
        normalized, error = _normalize_candidate(item, default_topic=parent_topic)
        if error:
            diagnostics.append(f"candidate {idx}: {error}")
        else:
            candidates.append(normalized)

    return {"ok": bool(candidates) and not diagnostics, "candidates": candidates, "diagnostics": diagnostics}


def parse_markdown_headings(content: str) -> list[dict[str, Any]]:
    lines = content.splitlines()
    headings = []
    stack = []

    for idx, line in enumerate(lines):
        line_num = idx + 1
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()

            while stack and stack[-1]["level"] >= level:
                popped = stack.pop()
                headings[popped["idx"]]["end_line"] = line_num - 1

            heading_path = [h["title"] for h in stack] + [title]

            heading_node = {
                "idx": len(headings),
                "title": title,
                "level": level,
                "start_line": line_num,
                "end_line": len(lines),
                "heading_path": heading_path,
            }
            headings.append(heading_node)
            stack.append(heading_node)

    return headings


def score_heading(heading_path: list[str], target_topic: str) -> float:
    topic_parts = [p.lower().strip() for p in target_topic.split(".") if p.strip()]
    if not topic_parts:
        return 0.0

    heading_words_by_level = []
    for title in heading_path:
        words = set(re.findall(r'\w+', title.lower()))
        heading_words_by_level.append(words)

    score = 0.0
    for i, part in enumerate(topic_parts):
        weight = 2.0 ** i
        matched = False
        for level_words in heading_words_by_level:
            if part in level_words:
                score += weight
                matched = True
                break
        if not matched:
            for title in heading_path:
                if part in title.lower():
                    score += 0.5 * weight
                    break

    leaf_part = topic_parts[-1]
    leaf_title = heading_path[-1].lower()
    leaf_words = set(re.findall(r'\w+', leaf_title))
    if leaf_part in leaf_words:
        score += 2.0 ** len(topic_parts)
    elif leaf_part in leaf_title:
        score += 0.5 * (2.0 ** len(topic_parts))

    return score


def expand_window(headings: list[dict[str, Any]], matched_idx: int, total_lines: int, min_lines: int) -> tuple[int, int]:
    matched = headings[matched_idx]
    start = matched["start_line"]
    end = matched["end_line"]

    if end - start + 1 >= min_lines:
        return start, end

    current_level = matched["level"]
    for i in range(matched_idx - 1, -1, -1):
        h = headings[i]
        if h["level"] < current_level:
            start = h["start_line"]
            end = max(end, h["end_line"])
            current_level = h["level"]
            if end - start + 1 >= min_lines:
                break

    start = max(1, start)
    end = min(total_lines, end)
    return start, end


def resolve_paragraph_window(content: str, target_topic: str, min_lines: int) -> tuple[int, int]:
    lines = content.splitlines()
    total_lines = len(lines)
    if total_lines <= min_lines:
        return 1, total_lines

    paragraphs = []
    curr_start = 1
    for idx, line in enumerate(lines):
        if not line.strip():
            if idx >= curr_start - 1:
                paragraphs.append((curr_start, idx + 1))
            curr_start = idx + 2
    if curr_start <= total_lines:
        paragraphs.append((curr_start, total_lines))

    if not paragraphs:
        return 1, min(total_lines, min_lines)

    topic_parts = [p.lower().strip() for p in target_topic.split(".") if p.strip()]

    best_para_idx = 0
    best_score = -1.0
    for p_idx, (start, end) in enumerate(paragraphs):
        para_text = "\n".join(lines[start-1:end]).lower()
        score = 0.0
        for part in topic_parts:
            if part in para_text:
                score += 1.0
        if score > best_score:
            best_score = score
            best_para_idx = p_idx

    start_para = best_para_idx
    end_para = best_para_idx

    while True:
        curr_start = paragraphs[start_para][0]
        curr_end = paragraphs[end_para][1]
        if curr_end - curr_start + 1 >= min_lines:
            break
        expanded = False
        if start_para > 0:
            start_para -= 1
            expanded = True
        if end_para < len(paragraphs) - 1:
            end_para += 1
            expanded = True
        if not expanded:
            break

    return paragraphs[start_para][0], paragraphs[end_para][1]


def resolve_source_context(content: str, title: str, target_topic: str, min_lines: int = 100) -> tuple[str, int, int]:
    if not content.strip():
        return "", 1, 1

    lines = content.splitlines()
    total_lines = len(lines)

    headings = parse_markdown_headings(content)
    best_heading_idx = -1
    best_score = 0.0

    for idx, h in enumerate(headings):
        score = score_heading(h["heading_path"], target_topic)
        if score > best_score:
            best_score = score
            best_heading_idx = idx

    if best_heading_idx != -1 and best_score > 0.0:
        start_line, end_line = expand_window(headings, best_heading_idx, total_lines, min_lines)
    else:
        start_line, end_line = resolve_paragraph_window(content, target_topic, min_lines)

    start_line = max(1, min(start_line, total_lines))
    end_line = max(start_line, min(end_line, total_lines))

    sliced_content = "\n".join(lines[start_line - 1 : end_line])
    return sliced_content, start_line, end_line
