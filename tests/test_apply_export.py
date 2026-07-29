import json
from pathlib import Path

from scripts.apply_export import _detect_target, _merge, main


def test_detect_target_known_commit() -> None:
    rec = {"tep_number": 10, "repo": "pipeline", "commit_sha": "abc123", "note": "n/a"}
    assert _detect_target(rec) == "overrides/known_commits.jsonl"


def test_detect_target_pr_attribution() -> None:
    rec = {"tep_number": 52, "repo": "results", "pr_number": 103, "action": "exclude"}
    assert _detect_target(rec) == "overrides/pr_attribution_overrides.jsonl"


def test_detect_target_section_override() -> None:
    rec = {
        "repo": "community",
        "pr_number": 82,
        "comment_id": 1,
        "override_section": "## Motivation",
    }
    assert _detect_target(rec) == "overrides/section_overrides.jsonl"


def test_detect_target_unknown_shape_returns_none() -> None:
    assert _detect_target({"foo": "bar"}) is None


def test_merge_appends_new_records(tmp_path: Path) -> None:
    target = tmp_path / "overrides.jsonl"
    appended, skipped = _merge([{"a": 1}, {"a": 2}], target)

    assert appended == 2
    assert skipped == 0
    lines = target.read_text().splitlines()
    assert len(lines) == 2


def test_merge_skips_already_present_records(tmp_path: Path) -> None:
    target = tmp_path / "overrides.jsonl"
    target.write_text(json.dumps({"a": 1}, sort_keys=True) + "\n")

    appended, skipped = _merge([{"a": 1}, {"a": 2}], target)

    assert appended == 1
    assert skipped == 1
    assert len(target.read_text().splitlines()) == 2


def test_merge_dedupes_regardless_of_key_order(tmp_path: Path) -> None:
    """Browser-exported JSON key order won't match json.dumps(..., sort_keys=True)."""
    target = tmp_path / "overrides.jsonl"
    target.write_text(json.dumps({"a": 1, "b": 2}, sort_keys=True) + "\n")

    appended, skipped = _merge([{"b": 2, "a": 1}], target)

    assert appended == 0
    assert skipped == 1


def test_main_merges_into_auto_detected_targets(tmp_path: Path, monkeypatch) -> None:
    export_path = tmp_path / "export.jsonl"
    export_path.write_text(
        json.dumps({"tep_number": 10, "repo": "pipeline", "commit_sha": "abc", "note": "n"}) + "\n"
    )
    monkeypatch.chdir(tmp_path)

    rc = main([str(export_path)])

    assert rc == 0
    written = (tmp_path / "overrides" / "known_commits.jsonl").read_text()
    assert "abc" in written


def test_main_missing_export_file_errors(tmp_path: Path) -> None:
    rc = main([str(tmp_path / "missing.jsonl")])
    assert rc == 1


def test_main_empty_export_file_is_a_noop(tmp_path: Path) -> None:
    export_path = tmp_path / "empty.jsonl"
    export_path.write_text("")

    rc = main([str(export_path)])

    assert rc == 0


def test_main_unrecognized_shape_errors(tmp_path: Path) -> None:
    export_path = tmp_path / "export.jsonl"
    export_path.write_text(json.dumps({"foo": "bar"}) + "\n")

    rc = main([str(export_path)])

    assert rc == 1


def test_main_respects_explicit_target(tmp_path: Path, monkeypatch) -> None:
    export_path = tmp_path / "export.jsonl"
    export_path.write_text(json.dumps({"foo": "bar"}) + "\n")
    monkeypatch.chdir(tmp_path)

    rc = main([str(export_path), "--target", "overrides/custom.jsonl"])

    assert rc == 0
    assert (tmp_path / "overrides" / "custom.jsonl").exists()
