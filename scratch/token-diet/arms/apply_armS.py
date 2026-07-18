"""ArmS: semantic-only validation. Apply on top of ArmJ templates.
Reject only semantic wrongness; coerce formatting variance; clip display-only
overflow. Run from repo root. Idempotent-ish (checks before editing)."""
import re
from pathlib import Path

ROOT = Path("/Users/stans/projects/dojo")


def sub(path, old, new, must=True):
    p = ROOT / path
    t = p.read_text(encoding="utf-8")
    if old not in t:
        if must:
            raise SystemExit(f"ANCHOR MISSING in {path}: {old[:60]!r}")
        return
    p.write_text(t.replace(old, new), encoding="utf-8")
    print(f"patched {path}")


# 1. Grade evidence: drop the word-cap REJECTION (verbatim-substring invariant
#    stays hard in apply_grade); storage is clipped there instead.
sub("src/dojo/schemas.py",
    """    _cap_evidence = field_validator("evidence")(
        _cap_words("evidence", _limits.GRADE_EVIDENCE_WORDS)
    )
""",
    "")

# 2. TEMPLATE_CAPS: evidence_words is no longer a validator a model can trip.
sub("src/dojo/limits.py",
    '        "evidence_words": GRADE_EVIDENCE_WORDS,\n',
    "")

# 3. apply_grade: clip stored evidence (bounded storage; quote stays verbatim).
sub("src/dojo/tasks/service.py",
    "    attempt.grade_evidence = result.evidence",
    "    # Storage stays bounded without ever rejecting an honest quote: a\n"
    "    # verbatim quote's prefix is still verbatim (ArmS 2026-07-17).\n"
    "    attempt.grade_evidence = \" \".join(\n"
    "        result.evidence.split()[: limits.GRADE_EVIDENCE_WORDS * 3]\n"
    "    )")

# 4. Rubric: a list of criterion strings is the same information — coerce.
sub("src/dojo/schemas.py",
    """    prompt: str = Field(min_length=1)
    answer: Optional[str] = None
    rubric: Optional[str] = None
    skill: Literal["recall", "explain", "apply", "produce", "critique", "diagnostic", "present"]
""",
    """    prompt: str = Field(min_length=1)
    answer: Optional[str] = None
    rubric: Optional[str] = None
    skill: Literal["recall", "explain", "apply", "produce", "critique", "diagnostic", "present"]

    @field_validator("rubric", mode="before")
    @classmethod
    def _rubric_tolerates_lists(cls, v):
        \"\"\"A list of criterion strings carries the same information as the
        dash-bullet string the contract asks for — coerce instead of burning
        a full re-generation on formatting variance (ArmS 2026-07-17).\"\"\"
        if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            return "\\n".join(
                x.strip() if x.strip().startswith("-") else f"- {x.strip()}" for x in v
            )
        return v
""")

# 5. Topic summary is display-only: clip at the cap, never reject.
sub("src/dojo/schemas.py",
    """    _cap_summary = field_validator("summary")(
        _cap_words("summary", _limits.PLAN_TOPIC_SUMMARY_WORDS)
    )""",
    """    @field_validator("summary")
    @classmethod
    def _clip_summary(cls, v):
        \"\"\"Display-only hook text: overflow is clipped, never rejected — a
        rejection costs a whole re-generation to save a few words
        (ArmS 2026-07-17).\"\"\"
        if v and _limits.word_count(v) > _limits.PLAN_TOPIC_SUMMARY_WORDS:
            return " ".join(v.split()[: _limits.PLAN_TOPIC_SUMMARY_WORDS])
        return v""",
    must=False)

# 6. Grade template: the cap is no longer a trippable floor; state intent only.
sub("src/dojo/prompts/attempt_grade.md",
    "3. `evidence` is a COPY, never a description: ≤ {{ evidence_words }} words\n"
    "   copied from ANSWER character-for-character, with no added quotation marks.\n"
    "   Your reasoning does not go there — only the learner's own words.",
    "3. `evidence` is a COPY, never a description: a few words (not sentences)\n"
    "   copied from ANSWER character-for-character, with no added quotation marks.\n"
    "   Your reasoning does not go there — only the learner's own words.",
    must=False)

print("ArmS applied.")
