#!/usr/bin/env python3
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
"""Sub-Task 2: Parse TEP .md files and emit raw/teps.jsonl.

Usage:
    python scripts/parse_teps.py --teps-dir /path/to/tektoncd/community/teps
    python scripts/parse_teps.py --teps-dir /path/to/teps --output raw/teps.jsonl
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from ruamel.yaml import YAML, YAMLError

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YAML_SEP = "---"
EXCLUDED = {"README.md", "README.md.mustache", "OWNERS"}

# Regex: TEP filename e.g. 0075-object-param-and-result-types.md
RE_TEP_FILENAME = re.compile(r"^(\d{4})-.*\.md$")

# Regex: GitHub PR full URL (tektoncd org only, pull requests only)
RE_PR_URL = re.compile(
    r"https://github\.com/tektoncd/([^/\s)\"']+)/pull/(\d+)"
)

# Regex: markdown link with a PR URL  e.g. [some text](https://github.com/...)
RE_MD_LINK = re.compile(
    r"\[([^\]]*)\]\(https://github\.com/tektoncd/[^/\s)\"']+/pull/\d+\)"
)

# Regex: shorthand  e.g. tektoncd/pipeline#123
RE_SHORTHAND = re.compile(r"tektoncd/([a-z0-9_-]+)#(\d+)")

# Regex: H2 / H3 headings (after frontmatter)
RE_HEADING = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)

# Status normalisation map  (strip trailing spaces, lower, unquote)
_STATUS_ALIASES = {
    "implementing": "implementable",  # rare but present in corpus
}


def _normalise_status(raw: str) -> str:
    s = str(raw).strip().strip("'\"").lower()
    return _STATUS_ALIASES.get(s, s)


# ---------------------------------------------------------------------------
# YAML frontmatter parsing
# ---------------------------------------------------------------------------

def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split a markdown file into (frontmatter_yaml, body).

    Returns empty strings for either part if the delimiter is absent.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != YAML_SEP:
        return "", text
    # Find the closing ---
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == YAML_SEP:
            fm = "".join(lines[1:i])
            body = "".join(lines[i + 1:])
            return fm, body
    return "", text


def _parse_frontmatter(yaml_text: str) -> dict:
    yaml = YAML()
    yaml.preserve_quotes = True
    try:
        data = yaml.load(yaml_text)
    except YAMLError:
        return {}
    return dict(data) if data else {}


def _str(value) -> str:
    """Coerce a YAML scalar to a plain Python str."""
    if value is None:
        return ""
    return str(value).strip()


def _list_of_str(value) -> list[str]:
    """Coerce authors / collaborators to a list of plain strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value]
    # Sometimes a single author is stored as a scalar
    return [str(value).strip()]


def _date_str(value) -> str:
    """Return ISO date string or empty string."""
    if value is None:
        return ""
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip().strip("'\"")


# ---------------------------------------------------------------------------
# Link extraction helpers
# ---------------------------------------------------------------------------

def _classify_link(raw_url: str, surrounding_text: str) -> str:
    """Classify a PR link as full-url, markdown-link, or shorthand.

    surrounding_text is the full line/context containing the URL so we
    can detect whether it was embedded in a markdown link syntax.
    """
    # Check if this URL appears inside markdown link syntax [text](URL)
    if re.search(
        r"\[[^\]]*\]\(" + re.escape(raw_url) + r"\)", surrounding_text
    ):
        return "markdown-link"
    return "full-url"


def _extract_pr_links(body: str) -> list[dict]:
    """Extract all tektoncd GitHub PR links from the markdown body.

    Returns a list of dicts:
        {"url": str, "repo": str, "pr_number": int, "format": str}

    Formats: "full-url", "markdown-link"
    (Shorthand tektoncd/repo#N links are excluded; they typically refer to
    issues, not pulls, and cannot be unambiguously classified as PRs without
    an API call.)
    """
    seen: set[str] = set()
    results: list[dict] = []

    for match in RE_PR_URL.finditer(body):
        url = match.group(0)
        if url in seen:
            continue
        seen.add(url)
        repo = match.group(1)
        pr_number = int(match.group(2))
        # Determine format: find the line containing this URL
        start = body.rfind("\n", 0, match.start()) + 1
        end = body.find("\n", match.end())
        line = body[start:end if end != -1 else len(body)]
        fmt = _classify_link(url, line)
        results.append({
            "url": url,
            "repo": repo,
            "pr_number": pr_number,
            "format": fmt,
        })

    return results


# ---------------------------------------------------------------------------
# Section / word-count helpers
# ---------------------------------------------------------------------------

def _extract_sections(body: str) -> tuple[list[str], dict[str, int]]:
    """Return (sections_present, word_count_per_section).

    sections_present: ordered list of "## Heading" / "### Heading" strings.
    word_count_per_section: maps heading text -> approximate word count of
        the content under that heading (up to the next same-or-higher heading).
    """
    headings: list[tuple[int, str, int]] = []  # (level, text, start_pos)
    for m in RE_HEADING.finditer(body):
        level = len(m.group(1))  # 2 or 3
        text = m.group(2).strip()
        headings.append((level, text, m.end()))

    sections_present: list[str] = [
        ("#" * level) + " " + text for level, text, _ in headings
    ]

    word_count: dict[str, int] = {}
    for i, (level, text, start) in enumerate(headings):
        # Content ends at the next heading of same or higher level, or EOF
        end = len(body)
        for j in range(i + 1, len(headings)):
            nlevel, _, nstart = headings[j]
            if nlevel <= level:
                end = nstart - len(RE_HEADING.pattern)  # rough; good enough
                break
            end = nstart
        section_text = body[start:end]
        word_count[text] = len(section_text.split())

    return sections_present, word_count


# ---------------------------------------------------------------------------
# Age calculation
# ---------------------------------------------------------------------------

def _age_days(creation: str, last_updated: str) -> int | None:
    """Return (last_updated - creation) in days, or None if either is absent."""
    try:
        d1 = date.fromisoformat(creation)
        d2 = date.fromisoformat(last_updated)
        return (d2 - d1).days
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Single-file parser
# ---------------------------------------------------------------------------

def parse_tep_file(md_path: Path, teps_dir: Path) -> dict | None:
    """Parse a single TEP .md file and return its record dict, or None on error."""
    text = md_path.read_text(encoding="utf-8", errors="replace")
    fm_text, body = _split_frontmatter(text)
    if not fm_text:
        return None

    fm = _parse_frontmatter(fm_text)
    if not fm:
        return None

    # --- Require at minimum a tep_number derivable from filename ---
    m = RE_TEP_FILENAME.match(md_path.name)
    if not m:
        return None
    tep_number = int(m.group(1))

    creation_date = _date_str(fm.get("creation-date"))
    last_updated = _date_str(fm.get("last-updated", fm.get("creation-date")))

    pr_links = _extract_pr_links(body)
    sections_present, word_count_per_section = _extract_sections(body)

    return {
        # --- Identity ---
        "tep_number": tep_number,
        "source_file": str(md_path.relative_to(teps_dir)),
        # --- Frontmatter ---
        "title": _str(fm.get("title")),
        "status": _normalise_status(fm.get("status", "")),
        "authors": _list_of_str(fm.get("authors")),
        "collaborators": _list_of_str(fm.get("collaborators")),
        "creation_date": creation_date,
        "last_updated": last_updated,
        # --- Derived ---
        "age_days": _age_days(creation_date, last_updated),
        "sections_present": sections_present,
        "word_count_per_section": word_count_per_section,
        "impl_pr_links": [lnk["url"] for lnk in pr_links],
        "impl_pr_links_detail": pr_links,
    }


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def _load_existing(output_path: Path) -> dict[int, dict]:
    """Load existing JSONL records keyed by tep_number."""
    existing: dict[int, dict] = {}
    if not output_path.exists():
        return existing
    with output_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                existing[rec["tep_number"]] = rec
            except (json.JSONDecodeError, KeyError):
                pass
    return existing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse TEP .md files and emit raw/teps.jsonl"
    )
    parser.add_argument(
        "--teps-dir",
        default=os.environ.get("COMMUNITY_REPO_PATH", "") + "/teps",
        help="Path to the tektoncd/community/teps/ directory",
    )
    parser.add_argument(
        "--output",
        default="raw/teps.jsonl",
        help="Output JSONL file (default: raw/teps.jsonl)",
    )
    args = parser.parse_args(argv)

    teps_dir = Path(args.teps_dir).expanduser().resolve()
    output_path = Path(args.output)

    if not teps_dir.is_dir():
        print(f"ERROR: teps-dir not found: {teps_dir}", file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing records to support idempotent appends
    existing = _load_existing(output_path)
    initial_count = len(existing)

    new_records: list[dict] = []
    errors: list[str] = []

    md_files = sorted(teps_dir.glob("*.md"))
    for md_path in md_files:
        if md_path.name in EXCLUDED:
            continue
        if not RE_TEP_FILENAME.match(md_path.name):
            continue

        record = parse_tep_file(md_path, teps_dir)
        if record is None:
            errors.append(md_path.name)
            continue

        if record["tep_number"] in existing:
            continue  # already present — skip (idempotent)

        new_records.append(record)
        existing[record["tep_number"]] = record

    # Append new records to JSONL
    if new_records:
        with output_path.open("a", encoding="utf-8") as fh:
            for rec in new_records:
                fh.write(json.dumps(rec, default=str) + "\n")

    # --- Summary ---
    all_records = list(existing.values())
    total = len(all_records)
    status_counts: Counter = Counter(r["status"] for r in all_records)
    with_links = sum(1 for r in all_records if r["impl_pr_links"])
    without_links = total - with_links

    print(f"\n=== TEP Parse Summary ===")
    print(f"Output file  : {output_path}")
    print(f"Pre-existing : {initial_count}")
    print(f"Newly added  : {len(new_records)}")
    print(f"Total records: {total}")
    if errors:
        print(f"Parse errors : {len(errors)} ({', '.join(errors)})")
    print(f"\nStatus breakdown:")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {status:<20} {count}")
    print(f"\nImpl PR links:")
    print(f"  With links   : {with_links}")
    print(f"  Without links: {without_links}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
