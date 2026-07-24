from pathlib import Path

from scripts.map_tep_prs import _map_pr_to_teps, build_pr_map, merge_stub_prs
from scripts.mine_pr_cache import _build_record, _load_cache


def test_load_cache_reads_jsonl_records(tmp_path: Path) -> None:
    cache_path = tmp_path / "community_pr_cache.jsonl"
    cache_path.write_text(
        '{"pr_number": 10, "updated_at": "2026-01-01T00:00:00Z", "files": ["a"]}\n'
        '{"pr_number": 11, "updated_at": "2026-01-02T00:00:00Z", "files": ["b"]}\n',
        encoding="utf-8",
    )

    cache = _load_cache(cache_path)

    assert sorted(cache) == [10, 11]
    assert cache[10]["files"] == ["a"]


def test_build_record_keeps_expected_fields() -> None:
    pr = {
        "number": 42,
        "title": "TEP-0042: answer everything",
        "body": "body",
        "state": "closed",
        "merged_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "html_url": "https://github.com/tektoncd/community/pull/42",
        "labels": [{"name": "tep"}],
    }

    record = _build_record(pr, ["teps/0042-answer-everything.md"])

    assert record == {
        "pr_number": 42,
        "title": "TEP-0042: answer everything",
        "body": "body",
        "state": "closed",
        "merged_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "html_url": "https://github.com/tektoncd/community/pull/42",
        "labels": ["tep"],
        "files": ["teps/0042-answer-everything.md"],
    }


def test_map_pr_to_teps_prefers_tep_file_paths() -> None:
    pr = {
        "title": "docs: update metadata",
        "body": "No explicit TEP mention",
        "labels": ["tep"],
        "files": ["teps/0007-awesome-feature.md"],
    }

    tep_numbers, evidence = _map_pr_to_teps(pr)

    assert tep_numbers == [7]
    assert evidence == {"resolution": ["path"], "path_teps": [7], "labels": ["tep"]}


def test_map_pr_to_teps_falls_back_to_title_and_body_mentions() -> None:
    pr = {
        "title": "TEP-0008: another feature",
        "body": "Follow-up for TEP-0009",
        "labels": [],
        "files": [],
    }

    tep_numbers, evidence = _map_pr_to_teps(pr)

    assert tep_numbers == [8, 9]
    assert evidence == {"resolution": ["text"], "title_teps": [8], "body_teps": [9]}


def test_map_pr_to_teps_resolves_multi_path_pr_with_single_title_tep() -> None:
    pr = {
        "title": "[TEP-0139] Trusted Artifacts - proposal",
        "body": "",
        "labels": ["kind/tep"],
        "files": [
            "teps/0138-decouple-api-and-feature-versioning.md",
            "teps/0139-trusted-artifacts.md",
        ],
    }

    tep_numbers, evidence = _map_pr_to_teps(pr)

    assert tep_numbers == [139]
    assert evidence == {
        "resolution": ["title_resolved_from_multi_path"],
        "path_teps": [138, 139],
        "title_teps": [139],
        "labels": ["kind/tep"],
    }


def test_map_pr_to_teps_resolves_multi_path_pr_with_single_body_tep() -> None:
    pr = {
        "title": "bulk proposal update",
        "body": "TEP-0132 problem statement",
        "labels": ["kind/tep"],
        "files": [
            "teps/0120-canceling-concurrent-pipelineruns.md",
            "teps/0132-queueing-concurrent-runs.md",
        ],
    }

    tep_numbers, evidence = _map_pr_to_teps(pr)

    assert tep_numbers == [132]
    assert evidence == {
        "resolution": ["text_resolved_from_multi_path"],
        "path_teps": [120, 132],
        "body_teps": [132],
        "labels": ["kind/tep"],
    }


def test_build_pr_map_skips_multiple_tep_file_paths_without_text_resolution() -> None:
    prs = [
        {
            "pr_number": 7,
            "title": "bulk update",
            "body": "",
            "merged_at": "2026-01-01T00:00:00Z",
            "labels": [],
            "files": ["teps/0007-awesome-feature.md", "teps/0008-another-feature.md"],
        }
    ]

    pr_map, unmatched = build_pr_map(prs)

    assert pr_map == {}
    assert unmatched == [
        {
            "pr_number": 7,
            "title": "bulk update",
            "tep_numbers": [7, 8],
            "reason": "multiple_tep_files_changed",
        }
    ]


def test_build_pr_map_keeps_multi_path_pr_when_title_resolves_to_one_tep() -> None:
    prs = [
        {
            "pr_number": 1044,
            "title": "[TEP-0139] Trusted Artifacts - proposal",
            "body": "",
            "merged_at": "2026-01-01T00:00:00Z",
            "labels": ["kind/tep"],
            "files": [
                "teps/0138-decouple-api-and-feature-versioning.md",
                "teps/0139-trusted-artifacts.md",
            ],
        },
        {
            "pr_number": 968,
            "title": "[TEP-0132] Queueing concurrent Runs [Problem statement]",
            "body": "",
            "merged_at": "2026-01-01T00:00:00Z",
            "labels": ["kind/tep"],
            "files": [
                "teps/0120-canceling-concurrent-pipelineruns.md",
                "teps/0132-queueing-concurrent-runs.md",
            ],
        },
    ]

    pr_map, unmatched = build_pr_map(prs)

    assert pr_map == {132: [968], 139: [1044]}
    assert unmatched == []


def test_merge_stub_prs_adds_open_proposal_prs() -> None:
    teps = {
        157: {
            "tep_number": 157,
            "stub": True,
            "proposal_pr_number": 1281,
            "all_open_prs": [1281, 1158],
        },
        132: {
            "tep_number": 132,
            "stub": False,
        },
    }

    merged = merge_stub_prs(teps, {132: [968]})

    assert merged == {132: [968], 157: [1158, 1281]}
