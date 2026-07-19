# W2-QCOERCE draft (apply ONLY after the bake-off completes — schemas.py
# is loaded by every battery process; an edit between batteries forks the arm)

Pre-registration: WORKBENCH "W2-QCOERCE". Evidence: 119 archived
questions-object rejections across all calibers; 3 rep2 fails with NO other
error; gemma baseline fails the same scenario the same way.

## Edit 1 — schemas.py: shared coercer next to _cap_words

```python
def _coerce_question_objects(v):
    """Models at every measured caliber sometimes emit questions as objects
    ({"question": ...} / {"text": ...} / {"q": ...}) with the content in the
    single obvious text key — semantically the contracted string (ArmS:
    coerce harmless formatting variance; 119 archived rejections). Anything
    else still rejects."""
    if isinstance(v, list):
        out = []
        for q in v:
            if isinstance(q, dict):
                keys = [k for k in ("question", "text", "q") if isinstance(q.get(k), str)]
                rest = [k for k in q if k not in ("question", "text", "q", "target_info",
                                                  "target_consent")]  # observed decoration keys? NO —
                # decision: accept dicts where EXACTLY ONE of question/text/q is a str,
                # ignore other keys entirely (observed: target_info flags ride along).
                if len(keys) == 1:
                    out.append(q[keys[0]])
                    continue
            out.append(q)
        return out
    return v
```

Wire as `@field_validator("questions", mode="before")` on Intervention and
ReflectResult, and `@field_validator("refinement_questions", mode="before")`
on PlanResult — BEFORE the word-cap validators so W1 walls apply to the
coerced strings (validator order: mode="before" runs first automatically).

Open design point resolved: ignore extra keys (observed target_info riding
along in run1) rather than requiring single-key dicts — the content key is
unambiguous; requiring exactly one CONTENT key among question/text/q, with
ties (two content keys) still rejecting.

## Edit 2 — tests/test_semantic_validation.py: new class

```python
class TestQuestionObjectCoercion:
    """W2 (2026-07-19): questions emitted as objects with one obvious text
    key coerce to strings — observed cross-caliber, 119 archived rejections."""

    def test_question_key_coerces(self):
        from dojo.schemas import ReflectResult
        r = ReflectResult(ops=[], journal="ok",
                          questions=[{"question": "Was this too hard?", "target_info": False}])
        assert r.questions == ["Was this too hard?"]

    def test_text_key_coerces(self):
        from dojo.schemas import ReflectResult
        r = ReflectResult(ops=[], journal="ok", questions=[{"text": "Skip which step?"}])
        assert r.questions == ["Skip which step?"]

    def test_ambiguous_two_content_keys_rejects(self):
        from dojo.schemas import ReflectResult
        with pytest.raises(Exception):
            ReflectResult(ops=[], journal="ok",
                          questions=[{"question": "a?", "text": "b?"}])

    def test_non_string_content_rejects(self):
        from dojo.schemas import ReflectResult
        with pytest.raises(Exception):
            ReflectResult(ops=[], journal="ok", questions=[{"question": 3}])

    def test_word_cap_wall_applies_to_coerced_string(self):
        from dojo.schemas import ReflectResult
        long_q = {"text": " ".join(["w"] * (limits.word_cap_hard(limits.REFLECT_QUESTION_WORDS) + 1))}
        with pytest.raises(Exception):
            ReflectResult(ops=[], journal="ok", questions=[long_q])

    # + same trio for PlanResult.refinement_questions and Intervention.questions
```

ReflectResult constructor signature: verify field names (ops vs insight_updates
etc.) against schemas.py at apply time — W1 tests used ReflectResult(ops=[],
journal=...) and passed, keep that shape.

## Gates
mode="before" coercion is monotone-looser at the string level → free gates:
full pytest + goldens untouched (no template change) + output-budget NOT
rebuilt (no template hash change, ok-floors only RISE on future re-measures).
Battery confirmation rides the NEXT scheduled battery (do not launch one for
this alone). Judged-quality spot-set rides the next codex spend.
