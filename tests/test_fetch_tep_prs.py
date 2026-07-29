from scripts.fetch_tep_prs import (
    _pr_record,
    _review_comment_records,
    _selected_pr_numbers,
)


def test_selected_pr_numbers_uses_all_teps_by_default() -> None:
    pr_map = {"30": [259], "132": [968, 1044]}

    selected = _selected_pr_numbers(pr_map, all_teps=False, sample="")

    assert selected == [259, 968, 1044]


def test_selected_pr_numbers_filters_to_sample() -> None:
    pr_map = {"30": [259], "132": [968, 1044]}

    selected = _selected_pr_numbers(pr_map, all_teps=False, sample="132")

    assert selected == [968, 1044]


def test_pr_record_collects_reviewers_and_decision() -> None:
    pr = {
        "number": 968,
        "user": {"login": "tep-author"},
        "title": "[TEP-0132] Queueing concurrent Runs [Problem statement]",
        "body": "body",
        "labels": [{"name": "kind/tep"}],
        "created_at": "2023-03-01T00:00:00Z",
        "merged_at": "2023-04-03T16:06:57Z",
        "state": "closed",
    }
    reviews = [
        {"state": "COMMENTED", "user": {"login": "reviewer-1"}},
        {"state": "APPROVED", "user": {"login": "reviewer-2"}},
    ]

    record = _pr_record(pr, reviews)

    assert record == {
        "pr_number": 968,
        "author": "tep-author",
        "title": "[TEP-0132] Queueing concurrent Runs [Problem statement]",
        "body": "body",
        "labels": ["kind/tep"],
        "created_at": "2023-03-01T00:00:00Z",
        "merged_at": "2023-04-03T16:06:57Z",
        "state": "closed",
        "reviewer_logins": ["reviewer-1", "reviewer-2"],
        "review_decision": "APPROVED",
    }


def test_review_comment_records_extract_fields() -> None:
    comments = [
        {
            "id": 10,
            "body": "nit",
            "path": "teps/0132-queueing-concurrent-runs.md",
            "line": 42,
            "user": {"login": "reviewer-1"},
            "created_at": "2023-03-02T00:00:00Z",
        }
    ]

    records = _review_comment_records(968, comments)

    assert records == [
        {
            "pr_number": 968,
            "comment_id": 10,
            "body": "nit",
            "path": "teps/0132-queueing-concurrent-runs.md",
            "line": 42,
            "author": "reviewer-1",
            "created_at": "2023-03-02T00:00:00Z",
        }
    ]
