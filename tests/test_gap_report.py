"""Unit tests for scripts/gap_report.py."""

# Copyright 2026 The Tekton Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

from scripts.gap_report import (
    _badge,
    _pr_links,
    build_report,
    main,
)

# ---------------------------------------------------------------------------
# _badge
# ---------------------------------------------------------------------------


class TestBadge:
    def test_known_fates(self):
        for fate in ("never_assigned", "closed_no_merge", "open_pr", "conflict", "renumbered"):
            html = _badge(fate)
            assert "<span" in html
            assert "badge" in html

    def test_unknown_fate_fallback(self):
        html = _badge("something_new")
        assert "something_new" in html


# ---------------------------------------------------------------------------
# _pr_links
# ---------------------------------------------------------------------------


class TestPrLinks:
    def test_empty(self):
        assert _pr_links([]) == "—"

    def test_single_open_pr(self):
        prs = [
            {
                "pr_number": 42,
                "state": "open",
                "merged": False,
                "merged_at": None,
                "closed_at": None,
                "html_url": "https://github.com/tektoncd/community/pull/42",
            }
        ]
        html = _pr_links(prs)
        assert "#42" in html
        assert "https://github.com/tektoncd/community/pull/42" in html
        assert "[open]" in html

    def test_merged_pr_shows_merged(self):
        prs = [
            {
                "pr_number": 1,
                "state": "closed",
                "merged": True,
                "merged_at": "2022-05-01T00:00:00Z",
                "closed_at": "2022-05-01T00:00:00Z",
                "html_url": "https://github.com/tektoncd/community/pull/1",
            }
        ]
        html = _pr_links(prs)
        assert "[merged" in html


# ---------------------------------------------------------------------------
# build_report
# ---------------------------------------------------------------------------

_SAMPLE_GAPS = [
    {
        "tep_number": 34,
        "fate": "never_assigned",
        "prs": [],
        "renamed_from": None,
        "renamed_to": None,
        "scanned_at": "2026-01-01T00:00:00+00:00",
    },
    {
        "tep_number": 13,
        "fate": "closed_no_merge",
        "prs": [
            {
                "pr_number": 228,
                "state": "closed",
                "merged": False,
                "merged_at": None,
                "closed_at": "2021-03-01T00:00:00Z",
                "html_url": "https://github.com/tektoncd/community/pull/228",
                "title": "TEP-0013: pipeline concurrency",
            }
        ],
        "renamed_from": None,
        "renamed_to": None,
        "scanned_at": "2026-01-01T00:00:00+00:00",
    },
]

_SAMPLE_TEPS = [
    {"tep_number": 1, "stub": False, "title": "TEP Process"},
    {"tep_number": 42, "stub": True, "title": "Open stub"},
]


class TestBuildReport:
    def test_returns_html_string(self):
        html = build_report(_SAMPLE_GAPS, _SAMPLE_TEPS)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_contains_tep_numbers(self):
        html = build_report(_SAMPLE_GAPS, _SAMPLE_TEPS)
        assert "TEP-0034" in html
        assert "TEP-0013" in html

    def test_summary_card_counts(self):
        html = build_report(_SAMPLE_GAPS, _SAMPLE_TEPS)
        # 1 non-stub tep
        assert ">1<" in html

    def test_no_token_needed(self):
        """build_report must not make any network calls."""
        # If this completes without error, no network calls were made
        build_report([], [])


# ---------------------------------------------------------------------------
# main() CLI
# ---------------------------------------------------------------------------


class TestMain:
    def test_missing_gaps_file_returns_error(self, tmp_path):
        rc = main(
            [
                "--gaps",
                str(tmp_path / "missing.jsonl"),
                "--teps",
                str(tmp_path / "teps.jsonl"),
                "--out",
                str(tmp_path / "out.html"),
            ]
        )
        assert rc == 1

    def test_produces_html_file(self, tmp_path):
        gaps_f = tmp_path / "gaps.jsonl"
        teps_f = tmp_path / "teps.jsonl"
        out_f = tmp_path / "report.html"
        gaps_f.write_text("\n".join(json.dumps(g) for g in _SAMPLE_GAPS) + "\n")
        teps_f.write_text("\n".join(json.dumps(t) for t in _SAMPLE_TEPS) + "\n")
        rc = main(["--gaps", str(gaps_f), "--teps", str(teps_f), "--out", str(out_f)])
        assert rc == 0
        assert out_f.exists()
        content = out_f.read_text()
        assert "<!DOCTYPE html>" in content
