from pathlib import Path

from scripts.synthesize import (
    _consistency_flags,
    _divergences,
    _extract_headings,
    _heading_positions,
    _impl_prs_summary,
    _is_bot,
    _load_pr_attribution_overrides,
    _load_section_overrides,
    _nearest_heading,
    _normalize_login,
    _proposal_pr_summary,
    _search_confidence,
    _title_confirms_tep,
    _write_snapshot,
    build_tep_record,
)

# ---------------------------------------------------------------------------
# Template / section structure
# ---------------------------------------------------------------------------


def test_extract_headings_finds_h2_and_h3() -> None:
    text = "## Summary\ntext\n### Goals\nmore\n## Motivation\n"

    assert _extract_headings(text) == ["## Summary", "### Goals", "## Motivation"]


def test_heading_positions_returns_line_numbers() -> None:
    text = "intro\n## Summary\nbody\nbody\n### Goals\n"

    assert _heading_positions(text) == [(2, "## Summary"), (5, "### Goals")]


def test_nearest_heading_returns_last_heading_at_or_before_line() -> None:
    positions = [(2, "## Summary"), (5, "### Goals"), (10, "## Motivation")]

    assert _nearest_heading(6, positions) == "### Goals"
    assert _nearest_heading(10, positions) == "## Motivation"
    assert _nearest_heading(20, positions) == "## Motivation"


def test_nearest_heading_returns_none_before_first_heading_or_null_line() -> None:
    positions = [(5, "## Summary")]

    assert _nearest_heading(1, positions) is None
    assert _nearest_heading(None, positions) is None


def test_divergences_reports_both_directions() -> None:
    template = ["## Summary", "## Motivation", "### Goals"]
    tep_sections = ["## Summary", "### Goals", "## Custom Section"]

    result = _divergences(tep_sections, template)

    assert result == {
        "missing_from_tep": ["## Motivation"],
        "extra_in_tep": ["## Custom Section"],
    }


# ---------------------------------------------------------------------------
# Bot / candidate-confidence helpers
# ---------------------------------------------------------------------------


def test_is_bot_detects_bracket_suffix() -> None:
    assert _is_bot("dependabot[bot]") is True
    assert _is_bot("github-advanced-security[bot]") is True
    assert _is_bot("vdemeester") is False
    assert _is_bot(None) is False


def test_normalize_login_strips_at_and_casefolds() -> None:
    assert _normalize_login("@vdemeester") == "vdemeester"
    assert _normalize_login("VDemeester") == "vdemeester"
    assert _normalize_login("bob") == "bob"


def test_title_confirms_tep_matches_bracket_and_colon_conventions() -> None:
    assert _title_confirms_tep("[TEP-0124] implement tracing", 124) is True
    assert _title_confirms_tep("TEP-0052: Automated Cleanup", 52) is True
    assert _title_confirms_tep("TEP-52: Automated Cleanup", 52) is True  # unpadded also OK
    assert _title_confirms_tep(None, 52) is False


def test_title_confirms_tep_rejects_mention_elsewhere_or_wrong_number() -> None:
    assert _title_confirms_tep("Bump pipeline, includes TEP-0052 fix", 52) is False
    assert _title_confirms_tep("TEP-0520: unrelated", 52) is False
    assert _title_confirms_tep("TEP-520: unrelated", 52) is False


def test_search_confidence_confirms_via_title() -> None:
    record = {"title": "TEP-0052: cleanup", "author": "a-stranger"}

    assert _search_confidence(record, 52, tep_authors=set()) == "confirmed"


def test_search_confidence_confirms_via_tep_author() -> None:
    record = {"title": "unrelated bump", "author": "VDemeester"}

    assert _search_confidence(record, 52, tep_authors={"vdemeester"}) == "confirmed"


def test_search_confidence_is_candidate_without_either_signal() -> None:
    record = {"title": "Bump pipeline to v0.51.0", "author": "dependabot-adjacent-human"}

    assert _search_confidence(record, 52, tep_authors={"wlynch"}) == "candidate"


def test_search_confidence_is_candidate_when_unfetched_or_404() -> None:
    assert _search_confidence(None, 52, tep_authors=set()) == "candidate"
    assert _search_confidence({"status": 404}, 52, tep_authors=set()) == "candidate"


def test_search_confidence_community_repo_ignores_author_match() -> None:
    """Regression test: community#477 is TEP-0076's own proposal PR, opened by bobcatfish, who
    is also a listed author of TEP-0075 — that shared authorship must not confirm it for
    TEP-0075. Author-match alone is only trusted for actual code repos."""
    record = {
        "repo": "community",
        "title": "[TEP-0076] Propose array results",
        "author": "bobcatfish",
    }

    assert _search_confidence(record, 75, tep_authors={"bobcatfish"}) == "candidate"


def test_search_confidence_community_repo_still_confirms_via_title() -> None:
    record = {
        "repo": "community",
        "title": "TEP-0052: Mark proposal as implementable",
        "author": "x",
    }

    assert _search_confidence(record, 52, tep_authors=set()) == "confirmed"


def test_search_confidence_non_community_repo_still_confirms_via_author() -> None:
    record = {"repo": "pipeline", "title": "unrelated bump", "author": "wlynch"}

    assert _search_confidence(record, 52, tep_authors={"wlynch"}) == "confirmed"


# ---------------------------------------------------------------------------
# _consistency_flags
# ---------------------------------------------------------------------------


def _impl_prs(total_count: int = 0, candidate_count: int = 0) -> dict:
    return {"total_count": total_count, "candidate_count": candidate_count}


def test_consistency_flags_implemented_with_zero_prs() -> None:
    flags = _consistency_flags("implemented", _impl_prs(total_count=0, candidate_count=0))

    assert len(flags) == 1
    assert flags[0]["code"] == "implemented_no_prs"


def test_consistency_flags_implemented_with_only_candidates() -> None:
    flags = _consistency_flags("implemented", _impl_prs(total_count=0, candidate_count=2))

    assert len(flags) == 1
    assert flags[0]["code"] == "implemented_only_candidates"
    assert "2" in flags[0]["message"]


def test_consistency_flags_implemented_with_confirmed_prs_is_clean() -> None:
    assert _consistency_flags("implemented", _impl_prs(total_count=3, candidate_count=0)) == []


def test_consistency_flags_non_implemented_status_never_flagged() -> None:
    assert _consistency_flags("proposed", _impl_prs(total_count=0, candidate_count=0)) == []
    assert _consistency_flags(None, _impl_prs(total_count=0, candidate_count=0)) == []


# ---------------------------------------------------------------------------
# Overrides
# ---------------------------------------------------------------------------


def test_load_section_overrides_keys_by_repo_pr_comment(tmp_path: Path) -> None:
    path = tmp_path / "overrides.jsonl"
    path.write_text(
        '{"repo": "community", "pr_number": 82, "comment_id": 123, '
        '"override_section": "## Motivation"}\n'
    )

    overrides = _load_section_overrides(path)

    assert overrides == {("community", 82, 123): "## Motivation"}


def test_load_section_overrides_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_section_overrides(tmp_path / "missing.jsonl") == {}


def test_load_pr_attribution_overrides_groups_by_tep(tmp_path: Path) -> None:
    path = tmp_path / "pr_overrides.jsonl"
    path.write_text(
        '{"tep_number": 52, "repo": "results", "pr_number": 103, "action": "exclude", '
        '"reason": "unrelated"}\n'
        '{"tep_number": 52, "repo": "pipeline", "pr_number": 999, "action": "include", '
        '"reason": "missed by search"}\n'
        '{"tep_number": 84, "repo": "chains", "pr_number": 1, "action": "exclude"}\n'
    )

    overrides = _load_pr_attribution_overrides(path)

    assert len(overrides[52]) == 2
    assert len(overrides[84]) == 1
    assert overrides[52][0]["action"] == "exclude"


def test_load_pr_attribution_overrides_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_pr_attribution_overrides(tmp_path / "missing.jsonl") == {}


# ---------------------------------------------------------------------------
# Proposal PR summary
# ---------------------------------------------------------------------------


def test_proposal_pr_summary_buckets_comments_by_section() -> None:
    prs_by_number = {
        82: {
            "pr_number": 82,
            "title": "TEP-0001",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_at": "2020-02-01T00:00:00Z",
            "reviewer_logins": ["alice"],
            "review_decision": "APPROVED",
        }
    }
    reviews = [
        {"pr_number": 82, "comment_id": 1, "line": 6, "created_at": "2020-01-05T00:00:00Z"},
        {"pr_number": 82, "comment_id": 2, "line": None, "created_at": "2020-01-05T00:00:00Z"},
        {"pr_number": 82, "comment_id": 3, "line": 2, "created_at": "2020-01-06T00:00:00Z"},
        {"pr_number": 999, "comment_id": 4, "line": 2, "created_at": "2020-01-07T00:00:00Z"},
    ]
    positions = [(2, "## Summary"), (5, "### Goals")]

    summary = _proposal_pr_summary([82], prs_by_number, reviews, positions, overrides={})

    assert summary["review_comment_count"] == 3  # comment on PR 999 excluded
    assert summary["comments_by_section"] == {"### Goals": 1, "## Summary": 1}
    assert summary["comments_unmapped"] == 1
    assert summary["review_rounds_approx"] == 2  # two distinct dates
    assert summary["reviewer_logins"] == ["alice"]


def test_proposal_pr_summary_override_wins_over_heuristic() -> None:
    prs_by_number = {
        82: {
            "pr_number": 82,
            "title": "t",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_at": None,
            "reviewer_logins": [],
            "review_decision": "COMMENTED",
        }
    }
    reviews = [
        {"pr_number": 82, "comment_id": 1, "line": 6, "created_at": "2020-01-05T00:00:00Z"},
    ]
    positions = [(2, "## Summary"), (5, "### Goals")]
    overrides = {("community", 82, 1): "## Motivation"}

    summary = _proposal_pr_summary([82], prs_by_number, reviews, positions, overrides)

    assert summary["comments_by_section"] == {"## Motivation": 1}
    comment = summary["comments"][0]
    assert comment["is_override"] is True
    assert comment["section"] == "## Motivation"
    assert comment["heuristic_section"] == "### Goals"  # what the heuristic alone would say


def test_proposal_pr_summary_comments_list_carries_identity_for_override_ui() -> None:
    prs_by_number = {
        82: {
            "pr_number": 82,
            "title": "t",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_at": None,
            "reviewer_logins": [],
            "review_decision": "COMMENTED",
        }
    }
    reviews = [
        {
            "pr_number": 82,
            "comment_id": 1,
            "author": "bob",
            "body": "nit",
            "path": "teps/0001-x.md",
            "line": 6,
            "created_at": "2020-01-05T00:00:00Z",
        },
    ]
    positions = [(2, "## Summary"), (5, "### Goals")]

    summary = _proposal_pr_summary([82], prs_by_number, reviews, positions, overrides={})

    assert summary["comments"] == [
        {
            "pr_number": 82,
            "comment_id": 1,
            "author": "bob",
            "body": "nit",
            "path": "teps/0001-x.md",
            "line": 6,
            "created_at": "2020-01-05T00:00:00Z",
            "section": "### Goals",
            "heuristic_section": "### Goals",
            "is_override": False,
            "is_self_comment": False,
        }
    ]


def test_proposal_pr_summary_filters_bot_comments() -> None:
    prs_by_number = {
        82: {
            "pr_number": 82,
            "title": "t",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_at": None,
            "reviewer_logins": [],
            "review_decision": "COMMENTED",
        }
    }
    reviews = [
        {"pr_number": 82, "comment_id": 1, "author": "bob", "line": 2, "created_at": "d"},
        {
            "pr_number": 82,
            "comment_id": 2,
            "author": "github-advanced-security[bot]",
            "line": 2,
            "created_at": "d",
        },
    ]
    positions = [(2, "## Summary")]

    summary = _proposal_pr_summary([82], prs_by_number, reviews, positions, overrides={})

    assert summary["review_comment_count"] == 1
    assert [c["comment_id"] for c in summary["comments"]] == [1]


def test_proposal_pr_summary_flags_self_comments_but_still_counts_them() -> None:
    prs_by_number = {
        82: {
            "pr_number": 82,
            "title": "t",
            "author": "author-of-pr",
            "created_at": "2020-01-01T00:00:00Z",
            "merged_at": None,
            "reviewer_logins": [],
            "review_decision": "COMMENTED",
        }
    }
    reviews = [
        {"pr_number": 82, "comment_id": 1, "author": "author-of-pr", "line": 2, "created_at": "d"},
        {"pr_number": 82, "comment_id": 2, "author": "someone-else", "line": 2, "created_at": "d"},
    ]
    positions = [(2, "## Summary")]

    summary = _proposal_pr_summary([82], prs_by_number, reviews, positions, overrides={})

    assert summary["review_comment_count"] == 2  # still collected/counted, just flagged
    by_id = {c["comment_id"]: c for c in summary["comments"]}
    assert by_id[1]["is_self_comment"] is True
    assert by_id[2]["is_self_comment"] is False


def test_proposal_pr_summary_handles_no_pr_numbers() -> None:
    summary = _proposal_pr_summary([], {}, [], [], {})

    assert summary["prs"] == []
    assert summary["review_comment_count"] == 0


# ---------------------------------------------------------------------------
# Implementation PRs summary
# ---------------------------------------------------------------------------


def test_impl_prs_summary_splits_linked_and_discovered() -> None:
    impl_prs_by_key = {
        ("pipeline", 1): {
            "title": "linked one",
            "author": "some-contributor",
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 10,
            "deletions": 1,
            "files_changed": 2,
        },
        ("results", 2): {
            "title": "TEP-0052: discovered one",  # title confirms -> not just a candidate
            "author": "another-contributor",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 5,
            "deletions": 0,
            "files_changed": 1,
        },
    }

    summary = _impl_prs_summary(
        {
            ("pipeline", 1): {
                "url": "https://github.com/tektoncd/pipeline/pull/1",
                "format": "full-url",
            }
        },
        {("results", 2): "…mentions TEP-0052…"},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={
            ("pipeline", 1): [
                {"comment_id": i, "author": "reviewer", "created_at": f"2021-01-0{i}T00:00:00Z"}
                for i in range(1, 4)
            ],
            ("results", 2): [
                {"comment_id": i, "author": "reviewer", "created_at": f"2021-01-0{i}T00:00:00Z"}
                for i in range(1, 5)
            ],
        },
        tep_number=52,
        tep_authors=set(),
    )

    assert summary["linked_count"] == 1
    assert summary["discovered_count"] == 1
    assert summary["manual_count"] == 0
    assert summary["candidate_count"] == 0
    assert summary["total_count"] == 2
    assert summary["by_repo"] == {"pipeline": 1, "results": 1}
    assert summary["review_comment_count"] == 7
    by_pr = {(i["repo"], i["pr_number"]): i for i in summary["items"]}
    assert by_pr[("pipeline", 1)]["attribution_source"] == "tep_file_link"
    assert by_pr[("pipeline", 1)]["evidence"]["format"] == "full-url"
    assert by_pr[("results", 2)]["attribution_source"] == "search"
    assert by_pr[("results", 2)]["evidence"] == "…mentions TEP-0052…"
    assert len(by_pr[("pipeline", 1)]["comments"]) == 3
    assert [c["comment_id"] for c in by_pr[("pipeline", 1)]["comments"]] == [1, 2, 3]  # sorted


def test_impl_prs_summary_comments_are_bot_filtered_upstream_and_flag_self_comments() -> None:
    impl_prs_by_key = {
        ("pipeline", 1): {
            "title": "linked one",
            "author": "author-of-pr",
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }
    # Bot filtering happens in synthesize.py's main() before impl_reviews_by_key is built —
    # a bot comment simply wouldn't be in this dict at all by the time _impl_prs_summary runs.
    summary = _impl_prs_summary(
        {("pipeline", 1): {"url": "u", "format": "full-url"}},
        {},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={
            ("pipeline", 1): [
                {
                    "comment_id": 1,
                    "author": "author-of-pr",
                    "created_at": "d1",
                    "body": "self note",
                },
                {
                    "comment_id": 2,
                    "author": "someone-else",
                    "created_at": "d2",
                    "body": "real review",
                },
            ]
        },
        tep_number=1,
        tep_authors=set(),
    )

    comments = summary["items"][0]["comments"]
    by_id = {c["comment_id"]: c for c in comments}
    assert by_id[1]["is_self_comment"] is True
    assert by_id[2]["is_self_comment"] is False
    assert summary["items"][0]["review_comment_count"] == 2  # both still counted


def test_impl_prs_summary_marks_genuine_404_as_not_found() -> None:
    impl_prs_by_key = {("pipeline", 1): {"repo": "pipeline", "pr_number": 1, "status": 404}}

    summary = _impl_prs_summary(
        {("pipeline", 1): {"url": "u", "format": "full-url"}},
        {},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=1,
        tep_authors=set(),
    )

    assert summary["items"][0]["status"] == "not_found"
    assert summary["items"][0]["title"] is None
    assert summary["items"][0]["review_comment_count"] == 0


def test_impl_prs_summary_marks_never_fetched_manual_include_as_pending() -> None:
    summary = _impl_prs_summary(
        {},
        {},
        pr_overrides=[
            {"repo": "pipeline", "pr_number": 999, "action": "include", "reason": "missed"}
        ],
        impl_prs_by_key={},  # never fetched by anything
        impl_reviews_by_key={},
        tep_number=1,
        tep_authors=set(),
    )

    assert summary["items"][0]["status"] == "pending_fetch"
    assert summary["items"][0]["attribution_source"] == "manual_include"


def test_impl_prs_summary_prefers_linked_attribution_when_both() -> None:
    impl_prs_by_key = {
        ("pipeline", 1): {
            "title": "t",
            "author": "a-stranger",
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {("pipeline", 1): {"url": "u", "format": "full-url"}},
        {("pipeline", 1): "snippet"},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=1,
        tep_authors=set(),
    )

    assert summary["total_count"] == 1
    assert summary["items"][0]["attribution_source"] == "tep_file_link"


def test_impl_prs_summary_linked_pr_skips_candidate_gate_even_if_author_unknown() -> None:
    """A TEP author commonly links a contributor's PR as 'the implementation' in their own
    doc — the linking itself is the confirmation, regardless of who opened the linked PR."""
    impl_prs_by_key = {
        ("pipeline", 1): {
            "title": "implement the thing",  # no TEP-number prefix
            "author": "random-contributor",  # not a listed TEP author
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {("pipeline", 1): {"url": "u", "format": "full-url"}},
        {},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=52,
        tep_authors={"someone-else"},
    )

    assert summary["linked_count"] == 1
    assert summary["candidate_count"] == 0
    assert summary["items"][0]["attribution_source"] == "tep_file_link"


def test_impl_prs_summary_exclude_override_removes_pr_and_records_it() -> None:
    impl_prs_by_key = {
        ("results", 2): {
            "title": "discovered one",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 5,
            "deletions": 0,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {},
        {("results", 2): "snippet"},
        pr_overrides=[
            {"repo": "results", "pr_number": 2, "action": "exclude", "reason": "unrelated"}
        ],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=52,
        tep_authors=set(),
    )

    assert summary["total_count"] == 0
    assert summary["discovered_count"] == 0
    assert summary["candidate_count"] == 0  # excluded before it could even become a candidate
    assert summary["excluded"] == [
        {
            "repo": "results",
            "pr_number": 2,
            "was_attribution_source": "search",
            "reason": "unrelated",
        }
    ]


def test_impl_prs_summary_include_override_adds_a_new_pr() -> None:
    impl_prs_by_key = {
        ("pipeline", 999): {
            "title": "manually added",
            "review_decision": "APPROVED",
            "discovered_via": "search",  # discovered for a different TEP originally
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {},
        {},
        pr_overrides=[
            {
                "repo": "pipeline",
                "pr_number": 999,
                "action": "include",
                "reason": "missed by search",
            }
        ],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=1,
        tep_authors=set(),
    )

    assert summary["manual_count"] == 1
    assert summary["total_count"] == 1
    assert summary["items"][0]["attribution_source"] == "manual_include"
    assert summary["items"][0]["evidence"] == "missed by search"


def test_impl_prs_summary_unconfirmed_search_hit_becomes_a_candidate() -> None:
    """The concrete false-positive this whole tier exists for: a downstream repo's dependency
    bump PR that happens to vendor in a commit mentioning the TEP number."""
    impl_prs_by_key = {
        ("catalog", 42): {
            "title": "Bump github.com/tektoncd/pipeline from 0.42.0 to 0.51.0",
            "author": "dependabot-lookalike",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {},
        {("catalog", 42): "…vendored commit mentions TEP-0052…"},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={("catalog", 42): [{"comment_id": i} for i in range(5)]},
        tep_number=52,
        tep_authors={"wlynch"},
    )

    assert summary["total_count"] == 0
    assert summary["discovered_count"] == 0
    assert summary["candidate_count"] == 1
    assert summary["review_comment_count"] == 0  # candidates don't feed into counted totals
    candidate = summary["candidates"][0]
    assert candidate["repo"] == "catalog"
    assert candidate["pr_number"] == 42
    assert candidate["evidence"] == "…vendored commit mentions TEP-0052…"
    assert "dependabot-lookalike" in candidate["why_candidate"]


def test_impl_prs_summary_include_override_promotes_candidate_to_counted() -> None:
    impl_prs_by_key = {
        ("catalog", 42): {
            "title": "Bump pipeline",
            "author": "a-stranger",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {},
        {("catalog", 42): "snippet"},
        pr_overrides=[
            {
                "repo": "catalog",
                "pr_number": 42,
                "action": "include",
                "reason": "manually confirmed, genuinely implements this TEP",
            }
        ],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=52,
        tep_authors=set(),
    )

    assert summary["candidate_count"] == 0
    assert summary["candidates"] == []
    assert summary["manual_count"] == 1
    assert summary["total_count"] == 1
    assert summary["items"][0]["attribution_source"] == "manual_include"


def test_impl_prs_summary_exclude_override_dismisses_candidate() -> None:
    impl_prs_by_key = {
        ("catalog", 42): {
            "title": "Bump pipeline",
            "author": "a-stranger",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {},
        {("catalog", 42): "snippet"},
        pr_overrides=[
            {
                "repo": "catalog",
                "pr_number": 42,
                "action": "exclude",
                "reason": "just a vendoring bump, unrelated",
            }
        ],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=52,
        tep_authors=set(),
    )

    assert summary["candidate_count"] == 0
    assert summary["candidates"] == []
    assert summary["excluded"] == [
        {
            "repo": "catalog",
            "pr_number": 42,
            "was_attribution_source": "search",
            "reason": "just a vendoring bump, unrelated",
        }
    ]


def test_impl_prs_summary_bot_authored_pr_is_silently_filtered() -> None:
    impl_prs_by_key = {
        ("pipeline", 1): {
            "title": "linked one",
            "author": "some-contributor",
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        },
        ("pipeline", 2): {
            "title": "Bump golang.org/x/net",
            "author": "dependabot[bot]",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 5,
            "deletions": 5,
            "files_changed": 1,
        },
    }

    summary = _impl_prs_summary(
        {("pipeline", 1): {"url": "u", "format": "full-url"}},
        {("pipeline", 2): "…mentions TEP-0052…"},
        pr_overrides=[],
        impl_prs_by_key=impl_prs_by_key,
        impl_reviews_by_key={},
        tep_number=52,
        tep_authors=set(),
    )

    assert summary["total_count"] == 1  # only the non-bot linked PR
    assert summary["candidate_count"] == 0  # not even surfaced as a candidate
    assert summary["bot_filtered_count"] == 1
    assert [i["pr_number"] for i in summary["items"]] == [1]
    assert summary["candidates"] == []
    assert summary["excluded"] == []


# ---------------------------------------------------------------------------
# build_tep_record (integration of the above)
# ---------------------------------------------------------------------------


def test_build_tep_record_assembles_full_record() -> None:
    tep = {
        "tep_number": 52,
        "title": "Cleanup",
        "status": "implemented",
        "authors": ["@a"],
        "collaborators": [],
        "creation_date": "2021-01-01",
        "last_updated": "2021-02-01",
        "age_days": 31,
        "source_file": "0052-cleanup.md",
        "sections_present": ["## Summary"],
        "impl_pr_links_detail": [{"repo": "pipeline", "pr_number": 1429}],
    }

    record = build_tep_record(
        tep,
        template_sections=["## Summary", "## Motivation"],
        tep_pr_map={"52": [347]},
        community_prs_by_number={
            347: {
                "pr_number": 347,
                "title": "TEP-0052",
                "created_at": "2021-01-01T00:00:00Z",
                "merged_at": "2021-01-15T00:00:00Z",
                "reviewer_logins": [],
                "review_decision": "APPROVED",
            }
        },
        community_pr_reviews=[],
        impl_prs_by_key={
            ("results", 103): {
                "title": "TEP-0052: cleanup impl",  # title confirms -> counted, not a candidate
                "review_decision": "APPROVED",
                "discovered_via": "search",
                "additions": 1,
                "deletions": 1,
                "files_changed": 1,
            }
        },
        impl_reviews_by_key={},
        discoveries={"52": [{"repo": "results", "pr_number": 103, "evidence": "…TEP-0052…"}]},
        gaps_by_number={},
        coverage_by_number={52: {"linked": 1, "discovered": 1, "search_hits_confirmed": 2}},
        section_overrides={},
        pr_overrides_by_tep={},
        heading_positions=[],
    )

    assert record["tep_number"] == 52
    assert record["divergences_from_template"] == {
        "missing_from_tep": ["## Motivation"],
        "extra_in_tep": [],
    }
    assert record["gap"] is None
    assert record["coverage"]["discovered"] == 1
    assert record["impl_prs"]["total_count"] == 2  # 1 linked + 1 discovered
    assert record["proposal_pr"]["pr_numbers"] == [347]


def test_build_tep_record_stub_has_no_divergences() -> None:
    tep = {
        "tep_number": 173,
        "title": "Stub",
        "status": "proposed",
        "authors": [],
        "collaborators": [],
        "creation_date": None,
        "last_updated": None,
        "age_days": None,
        "source_file": None,
        "sections_present": [],
        "stub": True,
    }

    record = build_tep_record(
        tep,
        template_sections=["## Summary"],
        tep_pr_map={},
        community_prs_by_number={},
        community_pr_reviews=[],
        impl_prs_by_key={},
        impl_reviews_by_key={},
        discoveries={},
        gaps_by_number={},
        coverage_by_number={},
        section_overrides={},
        pr_overrides_by_tep={},
        heading_positions=[],
    )

    assert record["stub"] is True
    assert record["divergences_from_template"] is None


# ---------------------------------------------------------------------------
# processed/ snapshot writing
# ---------------------------------------------------------------------------


def test_write_snapshot_creates_dated_dir_and_latest_symlink(tmp_path: Path) -> None:
    processed_dir = tmp_path / "processed"

    out_path = _write_snapshot([{"tep_number": 1}], processed_dir)

    assert out_path.exists()
    latest = processed_dir / "latest"
    assert latest.is_symlink()
    assert (latest / "per_tep_records.json").read_text() == out_path.read_text()
