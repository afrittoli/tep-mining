from pathlib import Path

from scripts.build_report_index import _label, build_index


def test_label_uses_title_tag_when_present(tmp_path: Path) -> None:
    report = tmp_path / "gap_report.html"
    report.write_text("<html><head><title>TEP Number Gap Report</title></head></html>")

    assert _label(report) == "TEP Number Gap Report"


def test_label_falls_back_to_filename_when_no_title(tmp_path: Path) -> None:
    report = tmp_path / "impl_prs_report.html"
    report.write_text("<html><body>no title here</body></html>")

    assert _label(report) == "Impl Prs Report"


def test_build_index_lists_a_tab_per_report_excluding_self(tmp_path: Path) -> None:
    (tmp_path / "gap_report.html").write_text("<title>Gap Report</title>")
    (tmp_path / "pr_map_report.html").write_text("<title>PR Map Report</title>")
    (tmp_path / "index.html").write_text("<title>should be excluded</title>")

    html = build_index(tmp_path, self_name="index.html")

    assert "Gap Report" in html
    assert "PR Map Report" in html
    assert "should be excluded" not in html
    assert html.count("<iframe") == 2


def test_build_index_handles_empty_reports_dir(tmp_path: Path) -> None:
    html = build_index(tmp_path, self_name="index.html")

    assert "No reports found" in html
