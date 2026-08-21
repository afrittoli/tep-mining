from pydantic import BaseModel

from scripts.classify_llm import (
    ModelOption,
    _build_result_model,
    _build_score_model,
    _call_mellea,
    _facet_and_values,
)

_TAXONOMY = {
    "facets": {
        "principle": {
            "description": "Why the feedback matters",
            "values": [
                {"value": "api-conventions", "description": "d1"},
                {"value": "simplicity", "description": "d2"},
            ],
        },
        "artifact": {
            "description": "What kind of artifact",
            "values": [
                {"value": "code", "description": "d3"},
            ],
        },
    }
}


def test_facet_and_values_whole_taxonomy_sorted_and_deduped() -> None:
    facet_names, all_values = _facet_and_values(_TAXONOMY, facet_scope=None)

    assert facet_names == ["principle", "artifact"]
    assert all_values == ["api-conventions", "code", "simplicity"]


def test_facet_and_values_narrows_to_one_facet() -> None:
    facet_names, all_values = _facet_and_values(_TAXONOMY, facet_scope="principle")

    assert facet_names == ["principle"]
    assert all_values == ["api-conventions", "simplicity"]


def test_build_result_model_matches_facet_and_values_enums() -> None:
    model = _build_result_model(_TAXONOMY, facet_scope=None)

    assert issubclass(model, BaseModel)
    schema = model.model_json_schema()
    match_schema = schema["$defs"]["Match"]
    facet_enum = match_schema["properties"]["facet"]["enum"]
    value_enum = match_schema["properties"]["value"]["enum"]
    assert sorted(facet_enum) == ["artifact", "principle"]
    assert sorted(value_enum) == ["api-conventions", "code", "simplicity"]


def test_build_result_model_requires_reasoning_before_matches_under_facet_split() -> None:
    model = _build_result_model(_TAXONOMY, facet_scope="principle")

    comment_result = model.model_fields["results"].annotation.__args__[0]
    field_names = list(comment_result.model_fields.keys())
    assert field_names.index("reasoning") < field_names.index("matches")
    match_schema = model.model_json_schema()["$defs"]["Match"]
    # A single-value Literal narrows to `const` in the generated JSON Schema, not `enum` - see
    # mellea-adoption.md's "const vs enum for single-value facets" note.
    assert match_schema["properties"]["facet"]["const"] == "principle"


def test_build_result_model_omits_reasoning_when_no_facet_scope() -> None:
    model = _build_result_model(_TAXONOMY, facet_scope=None)

    comment_result = model.model_fields["results"].annotation.__args__[0]
    assert "reasoning" not in comment_result.model_fields


def test_build_result_model_round_trips_valid_data() -> None:
    model = _build_result_model(_TAXONOMY, facet_scope=None)

    parsed = model.model_validate(
        {
            "results": [
                {
                    "comment_id": 1,
                    "matches": [
                        {
                            "facet": "principle",
                            "value": "simplicity",
                            "confidence": 0.8,
                            "evidence": "quote",
                        }
                    ],
                }
            ],
            "candidates": [],
        }
    )
    assert parsed.results[0].matches[0].value == "simplicity"


def test_build_result_model_rejects_value_outside_taxonomy() -> None:
    model = _build_result_model(_TAXONOMY, facet_scope=None)

    try:
        model.model_validate(
            {
                "results": [
                    {
                        "comment_id": 1,
                        "matches": [
                            {
                                "facet": "principle",
                                "value": "made-up-value",
                                "confidence": 0.5,
                                "evidence": "quote",
                            }
                        ],
                    }
                ],
                "candidates": [],
            }
        )
        raise AssertionError("expected a pydantic ValidationError")
    except Exception as exc:  # pydantic.ValidationError
        assert "made-up-value" in str(exc) or "value" in str(exc).lower()


def _comment_scores_schema(model: type[BaseModel]) -> dict:
    return model.model_json_schema()["$defs"]["CommentScores"]["properties"]["scores"]


def test_build_score_model_min_max_length_equals_total_values() -> None:
    model = _build_score_model(_TAXONOMY, facet_scope=None)

    scores_schema = _comment_scores_schema(model)
    assert scores_schema["minItems"] == 3
    assert scores_schema["maxItems"] == 3


def test_build_score_model_narrowed_to_facet_scope() -> None:
    model = _build_score_model(_TAXONOMY, facet_scope="principle")

    scores_schema = _comment_scores_schema(model)
    assert scores_schema["minItems"] == 2
    assert scores_schema["maxItems"] == 2
    score_schema = model.model_json_schema()["$defs"]["Score"]
    assert score_schema["properties"]["facet"]["const"] == "principle"


class _FakeResult:
    def __init__(self, value: str | None, error=None):
        self.value = value
        self.error = error


class _FakeSession:
    def __init__(self, result: _FakeResult):
        self._result = result
        self.calls: list[dict] = []

    def instruct(self, user_prompt, *, format, strategy, model_options):
        self.calls.append(
            {
                "user_prompt": user_prompt,
                "format": format,
                "strategy": strategy,
                "model_options": model_options,
            }
        )
        return self._result


def test_call_mellea_disables_rejection_sampling_strategy() -> None:
    output_model = _build_score_model(_TAXONOMY, facet_scope=None)
    session = _FakeSession(_FakeResult('{"results": []}'))

    _call_mellea("sys", "user prompt", session, "qwen2.5", output_model, None, None)

    assert session.calls[0]["strategy"] is None


def test_call_mellea_builds_model_options_from_system_prompt_num_ctx_temperature() -> None:
    output_model = _build_score_model(_TAXONOMY, facet_scope=None)
    session = _FakeSession(_FakeResult('{"results": []}'))

    _call_mellea("sys prompt", "user prompt", session, "qwen2.5", output_model, 8192, 0.2)

    opts = session.calls[0]["model_options"]
    assert opts[ModelOption.SYSTEM_PROMPT] == "sys prompt"
    assert opts[ModelOption.CONTEXT_WINDOW] == 8192
    assert opts[ModelOption.TEMPERATURE] == 0.2


def test_call_mellea_omits_unset_model_options() -> None:
    output_model = _build_score_model(_TAXONOMY, facet_scope=None)
    session = _FakeSession(_FakeResult('{"results": []}'))

    _call_mellea(None, "user prompt", session, "qwen2.5", output_model, None, None)

    assert session.calls[0]["model_options"] is None


def test_call_mellea_returns_parsed_content_and_meta() -> None:
    output_model = _build_score_model(_TAXONOMY, facet_scope=None)
    session = _FakeSession(_FakeResult('{"results": []}'))

    content, meta = _call_mellea("sys", "user prompt", session, "qwen2.5", output_model, None, None)

    assert content == {"results": []}
    assert meta["backend"] == "mellea"
    assert meta["model"] == "qwen2.5"
    assert isinstance(meta["duration_ms"], int)


def test_call_mellea_raises_systemexit_when_result_has_no_content() -> None:
    output_model = _build_score_model(_TAXONOMY, facet_scope=None)
    session = _FakeSession(_FakeResult(None, error="boom"))

    try:
        _call_mellea("sys", "user prompt", session, "qwen2.5", output_model, None, None)
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert "boom" in str(exc)
