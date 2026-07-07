"""Prompt template loading.

Templates are editable markdown artifacts (design/prompts.md §8): one file per
task kind plus compiler-selected fragments. `{{ name }}` injects values only —
no logic ever lives in a template; all branching happens in the compiler by
choosing which template/fragment to render.

`render()` is strict by design: a typo'd placeholder must fail a test, not
silently ship a literal `{{ strategy_line }}` to a model.

`load_prompt()` is the legacy loader for the pre-task-contract pipeline; it dies
with that pipeline (see docs/STATE.md).
"""
from __future__ import annotations

import re
import sys
import warnings
from pathlib import Path

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _templates_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "dojo" / "prompts"
    return Path(__file__).parent


class TemplateError(ValueError):
    """A template problem is a programming/packaging bug, never a runtime shrug."""


def render(template_name: str, values: dict[str, str]) -> str:
    """Renders `template_name` (e.g. "attempt_grade.md" or "fragments/x.md")
    with value-only interpolation.

    Raises TemplateError when the template is missing, when the template needs a
    placeholder `values` doesn't provide, or when interpolation leaves any
    `{{ }}` behind (e.g. a value smuggled a placeholder in). Extra keys in
    `values` are fine — compilers may pass a superset.
    """
    path = _templates_dir() / template_name
    if not path.exists():
        raise TemplateError(f"Prompt template not found: {template_name} (broken install?)")
    text = path.read_text(encoding="utf-8")

    needed = set(_PLACEHOLDER.findall(text))
    missing = needed - values.keys()
    if missing:
        raise TemplateError(
            f"Template {template_name} needs placeholders not provided: {sorted(missing)}"
        )

    def _sub(match: re.Match) -> str:
        return str(values[match.group(1)])

    result = _PLACEHOLDER.sub(_sub, text)

    leftover = set(_PLACEHOLDER.findall(result))
    if leftover:
        raise TemplateError(
            f"Rendering {template_name} left un-interpolated placeholders {sorted(leftover)} — "
            "an injected value contained '{{ }}'."
        )
    return result.strip()


def load_prompt(filename: str, placeholders: dict[str, str]) -> str:
    """Legacy loader (pre-task-contract pipeline). Warns instead of raising on
    leftover placeholders; scheduled for deletion with that pipeline."""
    path = _templates_dir() / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt template {filename} not found.")
    template_text = path.read_text(encoding="utf-8")

    result_text = template_text
    for key, val in placeholders.items():
        placeholder_pat = re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}")
        result_text = placeholder_pat.sub(val, result_text)

    remaining = _PLACEHOLDER.findall(result_text)
    if remaining:
        warnings.warn(
            f"Prompt template {filename} contains remaining un-interpolated placeholders: "
            f"{', '.join(sorted(set(remaining)))}."
        )
    return result_text
