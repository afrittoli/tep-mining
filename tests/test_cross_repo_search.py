from pathlib import Path

from scripts.cross_repo_search import (
    _build_report,
    _confirmed_hits,
    _linked_count,
    _own_pr_numbers,
    _repo_and_number,
    _write_coverage,
)


def _hit(title: str = "", body: str = "", repo: str = "chains", number: int = 1) -> dict:
    return {
        "title": title,
        "body": body,
        "repository_url": f"https://api.github.com/repos/tektoncd/{repo}",
        "number": number,
    }


def test_confirmed_hits_keeps_exact_number_match() -> None:
    hits = [_hit(title="Implements TEP-0084 followup")]

    assert _confirmed_hits(hits, 84) == hits


def test_confirmed_hits_rejects_different_number_with_shared_digits() -> None:
    hits = [_hit(title="Implements TEP-0184 followup")]

    assert _confirmed_hits(hits, 84) == []


def test_confirmed_hits_matches_in_body_not_just_title() -> None:
    hits = [_hit(title="Add retry support", body="Part of TEP-0084 work")]

    assert _confirmed_hits(hits, 84) == hits


def test_confirmed_hits_rejects_no_mention() -> None:
    hits = [_hit(title="Unrelated PR", body="nothing here")]

    assert _confirmed_hits(hits, 84) == []


def test_repo_and_number_extracts_from_repository_url() -> None:
    item = _hit(repo="chains", number=436)

    assert _repo_and_number(item) == ("chains", 436)


def test_own_pr_numbers_reads_from_map() -> None:
    tep_pr_map = {"84": [519, 705, 770]}

    assert _own_pr_numbers(tep_pr_map, 84) == {519, 705, 770}


def test_own_pr_numbers_missing_tep_returns_empty() -> None:
    assert _own_pr_numbers({}, 84) == set()


def test_linked_count_deduplicates_repeated_links() -> None:
    tep = {
        "impl_pr_links_detail": [
            {"repo": "chains", "pr_number": 436},
            {"repo": "chains", "pr_number": 436},
            {"repo": "chains", "pr_number": 598},
        ]
    }

    assert _linked_count(tep) == 2


def test_linked_count_handles_missing_key() -> None:
    assert _linked_count({}) == 0


def test_write_coverage_creates_dated_snapshot_and_latest_symlink(tmp_path: Path) -> None:
    coverage = [{"tep_number": 84, "linked": 7, "search_hits_confirmed": 1, "discovered": 0}]
    processed_dir = tmp_path / "processed"

    coverage_path = _write_coverage(coverage, processed_dir)

    assert coverage_path.exists()
    latest = processed_dir / "latest"
    assert latest.is_symlink()
    assert (latest / "coverage.json").read_text() == coverage_path.read_text()


def test_build_report_computes_under_linking_rate() -> None:
    coverage = [
        {"tep_number": 84, "linked": 3, "search_hits_confirmed": 1, "discovered": 1},
        {"tep_number": 2, "linked": 2, "search_hits_confirmed": 0, "discovered": 0},
    ]

    html = _build_report(coverage)

    assert html.startswith("<!DOCTYPE html>")
    assert "TEP-0084" in html
    assert "16.7%" in html  # 1 discovered / (5 linked + 1 discovered)


def test_build_report_handles_empty_coverage_without_crashing() -> None:
    html = _build_report([])

    assert html.startswith("<!DOCTYPE html>")
