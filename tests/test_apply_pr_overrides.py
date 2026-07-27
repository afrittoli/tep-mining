from pathlib import Path

from scripts.apply_pr_overrides import _pending_includes


def test_pending_includes_finds_unknown_pairs(tmp_path: Path) -> None:
    path = tmp_path / "overrides.jsonl"
    path.write_text(
        '{"tep_number": 52, "repo": "pipeline", "pr_number": 999, "action": "include"}\n'
        '{"tep_number": 52, "repo": "results", "pr_number": 103, "action": "include"}\n'
    )

    pending = _pending_includes(path, existing_prs={("results", 103)})

    assert pending == [("pipeline", 999)]


def test_pending_includes_ignores_exclude_actions(tmp_path: Path) -> None:
    path = tmp_path / "overrides.jsonl"
    path.write_text(
        '{"tep_number": 52, "repo": "pipeline", "pr_number": 999, "action": "exclude"}\n'
    )

    assert _pending_includes(path, existing_prs=set()) == []


def test_pending_includes_deduplicates(tmp_path: Path) -> None:
    path = tmp_path / "overrides.jsonl"
    path.write_text(
        '{"tep_number": 52, "repo": "pipeline", "pr_number": 999, "action": "include"}\n'
        '{"tep_number": 90, "repo": "pipeline", "pr_number": 999, "action": "include"}\n'
    )

    assert _pending_includes(path, existing_prs=set()) == [("pipeline", 999)]


def test_pending_includes_missing_file_returns_empty(tmp_path: Path) -> None:
    assert _pending_includes(tmp_path / "missing.jsonl", existing_prs=set()) == []
