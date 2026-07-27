from pathlib import Path

from scripts.synthesize import (
    _divergences,
    _extract_headings,
    _heading_positions,
    _impl_prs_summary,
    _load_overrides,
    _nearest_heading,
    _proposal_pr_summary,
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
# Overrides
# ---------------------------------------------------------------------------


def test_load_overrides_keys_by_repo_pr_comment(tmp_path: Path) -> None:
    path = tmp_path / "overrides.jsonl"
    path.write_text(
        '{"repo": "community", "pr_number": 82, "comment_id": 123, '
        '"override_section": "## Motivation"}\n'
    )

    overrides = _load_overrides(path)

    assert overrides == {("community", 82, 123): "## Motivation"}


def test_load_overrides_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _load_overrides(tmp_path / "missing.jsonl") == {}


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
        }
    ]


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
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 10,
            "deletions": 1,
            "files_changed": 2,
        },
        ("results", 2): {
            "title": "discovered one",
            "review_decision": "COMMENTED",
            "discovered_via": "search",
            "additions": 5,
            "deletions": 0,
            "files_changed": 1,
        },
    }

    summary = _impl_prs_summary(
        {("pipeline", 1)},
        {("results", 2)},
        impl_prs_by_key,
        impl_review_counts={("pipeline", 1): 3, ("results", 2): 4},
    )

    assert summary["linked_count"] == 1
    assert summary["discovered_count"] == 1
    assert summary["total_count"] == 2
    assert summary["by_repo"] == {"pipeline": 1, "results": 1}
    assert summary["review_comment_count"] == 7
    by_pr = {(i["repo"], i["pr_number"]): i["review_comment_count"] for i in summary["items"]}
    assert by_pr == {("pipeline", 1): 3, ("results", 2): 4}


def test_impl_prs_summary_handles_missing_or_404_record() -> None:
    impl_prs_by_key = {("pipeline", 1): {"repo": "pipeline", "pr_number": 1, "status": 404}}

    summary = _impl_prs_summary({("pipeline", 1)}, set(), impl_prs_by_key, impl_review_counts={})

    assert summary["items"][0]["status"] == 404
    assert summary["items"][0]["title"] is None
    assert summary["items"][0]["review_comment_count"] == 0


def test_impl_prs_summary_dedupes_pair_in_both_linked_and_discovered() -> None:
    impl_prs_by_key = {
        ("pipeline", 1): {
            "title": "t",
            "review_decision": "APPROVED",
            "discovered_via": "tep_file_link",
            "additions": 1,
            "deletions": 1,
            "files_changed": 1,
        }
    }

    summary = _impl_prs_summary(
        {("pipeline", 1)}, {("pipeline", 1)}, impl_prs_by_key, impl_review_counts={}
    )

    assert summary["total_count"] == 1


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
        impl_prs_by_key={},
        impl_review_counts={},
        discoveries={"52": [["results", 103]]},
        gaps_by_number={},
        coverage_by_number={52: {"linked": 1, "discovered": 1, "search_hits_confirmed": 2}},
        overrides={},
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
        impl_review_counts={},
        discoveries={},
        gaps_by_number={},
        coverage_by_number={},
        overrides={},
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
