import json

from scripts.build_explorer import _status_options, build_html


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
