"""Unit tests for scripts/scan_tep_gaps.py."""

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

from scripts.scan_tep_gaps import (
    FATE_CLOSED_NO_MERGE,
    FATE_CONFLICT,
    FATE_NEVER_ASSIGNED,
    FATE_OPEN_PR,
    _fate,
    build_gap_record,
    build_stub_tep_record,
)

# ---------------------------------------------------------------------------
# _fate
# ---------------------------------------------------------------------------


class TestFate:
    def test_no_prs(self):
        assert _fate([]) == FATE_NEVER_ASSIGNED

    def test_single_closed(self):
        prs = [{"state": "closed", "merged": False}]
        assert _fate(prs) == FATE_CLOSED_NO_MERGE

    def test_single_open(self):
        prs = [{"state": "open", "merged": False}]
        assert _fate(prs) == FATE_OPEN_PR

    def test_multiple_open_is_conflict(self):
        prs = [
            {"state": "open", "merged": False},
            {"state": "open", "merged": False},
        ]
        assert _fate(prs) == FATE_CONFLICT

    def test_open_and_closed_is_open(self):
        prs = [
            {"state": "closed", "merged": False},
            {"state": "open", "merged": False},
        ]
        assert _fate(prs) == FATE_OPEN_PR


# ---------------------------------------------------------------------------
# build_gap_record
# ---------------------------------------------------------------------------


class TestBuildGapRecord:
    def test_basic_structure(self):
        prs = [{"state": "open", "merged": False, "pr_number": 42, "html_url": "https://x"}]
        rec = build_gap_record(99, prs)
        assert rec["tep_number"] == 99
        assert rec["fate"] == FATE_OPEN_PR
        assert rec["prs"] == prs
        assert rec["renamed_from"] is None
        assert "scanned_at" in rec

    def test_renamed_from(self):
        rec = build_gap_record(171, [], renamed_from=190)
        assert rec["renamed_from"] == 190

    def test_no_prs_gives_never_assigned(self):
        rec = build_gap_record(34, [])
        assert rec["fate"] == FATE_NEVER_ASSIGNED


# ---------------------------------------------------------------------------
# build_stub_tep_record
# ---------------------------------------------------------------------------


_OPEN_PR = {
    "pr_number": 1254,
    "title": "TEP-0190: Chaos Testing Tekton",
    "state": "open",
    "merged": False,
    "merged_at": None,
    "closed_at": None,
    "created_at": "2025-06-01T10:00:00Z",
    "html_url": "https://github.com/tektoncd/community/pull/1254",
    "user": "alice",
    "body_snippet": "This is the PR body. @alice and @bob are authors.",
}


class TestBuildStubTepRecord:
    def test_no_open_prs_returns_none(self):
        closed_pr = {**_OPEN_PR, "state": "closed"}
        assert build_stub_tep_record(171, [closed_pr]) is None

    def test_basic_stub_fields(self):
        stub = build_stub_tep_record(171, [_OPEN_PR])
        assert stub is not None
        assert stub["tep_number"] == 171
        assert stub["status"] == "proposed"
        assert stub["stub"] is True
        assert stub["proposal_pr_number"] == 1254
        assert stub["proposal_pr_url"] == "https://github.com/tektoncd/community/pull/1254"

    def test_title_strips_old_tep_prefix(self):
        stub = build_stub_tep_record(171, [_OPEN_PR])
        assert stub is not None
        # Title should not still start with "TEP-0190:"
        assert not stub["title"].startswith("TEP-0190")

    def test_authors_extracted_from_body(self):
        stub = build_stub_tep_record(171, [_OPEN_PR])
        assert stub is not None
        assert "alice" in stub["authors"]
        assert "bob" in stub["authors"]

    def test_creation_date_from_pr(self):
        stub = build_stub_tep_record(171, [_OPEN_PR])
        assert stub is not None
        assert stub["creation_date"] == "2025-06-01"

    def test_all_open_prs_listed(self):
        pr2 = {**_OPEN_PR, "pr_number": 9999}
        stub = build_stub_tep_record(171, [_OPEN_PR, pr2])
        assert stub is not None
        assert set(stub["all_open_prs"]) == {1254, 9999}


# ---------------------------------------------------------------------------
# JSONL helpers (via tempfile)
# ---------------------------------------------------------------------------


class TestJsonlHelpers:
    def test_load_missing_file(self, tmp_path):
        from scripts.scan_tep_gaps import _load_jsonl

        result = _load_jsonl(tmp_path / "missing.jsonl")
        assert result == {}

    def test_load_and_key_by_tep_number(self, tmp_path):
        from scripts.scan_tep_gaps import _load_jsonl

        f = tmp_path / "gaps.jsonl"
        f.write_text(json.dumps({"tep_number": 13, "fate": "closed_no_merge"}) + "\n")
        result = _load_jsonl(f)
        assert result[13]["fate"] == "closed_no_merge"

    def test_append_jsonl(self, tmp_path):
        from scripts.scan_tep_gaps import _append_jsonl

        f = tmp_path / "out.jsonl"
        _append_jsonl(f, [{"tep_number": 1}, {"tep_number": 2}])
        lines = f.read_text().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["tep_number"] == 1
