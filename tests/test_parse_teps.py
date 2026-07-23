"""Unit tests for scripts/parse_teps.py."""

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
import textwrap

from scripts.parse_teps import (
    _age_days,
    _classify_link,
    _extract_pr_links,
    _extract_sections,
    _load_existing,
    _normalise_status,
    _split_frontmatter,
    main,
    parse_tep_file,
)

# ---------------------------------------------------------------------------
# _normalise_status
# ---------------------------------------------------------------------------


class TestNormaliseStatus:
    def test_implemented(self):
        assert _normalise_status("implemented") == "implemented"

    def test_strips_whitespace(self):
        assert _normalise_status("  proposed  ") == "proposed"

    def test_strips_quotes(self):
        assert _normalise_status("'implemented'") == "implemented"
        assert _normalise_status('"proposed"') == "proposed"

    def test_lowercase(self):
        assert _normalise_status("Implementable") == "implementable"

    def test_alias_implementing(self):
        assert _normalise_status("implementing") == "implementable"

    def test_trailing_space_in_value(self):
        # Corpus has "implementable " (trailing space) on some records
        assert _normalise_status("implementable ") == "implementable"


# ---------------------------------------------------------------------------
# _split_frontmatter
# ---------------------------------------------------------------------------


class TestSplitFrontmatter:
    def test_standard(self):
        text = "---\ntitle: Foo\n---\n\n## Body\n"
        fm, body = _split_frontmatter(text)
        assert fm.strip() == "title: Foo"
        assert "## Body" in body

    def test_no_frontmatter(self):
        text = "# Just a heading\n"
        fm, body = _split_frontmatter(text)
        assert fm == ""
        assert body == text

    def test_empty_frontmatter(self):
        text = "---\n---\n\nBody here\n"
        fm, body = _split_frontmatter(text)
        assert fm == ""
        assert "Body here" in body

    def test_unclosed_frontmatter(self):
        text = "---\ntitle: Foo\n"
        fm, body = _split_frontmatter(text)
        assert fm == ""


# ---------------------------------------------------------------------------
# _extract_pr_links
# ---------------------------------------------------------------------------


class TestExtractPrLinks:
    def test_plain_url(self):
        body = "- https://github.com/tektoncd/pipeline/pull/1234\n"
        links = _extract_pr_links(body)
        assert len(links) == 1
        assert links[0]["url"] == "https://github.com/tektoncd/pipeline/pull/1234"
        assert links[0]["repo"] == "pipeline"
        assert links[0]["pr_number"] == 1234
        assert links[0]["format"] == "full-url"

    def test_markdown_link(self):
        body = "[My PR](https://github.com/tektoncd/triggers/pull/628)\n"
        links = _extract_pr_links(body)
        assert len(links) == 1
        assert links[0]["format"] == "markdown-link"
        assert links[0]["repo"] == "triggers"

    def test_deduplication(self):
        url = "https://github.com/tektoncd/pipeline/pull/100"
        body = f"- {url}\n- {url}\n"
        links = _extract_pr_links(body)
        assert len(links) == 1

    def test_non_pull_url_ignored(self):
        body = "See https://github.com/tektoncd/pipeline/issues/99\n"
        links = _extract_pr_links(body)
        assert links == []

    def test_non_tektoncd_url_ignored(self):
        body = "See https://github.com/kubernetes/kubernetes/pull/1\n"
        links = _extract_pr_links(body)
        assert links == []

    def test_multiple_repos(self):
        body = (
            "- https://github.com/tektoncd/pipeline/pull/10\n"
            "- https://github.com/tektoncd/triggers/pull/20\n"
        )
        links = _extract_pr_links(body)
        repos = {lnk["repo"] for lnk in links}
        assert repos == {"pipeline", "triggers"}


# ---------------------------------------------------------------------------
# _extract_sections
# ---------------------------------------------------------------------------


class TestExtractSections:
    def test_h2_only(self):
        body = "## Summary\nFoo bar baz.\n\n## Motivation\nMore words here.\n"
        sections, wc = _extract_sections(body)
        assert "## Summary" in sections
        assert "## Motivation" in sections

    def test_h3_included(self):
        body = "## Summary\n\n### Goals\nGoal text.\n"
        sections, _ = _extract_sections(body)
        assert "### Goals" in sections

    def test_word_count_positive(self):
        body = "## Summary\none two three four five\n"
        _, wc = _extract_sections(body)
        assert wc.get("Summary", 0) > 0

    def test_empty_body(self):
        sections, wc = _extract_sections("")
        assert sections == []
        assert wc == {}


# ---------------------------------------------------------------------------
# _age_days
# ---------------------------------------------------------------------------


class TestAgeDays:
    def test_same_day(self):
        assert _age_days("2021-01-01", "2021-01-01") == 0

    def test_positive(self):
        assert _age_days("2021-01-01", "2021-01-11") == 10

    def test_none_on_bad_input(self):
        assert _age_days("", "2021-01-01") is None
        assert _age_days("2021-01-01", "") is None
        assert _age_days("not-a-date", "2021-01-01") is None


# ---------------------------------------------------------------------------
# _classify_link
# ---------------------------------------------------------------------------


class TestClassifyLink:
    def test_plain_url(self):
        url = "https://github.com/tektoncd/pipeline/pull/1"
        line = f"- {url}"
        assert _classify_link(url, line) == "full-url"

    def test_markdown_link(self):
        url = "https://github.com/tektoncd/pipeline/pull/1"
        line = f"[My PR]({url})"
        assert _classify_link(url, line) == "markdown-link"


# ---------------------------------------------------------------------------
# parse_tep_file (integration-style, uses tmp_path)
# ---------------------------------------------------------------------------

_MINIMAL_TEP = textwrap.dedent("""\
    ---
    title: Test TEP
    status: proposed
    authors:
      - '@alice'
    creation-date: '2022-01-01'
    last-updated: '2022-03-01'
    ---

    # TEP-0042: Test TEP

    ## Summary

    This is a test.

    ## Implementation Pull request(s)

    - https://github.com/tektoncd/pipeline/pull/999
    - [A markdown link](https://github.com/tektoncd/pipeline/pull/1000)
""")


class TestParseTepFile:
    def test_basic_fields(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        md = teps_dir / "0042-test-tep.md"
        md.write_text(_MINIMAL_TEP)
        rec = parse_tep_file(md, teps_dir)
        assert rec is not None
        assert rec["tep_number"] == 42
        assert rec["title"] == "Test TEP"
        assert rec["status"] == "proposed"
        assert rec["authors"] == ["@alice"]
        assert rec["creation_date"] == "2022-01-01"
        assert rec["last_updated"] == "2022-03-01"

    def test_age_days(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        md = teps_dir / "0042-test-tep.md"
        md.write_text(_MINIMAL_TEP)
        rec = parse_tep_file(md, teps_dir)
        assert rec["age_days"] == 59  # 2022-01-01 → 2022-03-01

    def test_impl_pr_links(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        md = teps_dir / "0042-test-tep.md"
        md.write_text(_MINIMAL_TEP)
        rec = parse_tep_file(md, teps_dir)
        assert len(rec["impl_pr_links"]) == 2
        formats = {d["format"] for d in rec["impl_pr_links_detail"]}
        assert "full-url" in formats
        assert "markdown-link" in formats

    def test_sections_present(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        md = teps_dir / "0042-test-tep.md"
        md.write_text(_MINIMAL_TEP)
        rec = parse_tep_file(md, teps_dir)
        assert "## Summary" in rec["sections_present"]
        assert "## Implementation Pull request(s)" in rec["sections_present"]

    def test_non_tep_filename_returns_none(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        md = teps_dir / "README.md"
        md.write_text(_MINIMAL_TEP)
        rec = parse_tep_file(md, teps_dir)
        assert rec is None

    def test_no_frontmatter_returns_none(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        md = teps_dir / "0001-no-fm.md"
        md.write_text("# Just a heading\nNo frontmatter here.\n")
        rec = parse_tep_file(md, teps_dir)
        assert rec is None


# ---------------------------------------------------------------------------
# main() — CLI end-to-end
# ---------------------------------------------------------------------------


class TestMain:
    def test_idempotent(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        (teps_dir / "0042-test-tep.md").write_text(_MINIMAL_TEP)
        out = tmp_path / "teps.jsonl"

        rc1 = main(["--teps-dir", str(teps_dir), "--output", str(out)])
        assert rc1 == 0
        lines_after_first = out.read_text().splitlines()

        rc2 = main(["--teps-dir", str(teps_dir), "--output", str(out)])
        assert rc2 == 0
        lines_after_second = out.read_text().splitlines()

        assert len(lines_after_first) == len(lines_after_second) == 1

    def test_missing_teps_dir(self, tmp_path):
        rc = main(
            ["--teps-dir", str(tmp_path / "nonexistent"), "--output", str(tmp_path / "out.jsonl")]
        )
        assert rc == 1

    def test_output_is_valid_jsonl(self, tmp_path):
        teps_dir = tmp_path / "teps"
        teps_dir.mkdir()
        (teps_dir / "0042-test-tep.md").write_text(_MINIMAL_TEP)
        out = tmp_path / "teps.jsonl"
        main(["--teps-dir", str(teps_dir), "--output", str(out)])
        records = [json.loads(line) for line in out.read_text().splitlines()]
        assert len(records) == 1
        assert records[0]["tep_number"] == 42


# ---------------------------------------------------------------------------
# _load_existing
# ---------------------------------------------------------------------------


class TestLoadExisting:
    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        assert _load_existing(f) == {}

    def test_missing_file(self, tmp_path):
        assert _load_existing(tmp_path / "missing.jsonl") == {}

    def test_roundtrip(self, tmp_path):
        f = tmp_path / "data.jsonl"
        f.write_text(json.dumps({"tep_number": 1, "title": "Foo"}) + "\n")
        result = _load_existing(f)
        assert result[1]["title"] == "Foo"
