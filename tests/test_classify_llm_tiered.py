"""Tests for the tiered pipeline's pure escalation-flag logic (taxonomy-and-pipeline-plan.md
Part 2) - the signals that decide which comments Pass 3 re-processes. No model call involved;
these operate on synthetic Pass 1/2 rows the way _run_tiered_batch would receive them."""

from scripts.classify_llm import (
    _low_confidence_ids,
    _missing_facet_flags,
    _nature_none_ids,
    _pass3_context_by_id,
    _quote_coverage_flags,
    _tags_context_by_id,
)

BY_ID = {
    1: {"body": "This looks fine, lgtm!"},
    2: {"body": "Why does the reconciler retry with backoff here instead of failing fast?"},
    3: {
        "body": "Split this into two PRs please, unrelated changes bundled together here "
        "for no good reason at all honestly."
    },
}

# Comment 1: nature:none ("lgtm") - should never escalate, even though its quotes don't cover
# every scaffolding word.
# Comment 2: area+nature both found; principle found but low-confidence - escalates.
# Comment 3: area found, nature missing entirely; principle found confidently, but its quotes
# leave much of the comment unaccounted for - escalates for two independent reasons.
ROWS1 = [
    {"comment_id": 1, "facet": "area", "value": "code", "confidence": 0.6, "quote": "looks fine"},
    {"comment_id": 1, "facet": "nature", "value": "none", "confidence": 0.9, "quote": "lgtm"},
    {
        "comment_id": 2,
        "facet": "area",
        "value": "code",
        "confidence": 0.6,
        "quote": "reconciler retry with backoff",
    },
    {
        "comment_id": 2,
        "facet": "nature",
        "value": "content",
        "confidence": 0.6,
        "quote": "retry with backoff here instead of failing fast",
    },
    {
        "comment_id": 3,
        "facet": "area",
        "value": "code",
        "confidence": 0.5,
        "quote": "Split this into two PRs",
    },
    # comment 3 has no nature row at all - missing.
]
ROWS2 = [
    {
        "comment_id": 2,
        "facet": "principle",
        "value": "reconciler-pattern",
        "confidence": 0.35,
        "quote": "retry with backoff",
    },
    {
        "comment_id": 3,
        "facet": "principle",
        "value": "cohesion",
        "confidence": 0.8,
        "quote": "unrelated changes bundled together",
    },
]
BATCH_IDS = {1, 2, 3}


def test_missing_facet_flags_only_comment_3() -> None:
    assert _missing_facet_flags(ROWS1, BATCH_IDS) == {3: ["nature"]}


def test_nature_none_ids() -> None:
    assert _nature_none_ids(ROWS1) == {1}


def test_low_confidence_principle_ids() -> None:
    assert _low_confidence_ids(ROWS2, "principle", 0.5) == {2}


def test_quote_coverage_excludes_nature_none_comments() -> None:
    """Without exclude_ids, comment 1's two short quotes ("looks fine", "lgtm") don't cover
    every scaffolding word/punctuation mark in "This looks fine, lgtm!" and would spuriously
    flag it - re-litigating a comment Pass 1 already confidently marked insignificant. Excluding
    nature:none comments (mirroring Pass 2's own skip rule) fixes that without hiding the real
    signal on comment 3, whose quotes genuinely leave under half its body accounted for."""
    unfiltered = _quote_coverage_flags(ROWS1 + ROWS2, BY_ID, 0.3)
    assert 1 in unfiltered  # confirms this isn't a vacuous test

    skip_ids = _nature_none_ids(ROWS1)
    flags = _quote_coverage_flags(ROWS1 + ROWS2, BY_ID, 0.3, exclude_ids=skip_ids)
    assert 1 not in flags
    assert 3 in flags
    assert 2 not in flags


def test_full_escalation_set_excludes_nature_none() -> None:
    """End-to-end union of all three signals, the way _run_tiered_batch combines them: comment
    1 (nature:none) never escalates; comment 2 escalates on low-confidence principle alone;
    comment 3 escalates on both missing-nature and quote-coverage."""
    missing_facets = _missing_facet_flags(ROWS1, BATCH_IDS)
    skip_ids = _nature_none_ids(ROWS1)
    low_conf = _low_confidence_ids(ROWS2, "principle", 0.5)
    quote_flags = _quote_coverage_flags(ROWS1 + ROWS2, BY_ID, 0.3, exclude_ids=skip_ids)

    flag_info: dict[int, dict] = {}
    for cid, missing in missing_facets.items():
        flag_info.setdefault(cid, {})["missing_facets"] = missing
    for cid in low_conf:
        flag_info.setdefault(cid, {})["low_confidence_principle"] = True
    for cid, frac in quote_flags.items():
        flag_info.setdefault(cid, {})["uncovered_fraction"] = frac

    assert sorted(flag_info) == [2, 3]


def test_tags_context_by_id_formats_known_and_untagged_comments() -> None:
    ctx = _tags_context_by_id(ROWS1, {1, 3})
    assert ctx[1] == "area/code (confidence 0.60); nature/none (confidence 0.90)"
    assert ctx[3] == "area/code (confidence 0.50)"


def test_pass3_context_includes_tags_and_flag_reasons() -> None:
    flag_info = {
        2: {"low_confidence_principle": True},
        3: {"missing_facets": ["nature"], "uncovered_fraction": 0.4672897196261682},
    }
    ctx = _pass3_context_by_id(ROWS1 + ROWS2, flag_info, {2, 3})
    assert "low-confidence principle match" in ctx[2]
    assert "reconciler-pattern" in ctx[2]
    assert "missing nature" in ctx[3]
    assert "47% of the comment's text uncovered by quotes" in ctx[3]
