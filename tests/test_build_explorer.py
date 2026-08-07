import json
from pathlib import Path

from scripts.build_explorer import _load_classifications, _status_options, build_html


def _record(tep_number: int, status: str = "proposed") -> dict:
    return {
        "tep_number": tep_number,
        "title": f"TEP {tep_number}",
        "status": status,
        "authors": ["@a"],
        "age_days": 10,
        "impl_prs": {"total_count": 2, "discovered_count": 1, "linked_count": 1, "items": []},
        "proposal_pr": {"review_comment_count": 3, "pr_numbers": [1], "prs": [], "comments": []},
    }


def test_status_options_deduplicates_and_sorts() -> None:
    records = [_record(1, "proposed"), _record(2, "implemented"), _record(3, "proposed")]

    html = _status_options(records)

    assert html.index('value="implemented"') < html.index('value="proposed"')
    assert html.count("<option") == 2


def test_status_options_skips_missing_status() -> None:
    records = [_record(1, ""), _record(2, "implemented")]

    html = _status_options(records)

    assert html.count("<option") == 1


def test_build_html_embeds_records_as_valid_json() -> None:
    records = [_record(52)]

    html = build_html(records)

    start = html.index('<script type="application/json" id="tep-data">') + len(
        '<script type="application/json" id="tep-data">'
    )
    end = html.index("</script>", start)
    embedded = json.loads(html[start:end])
    assert embedded == records


def test_build_html_computes_summary_stats() -> None:
    records = [_record(1), _record(2)]

    html = build_html(records)

    assert "<b>2</b> TEPs" in html
    assert "<b>4</b> implementation PRs" in html  # 2 + 2
    assert "<b>6</b> review comments" in html  # 3 + 3
    assert "<b>50%</b>" in html  # 2 discovered / 4 total


def test_build_html_handles_empty_records_without_crashing() -> None:
    html = build_html([])

    assert "<b>0</b> TEPs" in html
    assert "<!DOCTYPE html>" in html


def test_build_html_with_no_classifications_embeds_empty_list_and_no_stat() -> None:
    html = build_html([_record(1)])

    start = html.index('<script type="application/json" id="classification-data">') + len(
        '<script type="application/json" id="classification-data">'
    )
    end = html.index("</script>", start)
    assert json.loads(html[start:end]) == []
    assert "comment classifications (Sub-Task 8 pilot)" not in html


def test_build_html_embeds_classifications_and_shows_stat() -> None:
    classifications = [
        {
            "repo": "community",
            "pr_number": 280,
            "comment_id": 1,
            "facet": "artifact",
            "value": "tep-body",
            "confidence": 0.9,
            "evidence": "typo fix",
        }
    ]

    html = build_html([_record(1)], classifications)

    start = html.index('<script type="application/json" id="classification-data">') + len(
        '<script type="application/json" id="classification-data">'
    )
    end = html.index("</script>", start)
    assert json.loads(html[start:end]) == classifications
    assert "<b>1</b> comment classifications" in html


def test_load_classifications_missing_file_returns_empty_list() -> None:
    assert _load_classifications(Path("does/not/exist.jsonl")) == []


def test_load_classifications_reads_real_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "classifications.jsonl"
    rec = {
        "repo": "community",
        "pr_number": 1,
        "comment_id": 2,
        "facet": "nature",
        "value": "structure",
        "confidence": 0.5,
        "evidence": "e",
    }
    path.write_text(json.dumps(rec) + "\n")

    assert _load_classifications(path) == [rec]
