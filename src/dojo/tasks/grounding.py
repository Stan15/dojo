"""Source grounding: heading-window resolution (ADR 003b's mitigation).

Given a source document and a target topic, find the best-matching heading and
return a bounded window of surrounding lines — the compiler's source_slice input.
Moved verbatim from the legacy generate.py; behavior unchanged.
"""
from __future__ import annotations

import re
from typing import Any


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
