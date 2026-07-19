"""Semantic-only validation (ArmS, token-diet campaign 2026-07-18).

Principle: reject ONLY semantic wrongness; coerce harmless formatting
variance; clip display-only overflow. Every avoided rejection saves a whole
re-generation — measured as the dominant weak-model token cost (evidence:
dev/token-diet, scratch/token-diet/baselines/). Hard floors stay hard:
enum membership, id existence, verbatim-ness, item counts.
"""
from __future__ import annotations

import pytest

from dojo import limits
from dojo.schemas import GeneratedItem, GradeResult, PlanTopic


class TestRubricListCoercion:
    def test_list_of_criteria_coerces_to_dash_bullet_string(self):
        item = GeneratedItem(
            prompt="Name the capital.", answer="Paris",
            rubric=["names Paris", "- spelling correct"], skill="recall",
        )
        assert item.rubric == "- names Paris\n- spelling correct"

    def test_string_rubric_passes_through_unchanged(self):
        item = GeneratedItem(
            prompt="Name the capital.", answer="Paris",
            rubric="- names Paris", skill="recall",
        )
        assert item.rubric == "- names Paris"

    def test_non_string_list_still_rejected(self):
        with pytest.raises(ValueError):
            GeneratedItem(prompt="p", answer="a", rubric=[1, 2], skill="recall")


class TestEvidenceCapDropped:
    def test_long_evidence_no_longer_rejected_at_schema(self):
        """The word-cap rejection fired BEFORE the verbatim check and taught
        models to shorten their analysis instead of quoting (gemma3:1b:
        14/14 grade rejections). The cap is gone; the verbatim-substring
        invariant in apply_grade stays the hallucination guard."""
        long_quote = " ".join(["word"] * (limits.GRADE_EVIDENCE_WORDS * 2))
        result = GradeResult(
            score=0.7, evidence=long_quote, feedback="ok", error_tag=None,
            knowledge_gap=False,
        )
        assert result.evidence == long_quote

    def test_storage_clip_bound_matches_service(self):
        """apply_grade clips stored evidence at 3x the word target — a
        verbatim quote's prefix is still verbatim."""
        words = ["w"] * (limits.GRADE_EVIDENCE_WORDS * 5)
        clipped = " ".join(words[: limits.GRADE_EVIDENCE_WORDS * 3])
        assert len(clipped.split()) == limits.GRADE_EVIDENCE_WORDS * 3

    def test_evidence_words_not_a_template_cap_anymore(self):
        assert "evidence_words" not in limits.TEMPLATE_CAPS.get("grade", {}), (
            "evidence cap returned to TEMPLATE_CAPS without its validator"
        )


class TestSummaryClipNotReject:
    def test_overflowing_summary_is_clipped_to_cap(self):
        overflow = " ".join(f"w{i}" for i in range(limits.PLAN_TOPIC_SUMMARY_WORDS + 7))
        topic = PlanTopic(path="a.b", kind="recall", summary=overflow)
        assert limits.word_count(topic.summary) == limits.PLAN_TOPIC_SUMMARY_WORDS
        assert topic.summary == " ".join(overflow.split()[: limits.PLAN_TOPIC_SUMMARY_WORDS])

    def test_in_cap_summary_untouched(self):
        topic = PlanTopic(path="a.b", kind="recall", summary="short hook")
        assert topic.summary == "short hook"


class TestRetryMessagePedagogy:
    """R1/R2 (2026-07-19): rejection messages teach the RIGHT fix."""

    def test_path_charset_message_teaches_words_not_regex(self):
        from dojo.schemas import PlanTopic
        import pytest as _pytest
        with _pytest.raises(Exception) as exc:
            PlanTopic(path="git/bisect run", kind="skill")
        msg = str(exc.value)
        assert "underscores" in msg and "hyphens" in msg
        assert "String should match pattern" not in msg

    def test_mass_missing_root_fields_adds_syntax_hint(self, tmp_path):
        from dojo.tasks import service
        from pydantic import ValidationError
        from dojo.schemas import PlanResult
        try:
            PlanResult.model_validate({"topics": [{"path": "a.b", "kind": "recall"}]})
        except ValidationError as e:
            root_missing = sum(1 for err in e.errors()
                               if err.get("type") == "missing" and len(err.get("loc", ())) == 1)
            assert root_missing >= 3  # premise: inner-object grab looks like this
