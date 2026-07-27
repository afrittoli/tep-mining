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
"""Sub-Task 6: Cross-repo TEP reference search.

Augments raw/impl_prs.jsonl by discovering implementation PRs that reference a TEP
but were never linked in the TEP file itself (and therefore missed by Sub-Task 5).
For each TEP number, searches org:tektoncd for PRs mentioning "TEP-NNNN" anywhere
(title or body, not just title), confirms each hit really names that TEP number,
excludes the TEP's own known community proposal/doc PRs (from raw/tep_pr_map.json —
those aren't implementation), and fetches anything genuinely new with the same
fetch_one_impl_pr() Sub-Task 5 uses, tagged discovered_via: "search".

Usage:
    uv run scripts/cross_repo_search.py
    uv run scripts/cross_repo_search.py --sample 84,132
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from scripts.fetch_impl_prs import (
    GITHUB_API,
    ORG,
    _append_jsonl,
    _check_rate,
    _load_existing_prs,
    _load_existing_review_comments,
    _load_jsonl,
    _session,
    fetch_one_impl_pr,
)

load_dotenv()

DISCOVERED_VIA_SEARCH = "search"
SEARCH_RATE_LIMIT_SLEEP = 2.2  # search API: 30 req/min authenticated, stay comfortably under

# Confirms a search hit's title+body actually names the exact TEP number requested —
# GitHub's search tokenization on a quoted phrase is not a guaranteed exact match.
RE_TEP_CONFIRM = re.compile(r"\bTEP[-:\s]*0*(\d{1,4})\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def _search_prs_for_tep(
    session, tep_number: int, last_logged_remaining: int | None
) -> tuple[list[dict], int | None]:
    """Search org:tektoncd for PRs mentioning TEP-NNNN, anywhere, paginated.

    Only the zero-padded "TEP-NNNN" form is queried, deliberately. Verified against the
    live search API across 6 real TEP numbers (2, 21, 52, 90, 104, 142): querying
    "TEP_NNNN" (underscore) and "TEPNNNN" (concatenated) returned 0 genuine hits every
    time, and non-padded "TEP-N" returned zero *new* hits after checking the actual
    results — they were either duplicates already covered by the padded query, or false
    positives from GitHub's search matching a bare short number inside unrelated text
    (e.g. "TEP-21" matching "k8s 1.21" / "v0.21.0"; "TEP-2" matching PRs with no "TEP"
    mention at all). The TEP corpus convention (teps/NNNN-*.md, always 4-digit
    zero-padded) is consistent enough that real mentions almost always copy that exact
    format, so widening the query adds search volume and false-positive risk without
    adding recall.
    """
    query = f'org:{ORG} "TEP-{tep_number:04d}" type:pr'
    url: str | None = f"{GITHUB_API}/search/issues"
    params: dict[str, str | int] = {"q": query, "per_page": 30}
    items: list[dict] = []
    while url:
        response = session.get(url, params=params, timeout=30)
        last_logged_remaining = _check_rate(response, last_logged_remaining)
        response.raise_for_status()
        items.extend(response.json().get("items", []))

        next_url: str | None = None
        for part in response.headers.get("Link", "").split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>")
                break
        url = next_url
        params = {}
        if next_url:
            time.sleep(SEARCH_RATE_LIMIT_SLEEP)
    return items, last_logged_remaining


def _confirmed_hits(hits: list[dict], tep_number: int) -> list[dict]:
    """Keep only hits whose title+body genuinely mention this exact TEP number."""
    confirmed = []
    for item in hits:
        text = f"{item.get('title') or ''} {item.get('body') or ''}"
        numbers = {int(n) for n in RE_TEP_CONFIRM.findall(text)}
        if tep_number in numbers:
            confirmed.append(item)
    return confirmed


def _repo_and_number(item: dict) -> tuple[str, int]:
    """Extract (repo, pr_number) from a GitHub search API issue/PR item."""
    repo = str(item["repository_url"]).rsplit("/", 1)[-1]
    return repo, int(item["number"])


def _own_pr_numbers(tep_pr_map: dict, tep_number: int) -> set[int]:
    """PR numbers already known to be this TEP's own community proposal/doc history."""
    return {int(n) for n in tep_pr_map.get(str(tep_number), [])}


def _linked_count(tep: dict) -> int:
    """How many distinct (repo, pr_number) links the TEP author already declared."""
    links = tep.get("impl_pr_links_detail") or []
    return len({(link["repo"], link["pr_number"]) for link in links})


# ---------------------------------------------------------------------------
# processed/ layer — dated snapshot + `latest` symlink
# ---------------------------------------------------------------------------


def _write_coverage(coverage: list[dict], processed_dir: Path) -> Path:
    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    run_dir = processed_dir / date_str
    run_dir.mkdir(parents=True, exist_ok=True)

    coverage_path = run_dir / "coverage.json"
    coverage_path.write_text(
        json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    latest_link = processed_dir / "latest"
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(date_str, target_is_directory=True)

    return coverage_path


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px; line-height: 1.6; background: #ffffff; color: #1f2328; padding: 32px 16px; }
  .container { max-width: 860px; margin: 0 auto; }
  h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .subtitle { color: #57606a; font-size: 13px; margin-bottom: 20px; }
  .summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
  .card { background: #f7f8fa; border: 1px solid #e5e7eb; border-radius: 6px; padding: 14px 16px; }
  .card .num { font-size: 28px; font-weight: 700; color: #1f2328; }
  .card .label { font-size: 12px; color: #57606a; margin-top: 2px; }
  details { margin-top: 16px; border: 1px solid #e5e7eb; border-radius: 6px; background: #ffffff; }
  summary { cursor: pointer; list-style: none; padding: 12px 14px; font-weight: 600; background: #f7f8fa; border-bottom: 1px solid #e5e7eb; }
  summary::-webkit-details-marker { display: none; }
  .details-body { padding: 0 0 4px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th { background: #f7f8fa; text-align: left; padding: 7px 10px; font-weight: 600; border-bottom: 2px solid #e5e7eb; color: #57606a; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  tbody tr:nth-child(even) { background: #f7f8fa; }
  tbody td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: top; }
  a { color: #3b82d4; text-decoration: none; }
  footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid #e5e7eb; text-align: center; font-size: 12px; color: #57606a; }
"""


def _build_report(coverage: list[dict]) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    total_linked = sum(c["linked"] for c in coverage)
    total_discovered = sum(c["discovered"] for c in coverage)
    total = total_linked + total_discovered
    under_linking_rate = (total_discovered / total * 100) if total else 0.0

    rows = []
    for c in sorted(coverage, key=lambda c: -c["discovered"]):
        rows.append(
            "<tr>"
            f"<td>TEP-{c['tep_number']:04d}</td>"
            f"<td>{c['linked']}</td>"
            f"<td>{c['search_hits_confirmed']}</td>"
            f"<td>{c['discovered']}</td>"
            "</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Cross-Repo Search Report</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <h1>Cross-Repo Search Report</h1>
  <p class="subtitle">Generated {generated} &mdash; source: <code>processed/latest/coverage.json</code></p>
  <div class="summary-grid">
    <div class="card"><div class="num">{len(coverage)}</div><div class="label">TEPs searched</div></div>
    <div class="card"><div class="num">{total_linked}</div><div class="label">Already linked</div></div>
    <div class="card"><div class="num">{total_discovered}</div><div class="label">Newly discovered</div></div>
    <div class="card"><div class="num">{under_linking_rate:.1f}%</div><div class="label">Under-linking rate</div></div>
  </div>
  <details open>
    <summary>Per-TEP coverage</summary>
    <div class="details-body">
      <table>
        <thead><tr><th>TEP</th><th>Linked</th><th>Search hits confirmed</th><th>Newly discovered</th></tr></thead>
        <tbody>{"".join(rows)}</tbody>
      </table>
    </div>
  </details>
  <footer>Made with IBM Bob</footer>
</div>
</body>
</html>
"""


def _write_report(path: Path, coverage: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_build_report(coverage), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Discover implementation PRs referencing a TEP that weren't linked in the TEP file"
    )
    parser.add_argument("--teps-jsonl", default="raw/teps.jsonl")
    parser.add_argument("--tep-pr-map", default="raw/tep_pr_map.json")
    parser.add_argument("--impl-prs-jsonl", default="raw/impl_prs.jsonl")
    parser.add_argument("--output-reviews", default="raw/impl_pr_reviews.jsonl")
    parser.add_argument("--processed-dir", default="processed")
    parser.add_argument("--report", default="reports/cross_repo_search_report.html")
    parser.add_argument("--sample", default="", help="Comma-separated TEP numbers")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        help="GitHub token (default: $GITHUB_TOKEN or $GH_TOKEN)",
    )
    args = parser.parse_args(argv)

    if not args.token:
        print(
            "ERROR: No GitHub token found. Set GITHUB_TOKEN in .env or pass --token.",
            file=sys.stderr,
        )
        return 1

    teps = _load_jsonl(Path(args.teps_jsonl))
    if not teps:
        print(f"ERROR: no TEP records found in {args.teps_jsonl}", file=sys.stderr)
        return 1

    tep_pr_map_path = Path(args.tep_pr_map)
    tep_pr_map = json.loads(tep_pr_map_path.read_text()) if tep_pr_map_path.exists() else {}

    if args.all or not args.sample:
        tep_numbers = sorted({int(t["tep_number"]) for t in teps})
    else:
        tep_numbers = sorted(int(n) for n in args.sample.split(",") if n.strip())

    impl_prs_path = Path(args.impl_prs_jsonl)
    output_reviews_path = Path(args.output_reviews)
    existing_prs = _load_existing_prs(impl_prs_path)
    existing_comments = _load_existing_review_comments(output_reviews_path)
    teps_by_number = {int(t["tep_number"]): t for t in teps}

    session = _session(args.token)
    last_logged_remaining: int | None = None
    coverage: list[dict] = []
    total_new_prs = 0
    total_new_comments = 0

    print(f"[progress] searching {len(tep_numbers)} TEP number(s)", flush=True)

    for index, tep_number in enumerate(tep_numbers, start=1):
        print(
            f"[progress] TEP-{tep_number:04d} ({index}/{len(tep_numbers)})",
            flush=True,
        )
        hits, last_logged_remaining = _search_prs_for_tep(
            session, tep_number, last_logged_remaining
        )
        confirmed = _confirmed_hits(hits, tep_number)
        own_prs = _own_pr_numbers(tep_pr_map, tep_number)
        linked_prs = {
            (link["repo"], link["pr_number"])
            for link in teps_by_number.get(tep_number, {}).get("impl_pr_links_detail", [])
        }

        # "Discovered" is defined by set membership (confirmed search hit, not already linked,
        # not the TEP's own community doc PR) — not by whether a fetch happened in *this*
        # process. Interrupted/resumed runs must not under-count TEPs whose PRs were already
        # fetched by an earlier attempt.
        candidate_prs = set()
        for item in confirmed:
            repo, pr_number = _repo_and_number(item)
            if repo == "community" and pr_number in own_prs:
                continue  # the TEP's own proposal/doc PR, not an implementation PR
            candidate_prs.add((repo, pr_number))
        discovered_prs = candidate_prs - linked_prs
        discovered_this_tep = len(discovered_prs)

        for repo, pr_number in discovered_prs:
            if (repo, pr_number) in existing_prs:
                continue  # already fetched, by this run or an earlier one

            pr_record, review_records, last_logged_remaining = fetch_one_impl_pr(
                session, repo, pr_number, DISCOVERED_VIA_SEARCH, last_logged_remaining
            )
            existing_prs.add((repo, pr_number))
            _append_jsonl(impl_prs_path, [pr_record])
            total_new_prs += 1

            new_comments = []
            for comment_record in review_records:
                key = (repo, pr_number, comment_record["comment_id"])
                if key not in existing_comments:
                    new_comments.append(comment_record)
                    existing_comments.add(key)
            _append_jsonl(output_reviews_path, new_comments)
            total_new_comments += len(new_comments)

            print(f"[progress]   discovered {repo}#{pr_number}", flush=True)

        coverage.append(
            {
                "tep_number": tep_number,
                "linked": _linked_count(teps_by_number.get(tep_number, {})),
                "search_hits_confirmed": len(confirmed),
                "discovered": discovered_this_tep,
            }
        )

        time.sleep(SEARCH_RATE_LIMIT_SLEEP)

    coverage_path = _write_coverage(coverage, Path(args.processed_dir))
    _write_report(Path(args.report), coverage)

    total_linked = sum(c["linked"] for c in coverage)
    total_discovered = sum(c["discovered"] for c in coverage)
    print("\n=== Cross-Repo Search Summary ===")
    print(f"TEPs searched        : {len(coverage)}")
    print(f"Already linked       : {total_linked}")
    print(f"Discovered via search: {total_discovered}")
    print(f"  fetched this run   : {total_new_prs}")
    print(f"  already fetched    : {total_discovered - total_new_prs}")
    print(f"New review comments  : {total_new_comments}")
    if total_linked + total_discovered:
        rate = total_discovered / (total_linked + total_discovered) * 100
        print(f"Under-linking rate   : {rate:.1f}%")
    print(f"Written: {args.impl_prs_jsonl}")
    print(f"Written: {args.output_reviews}")
    print(f"Written: {coverage_path}")
    print(f"Written: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
