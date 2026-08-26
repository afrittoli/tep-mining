"""Pure-Python tests for the quote-field text-coverage heuristic (taxonomy-and-pipeline-plan.md
Part 2, "Catching missed tags on comments that did get tagged") - no model call involved, so
these are plain string-math checks, not integration tests against classify_llm.py's pipeline."""

import pytest

from scripts.classify_llm import _find_quote_span, uncovered_fraction


def test_exact_quote_is_fully_covered() -> None:
    body = "rebase this branch onto main"
    assert uncovered_fraction(body, [body]) == 0.0


def test_no_quotes_is_fully_uncovered() -> None:
    body = "Please rebase this branch onto main before merging."
    assert uncovered_fraction(body, []) == 1.0


def test_empty_comment_is_vacuously_covered() -> None:
    assert uncovered_fraction("", ["anything"]) == 0.0


def test_partial_quote_leaves_a_partial_residual() -> None:
    body = "AAAAABBBBB"  # 10 chars, first half quoted
    assert uncovered_fraction(body, ["AAAAA"]) == 0.5


def test_overlapping_quotes_dont_double_count() -> None:
    body = "AAAAABBBBB"
    # Two overlapping quotes covering the same first half - union, not sum, so still 0.5 left.
    assert uncovered_fraction(body, ["AAAAA", "AAABB"]) == 0.3


def test_multiple_disjoint_quotes_union_correctly() -> None:
    body = "one two three four five"  # 23 chars
    frac = uncovered_fraction(body, ["one", "five"])
    # "one" (3 chars) + "five" (4 chars) = 7 covered out of 23 total.
    assert frac == (23 - 7) / 23


def test_ungrounded_quote_contributes_no_coverage() -> None:
    body = "Please rebase this branch onto main before merging."
    # A hallucinated/paraphrased-past-recognition quote that isn't actually in the text at
    # all should not count as covering anything - that's the whole point of using a literal
    # substring instead of a self-reported percentage.
    assert uncovered_fraction(body, ["squash all the commits"]) == 1.0


def test_whitespace_only_difference_still_matches() -> None:
    body = "This spans\ntwo lines of a comment body."
    # A quote that collapses the newline to a space should still be treated as grounded -
    # "near-exact", not byte-for-byte exact.
    span = _find_quote_span(body, "This spans two lines")
    assert span is not None
    assert body[span[0] : span[1]].replace("\n", " ") == "This spans two lines"


def test_quote_not_present_returns_none_span() -> None:
    assert _find_quote_span("hello world", "goodbye world") is None


def test_full_coverage_from_multiple_matches_reaches_zero() -> None:
    body = "short comment"
    assert uncovered_fraction(body, ["short", "comment"]) == pytest.approx(1 / 13)


def test_quotes_are_stripped_before_matching() -> None:
    # A quote with incidental leading/trailing whitespace (a common model formatting quirk)
    # is stripped before searching - the space itself was never part of the "real words," so
    # it's correctly excluded from the covered span rather than causing a match failure.
    body = "short comment"
    assert uncovered_fraction(body, ["short", " comment"]) == pytest.approx(1 / 13)
