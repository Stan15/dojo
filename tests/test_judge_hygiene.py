"""Free-tier tests for the judge's evidence-verbatim check (no model calls).

The discard mechanism is anti-reward-hacking machinery: a judge pass without
a verbatim quote from the judged output doesn't count. It must not discard
HONEST quotes that differ only by JSON escaping (2026-07-11: LaTeX-heavy
outputs had every honest pass discarded as unproven — \\[ in the decoded
quote vs \\\\[ in the raw JSON source).

A pass proven with SEVERAL short quotes (set-level criteria: "spans three
axes") must not be discarded either (2026-07-18: a weight-4 pass listing
four real fragments was discarded because the comma-joined list is not a
substring) — while a list containing any fabricated fragment still fails.
"""
from dojo.evals.runner import _evidence_core, evidence_haystacks, evidence_matches


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


class TestMultiQuoteEvidence:
    RAW = (
        '{"items": [{"prompt": "How comfortable are you leading a discussion?"},'
        ' {"prompt": "What meetings have you facilitated before, if any?"},'
        ' {"prompt": "What kind of practice would feel most useful?"}]}'
    )

    def test_single_whole_quote_still_matches(self):
        h = evidence_haystacks(self.RAW)
        assert evidence_matches("facilitated before, if any?", h)

    def test_comma_joined_fragment_list_matches(self):
        # The observed judge shape for set-level criteria: several short
        # verbatim quotes joined with '", "'.
        h = evidence_haystacks(self.RAW)
        ev = '"comfortable", "facilitated before", "practice would feel most useful"'
        assert evidence_matches(ev, h)

    def test_elided_quote_matches_when_both_halves_are_real(self):
        h = evidence_haystacks(self.RAW)
        assert evidence_matches("How comfortable … leading a discussion?", h)

    def test_list_with_one_fabricated_fragment_fails(self):
        h = evidence_haystacks(self.RAW)
        ev = '"comfortable", "manages conflict daily"'
        assert not evidence_matches(ev, h)

    def test_fabricated_single_quote_fails(self):
        h = evidence_haystacks(self.RAW)
        assert not evidence_matches("delegates all facilitation", h)
