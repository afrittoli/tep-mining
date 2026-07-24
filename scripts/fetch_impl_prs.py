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
"""Sub-Task 5: Fetch implementation PR metadata and review comments.

Reads raw/teps.jsonl, extracts every (repo, pr_number) implementation PR link,
and fetches PR metadata + reviews + review comments from the GitHub REST API
across tektoncd/* repos generically (whichever repos actually appear in the
links, not a fixed allowlist).

Usage:
    uv run scripts/fetch_impl_prs.py
    uv run scripts/fetch_impl_prs.py --sample 84,132
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ORG = "tektoncd"
GITHUB_API = "https://api.github.com"
RATE_LIMIT_THRESHOLD = 10
RATE_LIMIT_LOG_STEP = 100

RE_CLOSES = re.compile(r"\b(?:close[sd]?|fixe[sd]?|resolve[sd]?)\s*:?\s*#(\d+)", re.IGNORECASE)


def _session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"
    session.headers["Authorization"] = f"Bearer {token}"
    return session


def _check_rate(response: requests.Response, last_logged_remaining: int | None) -> int | None:
    remaining = int(response.headers.get("X-RateLimit-Remaining", 999))
    should_log = (
        last_logged_remaining is None
        or remaining <= RATE_LIMIT_THRESHOLD
        or remaining // RATE_LIMIT_LOG_STEP < last_logged_remaining // RATE_LIMIT_LOG_STEP
    )
    if should_log:
        print(f"[rate-limit] remaining={remaining}", flush=True)
        last_logged_remaining = remaining
    if remaining <= RATE_LIMIT_THRESHOLD:
        reset_ts = int(response.headers.get("X-RateLimit-Reset", 0))
        wait = max(0, reset_ts - int(time.time())) + 2
        print(f"[rate-limit] sleeping {wait}s until reset", flush=True)
        time.sleep(wait)
    return last_logged_remaining


def _get_paginated(
    session: requests.Session,
    url: str,
    last_logged_remaining: int | None,
) -> tuple[list[dict], int | None]:
    items: list[dict] = []
    next_url: str | None = url
    while next_url:
        response = session.get(next_url, timeout=30)
        last_logged_remaining = _check_rate(response, last_logged_remaining)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            items.extend(data)
        else:
            items.append(data)
        next_url = None
        link_header = response.headers.get("Link", "")
        for part in link_header.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>")
                break
    return items, last_logged_remaining


# ---------------------------------------------------------------------------
# Selection: (repo, pr_number) tuples from raw/teps.jsonl
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _selected_impl_prs(teps: list[dict], all_teps: bool, sample: str) -> list[tuple[str, int]]:
    """Return sorted, deduplicated (repo, pr_number) tuples for the selected TEPs."""
    if all_teps or not sample:
        selected_teps = teps
    else:
        sample_numbers = {int(item.strip()) for item in sample.split(",") if item.strip()}
        selected_teps = [t for t in teps if t.get("tep_number") in sample_numbers]

    pairs: set[tuple[str, int]] = set()
    for tep in selected_teps:
        for link in tep.get("impl_pr_links_detail", []):
            pairs.add((str(link["repo"]), int(link["pr_number"])))
    return sorted(pairs)


# ---------------------------------------------------------------------------
# Record builders
# ---------------------------------------------------------------------------


def _user_login(obj: dict, field: str = "user") -> str | None:
    user = obj.get(field)
    if not isinstance(user, dict):
        return None
    login = user.get("login")
    return str(login) if login else None


def _linked_issues(body: str) -> list[int]:
    return sorted({int(n) for n in RE_CLOSES.findall(body or "")})


def _pr_record(repo: str, pr: dict, reviews: list[dict]) -> dict:
    reviewer_logins = sorted({login for review in reviews if (login := _user_login(review))})
    review_decision = "COMMENTED"
    for decision in ["CHANGES_REQUESTED", "APPROVED", "DISMISSED", "COMMENTED"]:
        if any(review.get("state") == decision for review in reviews):
            review_decision = decision
            break
    return {
        "repo": repo,
        "pr_number": int(pr["number"]),
        "title": str(pr.get("title") or ""),
        "body": str(pr.get("body") or ""),
        "labels": [
            str(label.get("name", "")) for label in pr.get("labels", []) if label.get("name")
        ],
        "files_changed": pr.get("changed_files"),
        "additions": pr.get("additions"),
        "deletions": pr.get("deletions"),
        "linked_issues": _linked_issues(pr.get("body") or ""),
        "created_at": pr.get("created_at"),
        "merged_at": pr.get("merged_at"),
        "reviewer_logins": reviewer_logins,
        "review_decision": review_decision,
    }


def _review_comment_records(repo: str, pr_number: int, comments: list[dict]) -> list[dict]:
    return [
        {
            "repo": repo,
            "pr_number": pr_number,
            "comment_id": int(comment["id"]),
            "body": str(comment.get("body") or ""),
            "path": comment.get("path"),
            "line": comment.get("line"),
            "author": _user_login(comment),
            "created_at": comment.get("created_at"),
        }
        for comment in comments
    ]


# ---------------------------------------------------------------------------
# Existing-record loading (for incremental skip)
# ---------------------------------------------------------------------------


def _load_existing_prs(path: Path) -> set[tuple[str, int]]:
    existing: set[tuple[str, int]] = set()
    for record in _load_jsonl(path):
        existing.add((str(record["repo"]), int(record["pr_number"])))
    return existing


def _load_existing_review_comments(path: Path) -> set[tuple[str, int, int]]:
    existing: set[tuple[str, int, int]] = set()
    for record in _load_jsonl(path):
        existing.add((str(record["repo"]), int(record["pr_number"]), int(record["comment_id"])))
    return existing


def _append_jsonl(path: Path, records: list[dict]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

CSS = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, "Segoe UI", system-ui, sans-serif; font-size: 14px; line-height: 1.6; background: #ffffff; color: #1f2328; padding: 32px 16px; }
  .container { max-width: 900px; margin: 0 auto; }
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


def _build_report(
    pr_records: list[dict],
    review_records: list[dict],
    not_found: list[dict],
    selected_count: int,
) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    review_counts: dict[tuple[str, int], int] = {}
    for review in review_records:
        key = (review["repo"], int(review["pr_number"]))
        review_counts[key] = review_counts.get(key, 0) + 1

    by_repo: dict[str, int] = {}
    for record in pr_records:
        by_repo[record["repo"]] = by_repo.get(record["repo"], 0) + 1
    repo_rows = "".join(
        f"<tr><td>{repo}</td><td>{count}</td></tr>"
        for repo, count in sorted(by_repo.items(), key=lambda kv: -kv[1])
    )

    pr_rows = []
    for record in sorted(pr_records, key=lambda r: (r["repo"], r["pr_number"])):
        repo = record["repo"]
        pr_number = record["pr_number"]
        key = (repo, pr_number)
        pr_rows.append(
            "<tr>"
            f'<td><a href="https://github.com/{ORG}/{repo}/pull/{pr_number}">{repo}#{pr_number}</a></td>'
            f"<td>{record['title']}</td>"
            f"<td>{record['review_decision']}</td>"
            f"<td>+{record['additions'] or 0}/-{record['deletions'] or 0} ({record['files_changed'] or 0} files)</td>"
            f"<td>{review_counts.get(key, 0)}</td>"
            "</tr>"
        )

    not_found_rows = "".join(
        f'<tr><td><a href="https://github.com/{ORG}/{r["repo"]}/pull/{r["pr_number"]}">{r["repo"]}#{r["pr_number"]}</a></td></tr>'
        for r in sorted(not_found, key=lambda r: (r["repo"], r["pr_number"]))
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Implementation PR Report</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <h1>Implementation PR Report</h1>
  <p class="subtitle">Generated {generated} &mdash; source: <code>raw/impl_prs.jsonl</code> and <code>raw/impl_pr_reviews.jsonl</code></p>
  <div class="summary-grid">
    <div class="card"><div class="num">{selected_count}</div><div class="label">Selected PR links</div></div>
    <div class="card"><div class="num">{len(pr_records)}</div><div class="label">Fetched PR records</div></div>
    <div class="card"><div class="num">{len(not_found)}</div><div class="label">Not found (404)</div></div>
    <div class="card"><div class="num">{len(review_records)}</div><div class="label">Review comments</div></div>
  </div>
  <details open>
    <summary>PRs by repo</summary>
    <div class="details-body">
      <table>
        <thead><tr><th>Repo</th><th>PR count</th></tr></thead>
        <tbody>{repo_rows}</tbody>
      </table>
    </div>
  </details>
  <details open>
    <summary>PR records</summary>
    <div class="details-body">
      <table>
        <thead><tr><th>PR</th><th>Title</th><th>Review decision</th><th>Size</th><th>Comment count</th></tr></thead>
        <tbody>{"".join(pr_rows)}</tbody>
      </table>
    </div>
  </details>
  <details>
    <summary>Not found (404 — deleted or transferred)</summary>
    <div class="details-body">
      <table>
        <thead><tr><th>PR</th></tr></thead>
        <tbody>{not_found_rows or "<tr><td>None</td></tr>"}</tbody>
      </table>
    </div>
  </details>
  <footer>Made with IBM Bob</footer>
</div>
</body>
</html>
"""


def _write_report(
    path: Path,
    pr_records: list[dict],
    review_records: list[dict],
    not_found: list[dict],
    selected_count: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _build_report(pr_records, review_records, not_found, selected_count),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch implementation PR metadata and reviews across tektoncd/* repos"
    )
    parser.add_argument("--teps-jsonl", default="raw/teps.jsonl")
    parser.add_argument("--sample", default="", help="Comma-separated TEP numbers")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--output-prs", default="raw/impl_prs.jsonl")
    parser.add_argument("--output-reviews", default="raw/impl_pr_reviews.jsonl")
    parser.add_argument("--report", default="reports/impl_prs_report.html")
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

    selected = _selected_impl_prs(teps, args.all, args.sample)
    output_prs_path = Path(args.output_prs)
    output_reviews_path = Path(args.output_reviews)
    existing_prs = _load_existing_prs(output_prs_path)
    existing_comments = _load_existing_review_comments(output_reviews_path)
    session = _session(args.token)

    print(f"[progress] selected {len(selected)} implementation PR(s)", flush=True)

    last_logged_remaining: int | None = None
    fetched_404 = 0
    for index, (repo, pr_number) in enumerate(selected, start=1):
        if (repo, pr_number) in existing_prs:
            continue

        print(
            f"[progress] fetching {repo}#{pr_number} ({index}/{len(selected)})",
            flush=True,
        )
        pr_url = f"{GITHUB_API}/repos/{ORG}/{repo}/pulls/{pr_number}"
        response = session.get(pr_url, timeout=30)
        last_logged_remaining = _check_rate(response, last_logged_remaining)

        if response.status_code == 404:
            fetched_404 += 1
            _append_jsonl(output_prs_path, [{"repo": repo, "pr_number": pr_number, "status": 404}])
            existing_prs.add((repo, pr_number))
            print(f"[progress] {repo}#{pr_number}: 404 not found", flush=True)
            continue

        response.raise_for_status()
        pr = response.json()

        reviews, last_logged_remaining = _get_paginated(
            session, f"{pr_url}/reviews", last_logged_remaining
        )
        comments, last_logged_remaining = _get_paginated(
            session, f"{pr_url}/comments", last_logged_remaining
        )

        _append_jsonl(output_prs_path, [_pr_record(repo, pr, reviews)])
        existing_prs.add((repo, pr_number))

        new_comments = []
        for comment_record in _review_comment_records(repo, pr_number, comments):
            key = (repo, pr_number, comment_record["comment_id"])
            if key not in existing_comments:
                new_comments.append(comment_record)
                existing_comments.add(key)
        _append_jsonl(output_reviews_path, new_comments)

        print(
            f"[progress] {repo}#{pr_number}: reviews={len(reviews)} comments={len(comments)} "
            f"new_comment_records={len(new_comments)}",
            flush=True,
        )

    all_pr_records = [r for r in _load_jsonl(output_prs_path) if r.get("status") != 404]
    not_found_records = [r for r in _load_jsonl(output_prs_path) if r.get("status") == 404]
    all_review_records = _load_jsonl(output_reviews_path)

    _write_report(
        Path(args.report), all_pr_records, all_review_records, not_found_records, len(selected)
    )

    print("\n=== Coverage ===")
    print(f"Selected     : {len(selected)}")
    print(f"Fetched      : {len(all_pr_records)}")
    print(f"Not found    : {len(not_found_records)}")
    print(f"Newly 404'd  : {fetched_404}")
    print(f"Review comments total: {len(all_review_records)}")
    print(f"Written: {args.output_prs}")
    print(f"Written: {args.output_reviews}")
    print(f"Written: {args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
