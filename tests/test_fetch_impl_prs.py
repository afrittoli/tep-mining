from scripts.fetch_impl_prs import (
    _linked_issues,
    _pr_record,
    _review_comment_records,
    _selected_impl_prs,
)


def _tep(number: int, links: list[tuple[str, int]]) -> dict:
    return {
        "tep_number": number,
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
    }


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
