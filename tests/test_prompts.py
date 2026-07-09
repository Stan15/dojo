"""Prompt template loader tests (design/prompts.md §8).

The loader is strict because a template typo must fail here, in CI — never ship
a literal `{{ placeholder }}` to a model at a learner's expense. Golden-payload
pinning for full compiled task payloads lives with the compiler tests
(test_task_compiler.py); these tests pin loader semantics and template inventory.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from dojo import limits
from dojo.prompts import TemplateError, render, _templates_dir
from dojo.tasks.compiler import TEMPLATES

TASK_TEMPLATES = [
    "exercise_generate.md",
    "exercise_diagnostic.md",
    "attempt_grade.md",
    "campaign_reflect.md",
    "campaign_plan.md",
    "capture_route.md",
    "goal_route.md",
]

FRAGMENTS = [
    "fragments/grounding_grounded.md",
    "fragments/grounding_synthetic.md",
]


class TestInventory:
    @pytest.mark.parametrize("name", TASK_TEMPLATES + FRAGMENTS)
    def test_template_exists(self, name: str):
        assert (_templates_dir() / name).exists(), f"missing template: {name}"

    @pytest.mark.parametrize("name", TASK_TEMPLATES)
    def test_task_templates_demand_json_only_output(self, name: str):
        text = (_templates_dir() / name).read_text(encoding="utf-8")
        assert "return only this JSON" in text
        closing_lines = text.rstrip().splitlines()[-3:]
        assert any(line.startswith("Check") for line in closing_lines), (
            "every task template ends with a self-check line (craft rule 9)"
        )

    @pytest.mark.parametrize("name", TASK_TEMPLATES)
    def test_templates_hold_no_logic(self, name: str):
        text = (_templates_dir() / name).read_text(encoding="utf-8")
        for construct in ("{% ", "{{#", "{{^", "<%"):
            assert construct not in text, "templates are value-injection only — no logic"

    @pytest.mark.parametrize("kind", sorted(limits.TEMPLATE_CAPS))
    def test_every_declared_cap_is_stated_in_its_template(self, kind: str):
        """The drift gate (owner decision 2026-07-09): every validator cap a
        fulfiller can trip must appear in its template — as a PLACEHOLDER, so
        the number is injected from limits.py and can never go stale. A
        template that forgets a floor goes red here, not in a live model run
        (the failure class behind every 2026-07-09 eval triage)."""
        text = (_templates_dir() / TEMPLATES[kind]).read_text(encoding="utf-8")
        missing = [
            name for name in limits.TEMPLATE_CAPS[kind]
            if not re.search(r"\{\{\s*" + re.escape(name) + r"\s*\}\}", text)
        ]
        assert not missing, (
            f"{TEMPLATES[kind]} never states these validator caps: {missing} — "
            "a floor the model can trip must be visible in the prompt"
        )

    def test_no_stale_literal_numbers_for_declared_caps(self):
        """Belt and braces: a declared cap's literal value must not ALSO appear
        hard-coded next to 'words'/'topics' etc. in its template — that's the
        drift vector the placeholders exist to remove. Structural literals
        (score bands, rubric counts) are fine; this only patrols phrases the
        caps own ('≤ N words')."""
        for kind, caps in limits.TEMPLATE_CAPS.items():
            text = (_templates_dir() / TEMPLATES[kind]).read_text(encoding="utf-8")
            for name, value in caps.items():
                if name.endswith("_words"):
                    assert f"≤ {value} words" not in text, (
                        f"{TEMPLATES[kind]}: literal '≤ {value} words' should be the "
                        f"{{{{ {name} }}}} placeholder"
                    )


class TestRenderStrictness:
    def test_missing_placeholder_raises(self):
        with pytest.raises(TemplateError, match="user_answer"):
            render("attempt_grade.md", {"exercise_prompt": "p", "rubric_and_answer": "r"})

    def test_unknown_template_raises(self):
        with pytest.raises(TemplateError, match="not found"):
            render("does_not_exist.md", {})

    def test_value_smuggling_placeholder_raises(self):
        with pytest.raises(TemplateError, match="un-interpolated"):
            render("attempt_grade.md", {
                **limits.TEMPLATE_CAPS["attempt.grade"],
                "exercise_prompt": "p",
                "rubric_and_answer": "{{ sneaky }}",
                "user_answer": "a",
            })

    def test_extra_values_are_fine(self):
        out = render("attempt_grade.md", {
            **limits.TEMPLATE_CAPS["attempt.grade"],
            "exercise_prompt": "Translate X.",
            "rubric_and_answer": "- correct tense",
            "user_answer": "Il va.",
            "unused_extra": "ignored",
        })
        assert "Translate X." in out and "{{" not in out

    def test_non_string_values_coerced(self):
        out = render("fragments/grounding_grounded.md", {"n_items": 3})
        assert "support 3 good" in out


class TestGoldenRender:
    """Byte-level pin of a fully rendered template: any template edit must show
    up as a diff to this fixture in the same commit."""

    def test_attempt_grade_golden(self):
        out = render("attempt_grade.md", {
            **limits.TEMPLATE_CAPS["attempt.grade"],
            "exercise_prompt": "Traduisez : He would have gone.",
            "rubric_and_answer": "Answer: Il serait allé.\n- past conditional with être",
            "user_answer": "Il aurait allé.",
        })
        golden = Path(__file__).parent / "golden" / "attempt_grade.rendered.txt"
        if not golden.exists():  # bootstrap: write once, review, commit
            golden.parent.mkdir(exist_ok=True)
            golden.write_text(out + "\n", encoding="utf-8")
        assert out + "\n" == golden.read_text(encoding="utf-8"), (
            "rendered template drifted from the reviewed golden fixture; "
            "if intentional, update tests/golden/attempt_grade.rendered.txt in the same commit"
        )
