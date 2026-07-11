"""Free-tier tests for the judge's evidence-verbatim check (no model calls).

The discard mechanism is anti-reward-hacking machinery: a judge pass without
a verbatim quote from the judged output doesn't count. It must not discard
HONEST quotes that differ only by JSON escaping (2026-07-11: LaTeX-heavy
outputs had every honest pass discarded as unproven — \\[ in the decoded
quote vs \\\\[ in the raw JSON source).
"""
from dojo.evals.runner import _evidence_core, evidence_haystacks


class TestEvidenceHaystacks:
    def test_latex_evidence_matches_raw_json_output(self):
        raw_output = '{"prompt": "Differentiate:\\n\\n\\\\[f(x)=(3x+1)^4\\\\]\\n\\nFind \\\\(f\'(x)\\\\)."}'
        judge_quote = "\\[f(x)=(3x+1)^4\\]"  # decoded, as the judge reads it
        core = _evidence_core(judge_quote)
        assert any(core in h for h in evidence_haystacks(raw_output))

    def test_plain_and_newline_evidence_still_match(self):
        raw_output = '{"feedback": "Right tense;\\naller takes être."}'
        core = _evidence_core("aller takes être")
        assert any(core in h for h in evidence_haystacks(raw_output))

    def test_fabricated_evidence_still_fails(self):
        raw_output = '{"prompt": "Differentiate \\\\[x^2\\\\]"}'
        core = _evidence_core("\\[x^3+9\\]")
        assert not any(core in h for h in evidence_haystacks(raw_output))
