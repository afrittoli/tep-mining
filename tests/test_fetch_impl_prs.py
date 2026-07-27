from scripts.fetch_impl_prs import (
    _build_report,
    _linked_issues,
    _pr_record,
    _review_badge,
    _review_comment_records,
    _selected_impl_prs,
    _tep_mapping_rows,
)


def _tep(number: int, links: list[tuple[str, int]], title: str = "", source_file: str = "") -> dict:
    return {
        "tep_number": number,
        "title": title,
        "source_file": source_file,
        "impl_pr_links_detail": [{"repo": repo, "pr_number": pr} for repo, pr in links],
    }


def test_selected_impl_prs_uses_all_teps_by_default() -> None:
    teps = [_tep(2, [("pipeline", 3463), ("pipeline", 3601)]), _tep(21, [("pipeline", 1921)])]

    selected = _selected_impl_prs(teps, all_teps=False, sample="")

    assert selected == [("pipeline", 1921), ("pipeline", 3463), ("pipeline", 3601)]


def test_selected_impl_prs_filters_to_sample() -> None:
    teps = [_tep(2, [("pipeline", 3463)]), _tep(21, [("pipeline", 1921)])]

    selected = _selected_impl_prs(teps, all_teps=False, sample="21")

    assert selected == [("pipeline", 1921)]


def test_selected_impl_prs_deduplicates_across_teps() -> None:
    teps = [_tep(2, [("pipeline", 100)]), _tep(3, [("pipeline", 100)])]

    selected = _selected_impl_prs(teps, all_teps=True, sample="")

    assert selected == [("pipeline", 100)]


def test_linked_issues_extracts_closing_keywords() -> None:
    body = "Fixes #12 and also closes #34. Related to #56 (not a closing keyword)."

    assert _linked_issues(body) == [12, 34]


def test_linked_issues_handles_empty_body() -> None:
    assert _linked_issues("") == []
    assert _linked_issues(None) == []


def test_pr_record_collects_reviewers_decision_and_size() -> None:
    pr = {
        "number": 3463,
        "title": "Add Custom Task support",
        "body": "Implements part of tektoncd/community#159. Fixes #200.",
        "labels": [{"name": "kind/feature"}],
        "changed_files": 12,
        "additions": 400,
        "deletions": 20,
        "created_at": "2021-01-01T00:00:00Z",
        "merged_at": "2021-02-01T00:00:00Z",
    }
    reviews = [
        {"state": "COMMENTED", "user": {"login": "reviewer-1"}},
        {"state": "APPROVED", "user": {"login": "reviewer-2"}},
    ]

    record = _pr_record("pipeline", pr, reviews)

    assert record == {
        "repo": "pipeline",
        "pr_number": 3463,
        "title": "Add Custom Task support",
        "body": "Implements part of tektoncd/community#159. Fixes #200.",
        "labels": ["kind/feature"],
        "files_changed": 12,
        "additions": 400,
        "deletions": 20,
        "linked_issues": [200],
        "created_at": "2021-01-01T00:00:00Z",
        "merged_at": "2021-02-01T00:00:00Z",
        "reviewer_logins": ["reviewer-1", "reviewer-2"],
        "review_decision": "APPROVED",
        "discovered_via": "tep_file_link",
    }


def test_pr_record_accepts_explicit_discovered_via() -> None:
    pr = {"number": 1, "title": "t", "body": "", "labels": []}

    record = _pr_record("chains", pr, reviews=[], discovered_via="search")

    assert record["discovered_via"] == "search"


def test_review_comment_records_extract_fields_with_repo() -> None:
    comments = [
        {
            "id": 10,
            "body": "nit",
            "path": "pkg/reconciler/foo.go",
            "line": 42,
            "user": {"login": "reviewer-1"},
            "created_at": "2021-01-02T00:00:00Z",
        }
    ]

    records = _review_comment_records("pipeline", 3463, comments)

    assert records == [
        {
            "repo": "pipeline",
            "pr_number": 3463,
            "comment_id": 10,
            "body": "nit",
            "path": "pkg/reconciler/foo.go",
            "line": 42,
            "author": "reviewer-1",
            "created_at": "2021-01-02T00:00:00Z",
        }
    ]


def test_review_badge_maps_known_decisions() -> None:
    assert "badge-approved" in _review_badge("APPROVED")
    assert "badge-changes" in _review_badge("CHANGES_REQUESTED")
    assert "badge-commented" in _review_badge("COMMENTED")
    assert "badge-commented" in _review_badge("DISMISSED")


def _pr(repo: str, pr_number: int, decision: str = "APPROVED") -> dict:
    return {"repo": repo, "pr_number": pr_number, "review_decision": decision}


def test_tep_mapping_rows_skips_teps_without_links() -> None:
    teps = [_tep(1, [], title="No links")]

    rows = _tep_mapping_rows(teps, pr_records=[], not_found=[])

    assert rows == ""


def test_tep_mapping_rows_links_fetched_pr_with_review_badge() -> None:
    teps = [_tep(2, [("pipeline", 3463)], title="Custom Tasks", source_file="0002-custom-tasks.md")]
    pr_records = [_pr("pipeline", 3463, "APPROVED")]

    rows = _tep_mapping_rows(teps, pr_records, not_found=[])

    assert "TEP-0002" in rows
    assert "0002-custom-tasks.md" in rows
    assert "Custom Tasks" in rows
    assert "pipeline#3463" in rows
    assert "badge-approved" in rows


def test_tep_mapping_rows_marks_404_and_unfetched() -> None:
    teps = [_tep(3, [("pipeline", 1), ("triggers", 2)], title="Two links")]

    rows = _tep_mapping_rows(teps, pr_records=[], not_found=[{"repo": "pipeline", "pr_number": 1}])

    assert "badge-404" in rows
    assert "badge-skipped" in rows
    assert "not fetched" in rows


def test_tep_mapping_rows_deduplicates_repeated_links() -> None:
    teps = [_tep(4, [("pipeline", 1), ("pipeline", 1)], title="Dup links")]
    pr_records = [_pr("pipeline", 1)]

    rows = _tep_mapping_rows(teps, pr_records, not_found=[])

    assert rows.count("pipeline#1") == 1


def test_tep_mapping_rows_orders_by_tep_number() -> None:
    teps = [
        _tep(30, [("pipeline", 9)], title="Thirty"),
        _tep(2, [("pipeline", 8)], title="Two"),
    ]
    pr_records = [_pr("pipeline", 9), _pr("pipeline", 8)]

    rows = _tep_mapping_rows(teps, pr_records, not_found=[])

    assert rows.index("TEP-0002") < rows.index("TEP-0030")


def test_build_report_includes_tep_mapping_section() -> None:
    teps = [_tep(2, [("pipeline", 3463)], title="Custom Tasks", source_file="0002-custom-tasks.md")]
    pr_records = [
        {
            "repo": "pipeline",
            "pr_number": 3463,
            "title": "Add Custom Task support",
            "review_decision": "APPROVED",
            "additions": 10,
            "deletions": 2,
            "files_changed": 3,
        }
    ]

    html = _build_report(teps, pr_records, review_records=[], not_found=[], selected_count=1)

    assert html.startswith("<!DOCTYPE html>")
    assert "Implementation PRs by TEP" in html
    assert "TEP-0002" in html
    assert "pipeline#3463" in html
